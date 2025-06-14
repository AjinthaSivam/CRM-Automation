from langgraph.graph import StateGraph, END
from langchain.prompts import PromptTemplate
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from pydantic import BaseModel, Field
from typing import Dict, List, Any
from .tools import SOQLQueryTool
from .llm import llm
from datetime import datetime, timedelta

# State Definition
class NEDState(BaseModel):
    query_text: str = ""
    contact_id: str = ""
    product_name: str = ""
    today_date: str = ""
    effective_date: str = ""
    account_id: str = ""
    order_items: List[Dict[str, Any]] = []
    product_id: str = ""
    error: str = ""
    node_outputs: List[Dict[str, Any]] = []

def call_llm_for_semantic_match(product_name: str, unique_products: List[Dict[str, str]]) -> Dict[str, Any]:
    response_schemas = [
        ResponseSchema(name="product_id", description="The ID of the most semantically similar product", type="string"),
        ResponseSchema(name="product_name", description="The name of the most semantically similar product", type="string"),
        ResponseSchema(name="match_type", description="Type of match: 'semantic'", type="string"),
        ResponseSchema(name="reason", description="Explanation of why this product was chosen", type="string")
    ]
    output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
    
    products_str = "\n".join([f"- {p['Product2.Name']} (ID: {p['Product2Id']})" for p in unique_products])
    
    prompt = PromptTemplate(
        template="""
        You are a product matching assistant. Given a user-provided product name and a list of available products, identify the product that is most semantically similar to the user's input. Do NOT generate a database query, SOQL query, or function call.

        **Matching Instructions**:
        1. Prioritize matching the product type (e.g., jacket, shoes, shirt, helmet) over contextual terms (e.g., 'trail', 'yoga').
        2. Only match products if their type aligns with the user's input (e.g., a jacket should not match shoes).
        3. Consider synonyms and attributes (e.g., 'fast-drying' ≈ 'quick-dry') only after confirming the product type.
        4. If no product of the correct type is found, return 'null' for product_id with a clear reason.
        5. Provide a detailed reason explaining why the product type and attributes match or why no match was found.

        User product name: "{product_name}"
        Available products: {products_str}

        Return a JSON object adhering to the following schema:
        {{
            "product_id": "string | null",
            "product_name": "string",
            "match_type": "semantic | none",
            "reason": "string"
        }}

        Examples:
        - User: "tennis shoes" → Product: "Classic Court Sneakers"
          Output: {{"product_id": "prod123", "product_name": "Classic Court Sneakers", "match_type": "semantic", "reason": "Both are shoes for tennis; 'shoes' matches 'sneakers'."}}
        - User: "fast-drying athletic shirt" → Product: "Women's Quick-Dry Sports Top"
          Output: {{"product_id": "prod456", "product_name": "Women's Quick-Dry Sports Top", "match_type": "semantic", "reason": "Both are tops/shirts; 'fast-drying' is synonymous with 'quick-dry'."}}
        - User: "breathable yoga top" → Product: "All-Around Yoga Tank"
          Output: {{"product_id": "prod789", "product_name": "All-Around Yoga Tank", "match_type": "semantic", "reason": "Both are tops for yoga; 'top' is similar to 'tank'."}}
        - User: "women's trail jacket" → Product: "Women's All-Weather Trail Jacket"
          Output: {{"product_id": "prod101", "product_name": "Women's All-Weather Trail Jacket", "match_type": "semantic", "reason": "Both are jackets for outdoor activities; 'trail' indicates the context."}}
        - User: "women's trail jacket" → Product: "Trail Running Shoes" (Incorrect)
          Output: {{"product_id": "null", "product_name": "", "match_type": "none", "reason": "No match found; 'jacket' is a different product type from 'shoes', despite sharing 'trail' context."}}

        {format_instructions}
        """,
        input_variables=["product_name", "products_str"],
        partial_variables={"format_instructions": output_parser.get_format_instructions()}
    )
    
    chain = prompt | llm | output_parser
    return chain.invoke({
        "product_name": product_name,
        "products_str": products_str
    })

# Helper Functions
def query_parsing_node(state: NEDState) -> NEDState:
    try:
        query_text = state.query_text
        contact_id = state.contact_id
        today_date = state.today_date

        if not contact_id or not today_date:
            return NEDState(
                query_text=query_text,
                error="Missing contact_id or today_date"
            )

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
            query_text=query_text,
            contact_id=contact_id,
            product_name=product_name,
            today_date=today_date,
            effective_date=effective_date
        )
    except Exception as e:
        return NEDState(query_text=query_text, error=f"Query Parsing Error: {str(e)}")

def account_retrieval_node(state: NEDState) -> NEDState:
    if state.error:
        return state
    try:
        contact_id = state.contact_id
        query = f"SELECT AccountId FROM Contact WHERE Id = '{contact_id}'"
        result = SOQLQueryTool()._run(query)
        account_id = result[0].get("AccountId", "None") if isinstance(result, list) and result else "None"
        return NEDState(
            query_text=state.query_text,
            contact_id=state.contact_id,
            product_name=state.product_name,
            today_date=state.today_date,
            effective_date=state.effective_date,
            account_id=account_id
        )
    except Exception as e:
        return NEDState(query_text=state.query_text, error=f"Account Retrieval Error: {str(e)}")

def orderitem_retrieval_node(state: NEDState) -> NEDState:
    if state.error or state.account_id == "None":
        return NEDState(
            query_text=state.query_text,
            contact_id=state.contact_id,
            product_name=state.product_name,
            today_date=state.today_date,
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
        result = SOQLQueryTool()._run(query)
        order_items = [
            {"Product2Id": r["Product2Id"], "Product2.Name": r["Product2"]["Name"]}
            for r in result if "Product2Id" in r and "Product2" in r and "Name" in r["Product2"]
        ]
        return NEDState(
            query_text=state.query_text,
            contact_id=state.contact_id,
            product_name=state.product_name,
            today_date=state.today_date,
            effective_date=state.effective_date,
            account_id=state.account_id,
            order_items=order_items
        )
    except Exception as e:
        return NEDState(query_text=state.query_text, error=f"OrderItem Retrieval Error: {str(e)}")

def product_matching_node(state: NEDState) -> NEDState:
    if state.error or not state.order_items or state.product_name == "Unknown Product":
        node_output = {"product_id": "None", "reason": "No valid inputs"}
        node_outputs = state.node_outputs + [{"node": "product_matching", "output": node_output}]
        return NEDState(
            query_text=state.query_text,
            contact_id=state.contact_id,
            product_name=state.product_name,
            today_date=state.today_date,
            effective_date=state.effective_date,
            account_id=state.account_id,
            order_items=state.order_items,
            product_id="None",
            node_outputs=node_outputs
        )

    try:
        product_name = state.product_name.lower()
        order_items = state.order_items

        # Step 1: Exact match
        for item in order_items:
            if item["Product2.Name"].lower() == product_name:
                node_output = {
                    "product_id": item["Product2Id"],
                    "product_name": item["Product2.Name"],
                    "match_type": "exact",
                    "reason": "Exact match found"
                }
                node_outputs = state.node_outputs + [{"node": "product_matching", "output": node_output}]
                return NEDState(
                    query_text=state.query_text,
                    contact_id=state.contact_id,
                    product_name=state.product_name,
                    today_date=state.today_date,
                    effective_date=state.effective_date,
                    account_id=state.account_id,
                    order_items=state.order_items,
                    product_id=item["Product2Id"],
                    node_outputs=node_outputs
                )

        # Step 2: Partial match
        product_words = set(product_name.split())
        for item in order_items:
            item_name = item["Product2.Name"].lower()
            item_words = set(item_name.split())
            common_words = product_words.intersection(item_words)
            if len(common_words) >= 3:
                node_output = {
                    "product_id": item["Product2Id"],
                    "product_name": item["Product2.Name"],
                    "match_type": "partial",
                    "reason": f"Partial match with common words: {common_words}"
                }
                node_outputs = state.node_outputs + [{"node": "product_matching", "output": node_output}]
                return NEDState(
                    query_text=state.query_text,
                    contact_id=state.contact_id,
                    product_name=state.product_name,
                    today_date=state.today_date,
                    effective_date=state.effective_date,
                    account_id=state.account_id,
                    order_items=state.order_items,
                    product_id=item["Product2Id"],
                    node_outputs=node_outputs
                )

        # Step 3: LLM-based semantic match
        # Extract distinct product names and IDs
        product_list = [
            {"Product2Id": item["Product2Id"], "Product2.Name": item["Product2.Name"]}
            for item in order_items
        ]
        # Remove duplicates while preserving order
        seen = set()
        unique_products = [
            item for item in product_list
            if not (item["Product2.Name"] in seen or seen.add(item["Product2.Name"]))
        ]

        # Call LLM with structured output
        llm_response = call_llm_for_semantic_match(product_name, unique_products)
        if not llm_response:
            raise Exception("LLM call failed or returned no response")

        # Process LLM response
        node_output = {
            "product_id": llm_response.get("product_id", "null"),
            "product_name": llm_response.get("product_name", ""),
            "match_type": llm_response.get("match_type", "none"),
            "reason": llm_response.get("reason", "No match found")
        }
        node_outputs = state.node_outputs + [{"node": "product_matching", "output": node_output}]

        product_id = llm_response.get("product_id", "None")
        if product_id is None or product_id == "null":
            product_id = "None"

        return NEDState(
            query_text=state.query_text,
            contact_id=state.contact_id,
            product_name=state.product_name,
            today_date=state.today_date,
            effective_date=state.effective_date,
            account_id=state.account_id,
            order_items=state.order_items,
            product_id=product_id,
            node_outputs=node_outputs
        )

    except Exception as e:
        node_output = {"error": f"Product Matching Error: {str(e)}"}
        node_outputs = state.node_outputs + [{"node": "product_matching", "output": node_output}]
        return NEDState(
            query_text=state.query_text,
            contact_id=state.contact_id,
            product_name=state.product_name,
            today_date=state.today_date,
            effective_date=state.effective_date,
            account_id=state.account_id,
            order_items=state.order_items,
            product_id="None",
            error=f"Product Matching Error: {str(e)}",
            node_outputs=node_outputs
        )

# Workflow
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