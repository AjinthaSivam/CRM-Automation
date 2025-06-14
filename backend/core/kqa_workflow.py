from langgraph.graph import StateGraph, END
from langchain.prompts import PromptTemplate
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from pydantic import BaseModel
from typing import List, Dict
from .tools import SOSLQueryTool
from .llm import llm
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# State Definition
class QAState(BaseModel):
    query_text: str = ""
    search_terms: str = ""
    articles: List[Dict[str, str]] = []
    answer: str = ""
    article_count: int = 0
    sosl_query: str = ""
    error: str = ""

# Helper Functions
def extract_search_terms(query: str) -> str:
    search_terms_prompt = PromptTemplate(
        template="""
        You are a smart assistant that extracts useful search terms from user queries for a Salesforce SOSL search.

        Your task: Extract two key terms, each with a maximum of 2 words, from the following query:
        "{query}"

        Guidelines:
        - Exclude common or generic terms that appear in almost every record (e.g., "shoes & clothings")
        - Focus on specific, unique terms that will help narrow down search results and improve relevance

        Output format:
        Return ONLY a comma-separated string of the two terms. No explanations or extra text.

        Examples:
        - Query: "What technology features do golf shoes have?"
        Output: {{"terms": "golf shoes, technology"}}
        - Query: "What is the typical time window for cancelling an order at Shoes & Clothings?"
        Output: {{"terms": "cancellation, time window"}}
        """,
        input_variables=["query"]
    )
    chain = search_terms_prompt | llm
    result = chain.invoke({"query": query})
    terms = result.content.strip()
    terms = terms.replace('```json', '').replace('```', '').strip()
    if terms.startswith('{') and terms.endswith('}'):
        try:
            import json
            parsed = json.loads(terms)
            if 'terms' in parsed:
                terms = parsed['terms']
        except:
            pass
    return terms

def escape_sosl_term(term: str) -> str:
    pattern = r'([?&|!{}\[\]\(\)\^~\*:\\\'"\+\-])'
    return re.sub(pattern, r'\\\1', term)

def execute_sosl_query(search_terms: str) -> list:
    terms_list = [term.strip() for term in search_terms.split(',')]
    escaped_terms = [escape_sosl_term(term) for term in terms_list]
    formatted_terms = [f'"{term}"' if ' ' in term else term for term in escaped_terms]
    sosl_search_term = " OR ".join(formatted_terms)
    sosl_query = f"FIND {{{sosl_search_term}}} IN ALL FIELDS RETURNING Knowledge__kav(Id, Title, FAQ_Answer__c WHERE PublishStatus='Online' AND Language='en_US')"
    print(sosl_query)
    raw_result = SOSLQueryTool()._run(sosl_query)
    print(raw_result)
    try:
        search_records = raw_result.get("searchRecords", [])
        articles = [
            {
                "Id": str(record.get("Id", "")),
                "Title": str(record.get("Title", "")),
                "FAQ_Answer__c": str(record.get("FAQ_Answer__c", ""))
            }
            for record in search_records
        ]
        print(articles)
        return articles
    except Exception as e:
        print(f"DEBUG: Error in execute_sosl_query: {str(e)}")
        return []

def extract_answer(query: str, articles: list) -> str:
    answer_prompt = PromptTemplate(
        template="""
        Answer the query based on Salesforce Knowledge articles. Query: "{query}"
        Articles:
        {articles}
        
        Instructions:
        1. Provide a complete answer that includes both the fact and the explanation/reasoning
        2. If the answer is a specific number or date, explain why that number/date is important
        3. If no relevant info, return "No relevant information found"
        4. Do not include phrases like "According to the articles" or "Based on the information"
        5. Keep answers clear and informative
        
        Examples:
        Query: "What technology features do Shoes & Clothings golf shoes have?"
        Answer: "Advanced sole technology and waterproof materials"
        
        Query: "If opting for store credit, within how many days from the purchase date must you request it?"
        Answer: "90 days"
        
        Query: "Can I get a full refund for damaged running shoes after 30 days?"
        Answer: "No, the request must be submitted within 30 days of the purchase date."
        
        {format_instructions}
        """,
        input_variables=["query", "articles"],
        partial_variables={"format_instructions": StructuredOutputParser.from_response_schemas([
            ResponseSchema(name="answer", description="A concise answer to the query.", type="string"),
            ResponseSchema(name="article_count", description="Number of articles found for this query.", type="integer")
        ]).get_format_instructions()}
    )
    articles_str = "\n".join([f"Title: {a['Title']}\nFAQ_Answer__c: {a.get('FAQ_Answer__c', '')}" for a in articles])
    chain = answer_prompt | llm | StructuredOutputParser.from_response_schemas([
        ResponseSchema(name="answer", description="A concise answer to the query.", type="string")
    ])
    result = chain.invoke({"query": query, "articles": articles_str})
    print("result", result)
    return result["answer"]

# Nodes
def extract_terms_node(state: QAState) -> QAState:
    try:
        search_terms = extract_search_terms(state.query_text)
        print(search_terms)
        return QAState(query_text=state.query_text, search_terms=search_terms)
    except Exception as e:
        print(f"DEBUG: Error in extract_terms_node: {str(e)}")
        return QAState(query_text=state.query_text, error=f"Search Terms Extraction Error: {str(e)}")

def search_articles_node(state: QAState) -> QAState:
    if state.error:
        print(f"DEBUG: Error in search_articles_node: {state.error}")
        return state
    try:
        terms_list = [term.strip() for term in state.search_terms.split(',')]
        escaped_terms = [escape_sosl_term(term) for term in terms_list]
        formatted_terms = [f'"{term}"' if ' ' in term else term for term in escaped_terms]
        sosl_search_term = " OR ".join(formatted_terms)
        sosl_query = f"FIND {{{sosl_search_term}}} IN ALL FIELDS RETURNING Knowledge__kav(Id, Title, FAQ_Answer__c WHERE PublishStatus='Online' AND Language='en_US')"
        print(sosl_query)
        raw_result = SOSLQueryTool()._run(sosl_query)
        print(raw_result)
        try:
            search_records = raw_result.get("searchRecords", [])
            articles = [
                {
                    "Id": str(record.get("Id", "")),
                    "Title": str(record.get("Title", "")),
                    "FAQ_Answer__c": str(record.get("FAQ_Answer__c", ""))
                }
                for record in search_records
            ]
            print(articles)
            return QAState(
                query_text=state.query_text,
                search_terms=state.search_terms,
                articles=articles,
                sosl_query=sosl_query,
                article_count=len(articles)
            )
        except Exception as e:
            print(f"DEBUG: Error in execute_sosl_query: {str(e)}")
            return QAState(query_text=state.query_text, error=f"Article Search Error: {str(e)}")
    except Exception as e:
        return QAState(query_text=state.query_text, error=f"Article Search Error: {str(e)}")

def extract_answer_node(state: QAState) -> QAState:
    if state.error or not state.articles:
        print(f"DEBUG: Error in extract_answer_node: {state.error}")
        return QAState(
            query_text=state.query_text,
            search_terms=state.search_terms,
            articles=state.articles,
            answer="No relevant information found",
            article_count=0,
            sosl_query=state.sosl_query
        )
    try:
        answer = extract_answer(state.query_text, state.articles)
        return QAState(
            query_text=state.query_text,
            search_terms=state.search_terms,
            articles=state.articles,
            answer=answer,
            article_count=len(state.articles),
            sosl_query=state.sosl_query
        )
    except Exception as e:
        print(f"DEBUG: Error in extract_answer_node: {str(e)}")
        return QAState(
            query_text=state.query_text,
            error=f"Answer Extraction Error: {str(e)}",
            sosl_query=state.sosl_query
        )

# Workflow
qa_workflow = StateGraph(QAState)
qa_workflow.add_node("extract_terms", extract_terms_node)
qa_workflow.add_node("search_articles", search_articles_node)
qa_workflow.add_node("extract_answer", extract_answer_node)
qa_workflow.add_edge("extract_terms", "search_articles")
qa_workflow.add_edge("search_articles", "extract_answer")
qa_workflow.add_edge("extract_answer", END)
qa_workflow.set_entry_point("extract_terms")
qa_app = qa_workflow.compile()