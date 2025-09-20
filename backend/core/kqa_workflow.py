from langgraph.graph import StateGraph, END
from langchain.prompts import PromptTemplate
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from pydantic import BaseModel
from typing import List, Dict, Any
from .tools import SOSLQueryTool
from .llm import llm, get_llm
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
    node_outputs: List[Dict[str, Any]] = []
    model_name: str = "70b"

# Helper Functions
def extract_search_terms(query: str, model_name: str = "70b") -> str:
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
    current_llm = get_llm(model_name)
    chain = search_terms_prompt | current_llm
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

def extract_answer(query: str, articles: list, model_name: str = "70b") -> str:
    answer_prompt = PromptTemplate(
        template="""
        You are a Salesforce Knowledge Specialist tasked with answering a query based on Salesforce Knowledge articles. Your role is to extract a precise and concise answer directly from the FAQ_Answer__c field of the most relevant article. The query is: "{query}"
        Below are the relevant Knowledge articles retrieved: {articles}
        Instructions:
            - Extract the answer verbatim from the FAQ_Answer__c field of the article that best matches the query's focus (e.g., actions, time frames, or specific features), ensuring all key details are included without omissions.
            - If the FAQ_Answer__c field is unavailable or incomplete, provide a concise summary of the most relevant information from the article’s content, capturing only the essential points that address the query’s intent.
            - If multiple articles are relevant, select the one most closely aligned with the query’s specific focus.
            - Before returning "No relevant information found," thoroughly re-evaluate the provided articles to confirm no relevant information exists.
            - Should keep the answer exact, and aligned with the query’s intent, avoiding extraneous details or explanations.
            - Format the response as a JSON object with an "answer" key.
        {format_instructions}
        Examples:
        Query: "What technology features do Shoes & Clothings golf shoes have?"
        Answer: "Advanced sole technology and waterproof materials"

        Query: "If opting for store credit, within how many days from the purchase date must you request it?"
        Answer: "90 days"

        Query: "Can I get a full refund for damaged running shoes after 30 days?"
        Answer: "No, the request must be submitted within 30 days of the purchase date."

        Query: "{query}"
        """,
        input_variables=["query", "articles"],
        partial_variables={"format_instructions": StructuredOutputParser.from_response_schemas([
            ResponseSchema(name="answer", description="A concise answer to the query.", type="string"),
            ResponseSchema(name="article_count", description="Number of articles found for this query.", type="integer")
        ]).get_format_instructions()}
    )
    articles_str = "\n".join([f"Title: {a['Title']}\nFAQ_Answer__c: {a.get('FAQ_Answer__c', '')}" for a in articles])
    current_llm = get_llm(model_name)
    chain = answer_prompt | current_llm | StructuredOutputParser.from_response_schemas([
        ResponseSchema(name="answer", description="A concise answer to the query.", type="string")
    ])
    result = chain.invoke({"query": query, "articles": articles_str})
    print("result", result)
    return result["answer"]

# Nodes
def extract_terms_node(state: QAState) -> QAState:
    try:
        search_terms = extract_search_terms(state.query_text, state.model_name)
        print(search_terms)
        node_output = {"search_terms": search_terms, "model_used": state.model_name}
        node_outputs = state.node_outputs + [{"node": "extract_terms", "output": node_output}]
        return QAState(
            query_text=state.query_text, 
            search_terms=search_terms,
            model_name=state.model_name,
            node_outputs=node_outputs
        )
    except Exception as e:
        print(f"DEBUG: Error in extract_terms_node: {str(e)}")
        node_output = {"error": f"Search Terms Extraction Error: {str(e)}"}
        node_outputs = state.node_outputs + [{"node": "extract_terms", "output": node_output}]
        return QAState(
            query_text=state.query_text, 
            error=f"Search Terms Extraction Error: {str(e)}",
            model_name=state.model_name,
            node_outputs=node_outputs
        )

def search_articles_node(state: QAState) -> QAState:
    if state.error:
        print(f"DEBUG: Error in search_articles_node: {state.error}")
        node_output = {"error": state.error}
        node_outputs = state.node_outputs + [{"node": "search_articles", "output": node_output}]
        return QAState(
            query_text=state.query_text,
            search_terms=state.search_terms,
            articles=state.articles,
            sosl_query=state.sosl_query,
            article_count=state.article_count,
            error=state.error,
            model_name=state.model_name,
            node_outputs=node_outputs
        )
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
            node_output = {
                "sosl_query": sosl_query,
                "articles": articles,
                "article_count": len(articles),
                "model_used": state.model_name
            }
            node_outputs = state.node_outputs + [{"node": "search_articles", "output": node_output}]
            return QAState(
                query_text=state.query_text,
                search_terms=state.search_terms,
                articles=articles,
                sosl_query=sosl_query,
                article_count=len(articles),
                model_name=state.model_name,
                node_outputs=node_outputs
            )
        except Exception as e:
            print(f"DEBUG: Error in execute_sosl_query: {str(e)}")
            node_output = {"error": f"Article Search Error: {str(e)}"}
            node_outputs = state.node_outputs + [{"node": "search_articles", "output": node_output}]
            return QAState(
                query_text=state.query_text, 
                error=f"Article Search Error: {str(e)}",
                model_name=state.model_name,
                node_outputs=node_outputs
            )
    except Exception as e:
        node_output = {"error": f"Article Search Error: {str(e)}"}
        node_outputs = state.node_outputs + [{"node": "search_articles", "output": node_output}]
        return QAState(
            query_text=state.query_text, 
            error=f"Article Search Error: {str(e)}",
            model_name=state.model_name,
            node_outputs=node_outputs
        )

def extract_answer_node(state: QAState) -> QAState:
    if state.error or not state.articles:
        print(f"DEBUG: Error in extract_answer_node: {state.error}")
        node_output = {
            "answer": "No relevant information found",
            "article_count": 0,
            "error": state.error if state.error else "No articles found"
        }
        node_outputs = state.node_outputs + [{"node": "extract_answer", "output": node_output}]
        return QAState(
            query_text=state.query_text,
            search_terms=state.search_terms,
            articles=state.articles,
            answer="No relevant information found",
            article_count=0,
            sosl_query=state.sosl_query,
            error=state.error,
            model_name=state.model_name,
            node_outputs=node_outputs
        )
    try:
        answer = extract_answer(state.query_text, state.articles, state.model_name)
        node_output = {
            "answer": answer,
            "article_count": len(state.articles),
            "model_used": state.model_name
        }
        node_outputs = state.node_outputs + [{"node": "extract_answer", "output": node_output}]
        return QAState(
            query_text=state.query_text,
            search_terms=state.search_terms,
            articles=state.articles,
            answer=answer,
            article_count=len(state.articles),
            sosl_query=state.sosl_query,
            model_name=state.model_name,
            node_outputs=node_outputs
        )
    except Exception as e:
        print(f"DEBUG: Error in extract_answer_node: {str(e)}")
        node_output = {"error": f"Answer Extraction Error: {str(e)}"}
        node_outputs = state.node_outputs + [{"node": "extract_answer", "output": node_output}]
        return QAState(
            query_text=state.query_text,
            error=f"Answer Extraction Error: {str(e)}",
            sosl_query=state.sosl_query,
            model_name=state.model_name,
            node_outputs=node_outputs
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