from langgraph.graph import StateGraph, END
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from datetime import datetime, timedelta
import re
from pydantic import BaseModel, Field
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.prompts import PromptTemplate
from typing import Type, Dict, List, Any
from .salesforce import sf_client
from .llm import llm

# Tools
class SOSLQueryInput(BaseModel):
    query: str = Field(..., description="A dynamically generated SOSL query.")

class SOSLQueryTool(BaseTool):
    name: str = "SOSL Query Tool"
    description: str = "Executes a SOSL query against Salesforce."
    args_schema: Type[BaseModel] = SOSLQueryInput

    def _run(self, query: str) -> str:
        try:
            result = sf_client.search(query)
            return result
        except Exception as e:
            return f"Error: {str(e)}"

sosl_tool = SOSLQueryTool()
llm_with_sosl_tools = llm.bind_tools([sosl_tool])

class SOQLQueryInput(BaseModel):
    query: str = Field(..., description="A dynamically generated SOQL query.")

class SOQLQueryTool(BaseTool):
    name: str = "SOQL Query Tool"
    description: str = "Executes a SOQL query against Salesforce."
    args_schema: Type[BaseModel] = SOQLQueryInput

    def _run(self, query: str) -> str:
        try:
            result = sf_client.query_all(query)
            return result['records']
        except Exception as e:
            return f"Error: {str(e)}"

soql_tool = SOQLQueryTool()
llm_with_soql_tools = llm.bind_tools([soql_tool])

# State Definitions
class HybridState(BaseModel):
    query: Dict[str, Any]
    query_text: str
    query_type: str = ""
    result: str = ""
    error: str = ""
    prompt: str = ""

class QAState(BaseModel):
    query: Dict[str, Any]
    query_text: str
    search_terms: str = ""
    articles: List[Dict[str, str]] = []
    answer: str = ""
    error: str = ""

class NEDState(BaseModel):
    query_data: Dict[str, Any]
    contact_id: str = ""
    product_name: str = ""
    effective_date: str = ""
    account_id: str = ""
    order_items: List[Dict[str, Any]] = []
    product_id: str = ""
    error: str = ""

# Helper Functions for Knowledge QA Workflow
def extract_search_terms(query_text: str) -> str:
    search_terms_prompt = PromptTemplate(
        template="""
        Extract key terms from the query for a Salesforce SOSL search: "{query_text}"
        Return ONLY a comma-separated string of terms, nothing else.
        Example format: term1, term2, term3
        """,
        input_variables=["query_text"]
    )
    chain = search_terms_prompt | llm
    result = chain.invoke({"query_text": query_text})
    # Extract content from AIMessage object
    terms = result.content.strip()
    # Remove any JSON formatting or extra text
    terms = terms.replace('```json', '').replace('```', '').strip()
    # If the response is still in JSON format, try to parse it
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
    terms_list = [term.strip() for term in search_terms.split(",")]
    escaped_terms = [escape_sosl_term(term) for term in terms_list]
    formatted_terms = [f'"{term}"' if " " in term else term for term in escaped_terms]
    sosl_search_term = " OR ".join(formatted_terms)
    sosl_query = f"FIND {{{sosl_search_term}}} IN ALL FIELDS RETURNING Knowledge__kav(Id, Title, FAQ_Answer__c WHERE PublishStatus='Online' AND Language='en_US')"
    print(sosl_query)
    raw_result = sosl_tool._run(sosl_query)
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
        Extract a concise answer, focusing on FAQ_Answer__c. If no relevant info, return "No relevant information found."
        {format_instructions}
        """,
        input_variables=["query", "articles"],
        partial_variables={"format_instructions": StructuredOutputParser.from_response_schemas([
            ResponseSchema(name="answer", description="A concise answer to the query.", type="string")
        ]).get_format_instructions()}
    )
    articles_str = "\n".join([f"Title: {a['Title']}\nFAQ_Answer__c: {a.get('FAQ_Answer__c', 'N/A')}" for a in articles])
    chain = answer_prompt | llm | StructuredOutputParser.from_response_schemas([
        ResponseSchema(name="answer", description="A concise answer to the query.", type="string")
    ])
    result = chain.invoke({"query": query, "articles": articles_str})
    print(result)
    return result["answer"]

def extract_terms_node(state: QAState) -> QAState:
    try:
        query_text = state.query.get("query", "")
        search_terms = extract_search_terms(query_text)
        print(search_terms)
        return QAState(query=state.query, query_text=query_text, search_terms=search_terms)
    except Exception as e:
        print(f"DEBUG: Error in extract_terms_node: {str(e)}")
        return QAState(query=state.query, query_text=state.query_text, error=f"Search Terms Extraction Error: {str(e)}")

def search_articles_node(state: QAState) -> QAState:
    if state.error:
        print(f"DEBUG: Error in search_articles_node: {state.error}")
        return state
    try:
        articles = execute_sosl_query(state.search_terms)
        return QAState(query=state.query, query_text=state.query_text, search_terms=state.search_terms, articles=articles)
    except Exception as e:
        return QAState(query=state.query, query_text=state.query_text, error=f"Article Search Error: {str(e)}")

def extract_answer_node(state: QAState) -> QAState:
    if state.error or not state.articles:
        print(f"DEBUG: Error in extract_answer_node: {state.error}")
        return QAState(query=state.query, query_text=state.query_text, search_terms=state.search_terms, articles=state.articles, answer="No relevant information found")
    try:
        query_str = state.query.get("query", "")
        answer = extract_answer(query_str, state.articles)
        return QAState(query=state.query, query_text=state.query_text, search_terms=state.search_terms, articles=state.articles, answer=answer)
    except Exception as e:
        print(f"DEBUG: Error in extract_answer_node: {str(e)}")
        return QAState(query=state.query, query_text=state.query_text, error=f"Answer Extraction Error: {str(e)}")

qa_workflow = StateGraph(QAState)
qa_workflow.add_node("extract_terms", extract_terms_node)
qa_workflow.add_node("search_articles", search_articles_node)
qa_workflow.add_node("extract_answer", extract_answer_node)
qa_workflow.add_edge("extract_terms", "search_articles")
qa_workflow.add_edge("search_articles", "extract_answer")
qa_workflow.add_edge("extract_answer", END)
qa_workflow.set_entry_point("extract_terms")
qa_app = qa_workflow.compile()

# Helper Functions for Named Entity Disambiguation Workflow
def query_parsing_node(state: NEDState) -> NEDState:
    try:
        query_data = state.query_data
        contact_id = query_data['metadata']['required'].split('Contact Id interacting: ')[1].split('\n')[0]
        today_date = query_data['metadata']['required'].split("Today's date: ")[1]
        query_text = query_data['query']

        response_schemas = [
            ResponseSchema(name="product_name", description="The name of the product purchased.", type="string"),
            ResponseSchema(name="days", description="Days before today the purchase was made.", type="integer")
        ]
        output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
        prompt = PromptTemplate(
            template="""
            Extract from the query: "{query_text}"
            1. Product name.
            2. Days before today the purchase was made.
            {format_instructions}
            """,
            input_variables=["query_text"],
            partial_variables={"format_instructions": output_parser.get_format_instructions()}
        )
        chain = prompt | llm | output_parser
        extracted_data = chain.invoke({"query_text": query_text})
        product_name = extracted_data.get('product_name', 'Unknown Product')
        days = extracted_data.get('days', 7)

        if not isinstance(days, int) or days < 0:
            days = 7
        if not product_name or not isinstance(product_name, str):
            product_name = 'Unknown Product'

        today = datetime.strptime(today_date, '%Y-%m-%d')
        effective_date = (today - timedelta(days=days)).strftime('%Y-%m-%d')

        return NEDState(
            query_data=state.query_data,
            contact_id=contact_id,
            product_name=product_name,
            effective_date=effective_date
        )
    except Exception as e:
        return NEDState(error=f"Query Parsing Error: {str(e)}")

def account_retrieval_node(state: NEDState) -> NEDState:
    if state.error:
        return state
    try:
        contact_id = state.contact_id
        query = f"SELECT AccountId FROM Contact WHERE Id = '{contact_id}'"
        result = soql_tool._run(query)
        account_id = result[0].get("AccountId", "None") if isinstance(result, list) and result else "None"
        return NEDState(
            query_data=state.query_data,
            contact_id=state.contact_id,
            product_name=state.product_name,
            effective_date=state.effective_date,
            account_id=account_id
        )
    except Exception as e:
        return NEDState(error=f"Account Retrieval Error: {str(e)}")

def orderitem_retrieval_node(state: NEDState) -> NEDState:
    if state.error or state.account_id == "None":
        return NEDState(
            query_data=state.query_data,
            contact_id=state.contact_id,
            product_name=state.product_name,
            effective_date=state.effective_date,
            account_id=state.account_id,
            order_items=[]
        )
    try:
        account_id = state.account_id
        effective_date = state.effective_date
        query = f"""
            SELECT Product2Id, Product2.Name
            FROM OrderItem
            WHERE Order.AccountId = '{account_id}'
            AND Order.EffectiveDate >= {effective_date}
            LIMIT 10
        """
        result = soql_tool._run(query)
        order_items = [
            {"Product2Id": r["Product2Id"], "Product2.Name": r["Product2"]["Name"]}
            for r in result if "Product2Id" in r and "Product2" in r and "Name" in r["Product2"]
        ]
        return NEDState(
            query_data=state.query_data,
            contact_id=state.contact_id,
            product_name=state.product_name,
            effective_date=state.effective_date,
            account_id=state.account_id,
            order_items=order_items
        )
    except Exception as e:
        return NEDState(error=f"OrderItem Retrieval Error: {str(e)}")

def product_matching_node(state: NEDState) -> NEDState:
    if state.error or not state.order_items or state.product_name == "Unknown Product":
        return NEDState(
            query_data=state.query_data,
            contact_id=state.contact_id,
            product_name=state.product_name,
            effective_date=state.effective_date,
            account_id=state.account_id,
            order_items=state.order_items,
            product_id="None"
        )
    try:
        product_name = state.product_name.lower()
        order_items = state.order_items
        for item in order_items:
            if item["Product2.Name"].lower() == product_name:
                return NEDState(
                    query_data=state.query_data,
                    contact_id=state.contact_id,
                    product_name=state.product_name,
                    effective_date=state.effective_date,
                    account_id=state.account_id,
                    order_items=state.order_items,
                    product_id=item["Product2Id"]
                )
        product_words = set(product_name.split())
        for item in order_items:
            item_name = item["Product2.Name"].lower()
            item_words = set(item_name.split())
            common_words = product_words.intersection(item_words)
            if len(common_words) >= 2:
                return NEDState(
                    query_data=state.query_data,
                    contact_id=state.contact_id,
                    product_name=state.product_name,
                    effective_date=state.effective_date,
                    account_id=state.account_id,
                    order_items=state.order_items,
                    product_id=item["Product2Id"]
                )
        return NEDState(
            query_data=state.query_data,
            contact_id=state.contact_id,
            product_name=state.product_name,
            effective_date=state.effective_date,
            account_id=state.account_id,
            order_items=state.order_items,
            product_id="None"
        )
    except Exception as e:
        return NEDState(error=f"Product Matching Error: {str(e)}")

ned_workflow = StateGraph(NEDState)
ned_workflow.add_node("query_parsing", query_parsing_node)
ned_workflow.add_node("account_retrieval", account_retrieval_node)
ned_workflow.add_node("orderitem_retrieval", orderitem_retrieval_node)
ned_workflow.add_node("product_matching", product_matching_node)
ned_workflow.add_edge("query_parsing", "account_retrieval")
ned_workflow.add_edge("account_retrieval", "orderitem_retrieval")
ned_workflow.add_edge("orderitem_retrieval", "product_matching")
ned_workflow.add_edge("product_matching", END)
ned_workflow.set_entry_point("query_parsing")
ned_app = ned_workflow.compile()

# Workflow Logic
def classify_query_node(state: HybridState) -> HybridState:
    try:
        query_text = state.query.get("query", "")
        response_schemas = [ResponseSchema(name="query_type", description="Type of query: 'knowledge_qa' or 'named_entity_disambiguation'", type="string")]
        parser = StructuredOutputParser.from_response_schemas(response_schemas)
        prompt = PromptTemplate(
            template="""
            Classify query: "{query_text}" as 'knowledge_qa' or 'named_entity_disambiguation'.
            - 'knowledge_qa': Queries asking for general information (e.g., "What technology features do Shoes & Clothings golf shoes have?").
            - 'named_entity_disambiguation': Queries asking for past purchase details (e.g., "Can you display the women's trail jacket I purchased a fortnight ago?").
            {format_instructions}
            """,
            input_variables=["query_text"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )
        chain = prompt | llm | parser
        result = chain.invoke({"query_text": query_text})
        return HybridState(query=state.query, query_text=query_text, query_type=result["query_type"])
    except Exception as e:
        return HybridState(query=state.query, query_text=state.query_text, error=f"Error: {str(e)}")

def check_metadata_node(state: HybridState) -> HybridState:
    if state.query_type == "named_entity_disambiguation":
        metadata = state.query.get("metadata", {}).get("required", "")
        contact_id_present = "Contact Id interacting:" in metadata
        date_present = "Today's date:" in metadata
        if not (contact_id_present and date_present):
            prompt = "Please provide the following information:\n- Contact Id interacting: (e.g., 003Ws000004Fo3qIAC)\n- Today's date: (e.g., 2020-06-15)"
            return HybridState(
                query=state.query,
                query_text=state.query_text,
                query_type=state.query_type,
                prompt=prompt
            )
    return state

def knowledge_qa_node(state: HybridState) -> HybridState:
    try:
        qa_state = QAState(query=state.query, query_text=state.query_text)
        final_qa_state = qa_app.invoke(qa_state)
        return HybridState(
            query=state.query,
            query_text=state.query_text,
            query_type=state.query_type,
            result=final_qa_state['answer'],
            error=final_qa_state['error']
        )
    except Exception as e:
        return HybridState(query=state.query, query_text=state.query_text, query_type=state.query_type, error=f"Knowledge QA Error: {str(e)}")

def named_entity_disambiguation_node(state: HybridState) -> HybridState:
    try:
        ned_state = NEDState(query_data=state.query)
        final_ned_state = ned_app.invoke(ned_state)
        return HybridState(
            query=state.query,
            query_text=state.query_text,
            query_type=state.query_type,
            result=final_ned_state['product_id'] if not final_ned_state['error'] else "None",
            error=final_ned_state['error']
        )
    except Exception as e:
        return HybridState(query=state.query, query_text=state.query_text, query_type=state.query_type, error=f"Named Entity Disambiguation Error: {str(e)}")

# Routing Function for Conditional Edges
def route_query_type(state: HybridState) -> str:
    if state.query_type == "knowledge_qa":
        return "knowledge_qa"
    elif state.query_type == "named_entity_disambiguation":
        return "named_entity_disambiguation"
    return END

# Initial Workflow to Classify and Check Metadata
initial_workflow = StateGraph(HybridState)
initial_workflow.add_node("classify_query", classify_query_node)
initial_workflow.add_node("check_metadata", check_metadata_node)
initial_workflow.add_edge("classify_query", "check_metadata")
initial_workflow.add_edge("check_metadata", END)
initial_workflow.set_entry_point("classify_query")
initial_app = initial_workflow.compile()

# Main Workflow for Full Processing
main_workflow = StateGraph(HybridState)
main_workflow.add_node("classify_query", classify_query_node)
main_workflow.add_node("knowledge_qa", knowledge_qa_node)
main_workflow.add_node("named_entity_disambiguation", named_entity_disambiguation_node)
# Use add_conditional_edges instead of add_edge with condition
main_workflow.add_conditional_edges(
    "classify_query",
    route_query_type,
    {
        "knowledge_qa": "knowledge_qa",
        "named_entity_disambiguation": "named_entity_disambiguation",
        END: END
    }
)
main_workflow.add_edge("knowledge_qa", END)
main_workflow.add_edge("named_entity_disambiguation", END)
main_workflow.set_entry_point("classify_query")
main_app = main_workflow.compile()

def process_initial_query(query_data: Dict) -> Dict:
    initial_state = HybridState(query=query_data, query_text=query_data.get("query", ""))
    final_state = initial_app.invoke(initial_state)
    if final_state['prompt']:
        return {"prompt": final_state['prompt'], "query_type": final_state['query_type']}
    return {}

def process_query(query_data: Dict) -> Dict:
    initial_state = HybridState(query=query_data, query_text=query_data.get("query", ""))
    final_state = main_app.invoke(initial_state)
    return {"result": final_state['result'], "error": final_state['error']} if final_state['error'] else {"result": final_state['result']}