from langgraph.graph import StateGraph, END
from langchain.prompts import PromptTemplate
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from pydantic import BaseModel, Field
from typing import Dict, Optional
from .kqa_workflow import qa_app, QAState
from .ned_workflow import ned_app, NEDState
from .llm import llm
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# State Definition
class HybridState(BaseModel):
    query_text: str
    query_type: str = ""
    result: str = ""
    error: str = ""
    prompt: str = ""
    metadata: Optional[Dict] = None  # Store metadata in state

# Nodes
def classify_query_node(state: HybridState) -> HybridState:
    try:
        query_text = state.query_text
        response_schemas = [
            ResponseSchema(name="query_type", description="Type of query: 'knowledge_qa' or 'named_entity_disambiguation'", type="string")
        ]
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
        logger.info(f"Classified query '{query_text}' as {result['query_type']}")
        return HybridState(
            query_text=query_text,
            query_type=result["query_type"],
            metadata=state.metadata
        )
    except Exception as e:
        logger.error(f"Error classifying query: {str(e)}")
        return HybridState(query_text=state.query_text, error=f"Classification error: {str(e)}", metadata=state.metadata)

def check_metadata_node(state: HybridState) -> HybridState:
    if state.query_type == "named_entity_disambiguation":
        metadata = state.metadata or {}
        logger.info(f"Checking metadata for NED query: {metadata}")

        # Extract and clean metadata
        contact_id = str(metadata.get("contact_id", "")).strip()
        today_date = str(metadata.get("today's_date", "")).strip()

        # Validate formats
        contact_id_valid = bool(contact_id and re.match(r'^003[a-zA-Z0-9]{15}$', contact_id))
        date_valid = bool(today_date and re.match(r'^\d{4}-\d{2}-\d{2}$', today_date))

        if not (contact_id_valid and date_valid):
            prompt = "Please provide the following information:\n- contact_id: (e.g., 003Ws000004Fo3qIAC)\n- today's_date: (e.g., 2020-06-15)"
            logger.warning(f"Metadata validation failed: contact_id='{contact_id}', contact_id_valid={contact_id_valid}, today_date='{today_date}', date_valid={date_valid}")
            return HybridState(
                query_text=state.query_text,
                query_type=state.query_type,
                prompt=prompt,
                error="Missing or invalid metadata",
                metadata=state.metadata
            )
        logger.info(f"Metadata validated: contact_id={contact_id}, today_date={today_date}")
    else:
        logger.info(f"No metadata required for query_type: {state.query_type}")
    return state

def knowledge_qa_node(state: HybridState) -> HybridState:
    try:
        logger.info(f"Processing KQA query: {state.query_text}")
        qa_state = QAState(query_text=state.query_text)
        final_qa_state = qa_app.invoke(qa_state)
        result = final_qa_state['answer'] or "No specific data found, but typical products may include standard features relevant to the query."
        error = final_qa_state['error']
        logger.info(f"KQA result: answer='{result}', error='{error}'")
        return HybridState(
            query_text=state.query_text,
            query_type=state.query_type,
            result=result,
            error=error,
            metadata=state.metadata
        )
    except Exception as e:
        logger.error(f"KQA error: {str(e)}")
        return HybridState(
            query_text=state.query_text,
            query_type=state.query_type,
            result="",
            error=f"KQA processing error: {str(e)}",
            metadata=state.metadata
        )

def named_entity_disambiguation_node(state: HybridState) -> HybridState:
    try:
        metadata = state.metadata or {}
        contact_id = str(metadata.get("contact_id", "")).strip()
        today_date = str(metadata.get("today's_date", "")).strip()
        logger.info(f"Processing NED query: {state.query_text}, metadata: contact_id='{contact_id}', today_date='{today_date}'")

        # Re-validate metadata
        if not (re.match(r'^003[a-zA-Z0-9]{15}$', contact_id) and re.match(r'^\d{4}-\d{2}-\d{2}$', today_date)):
            logger.error(f"Invalid metadata in NED node: contact_id='{contact_id}', today_date='{today_date}'")
            return HybridState(
                query_text=state.query_text,
                query_type=state.query_type,
                error="Invalid metadata format",
                metadata=state.metadata
            )

        ned_state = NEDState(query_text=state.query_text, contact_id=contact_id, today_date=today_date)
        final_ned_state = ned_app.invoke(ned_state)
        result = final_ned_state['product_id'] if not final_ned_state['error'] else "None"
        error = final_ned_state['error']
        logger.info(f"NED result: product_id='{result}', error='{error}'")
        return HybridState(
            query_text=state.query_text,
            query_type=state.query_type,
            result=result,
            error=error,
            metadata=state.metadata
        )
    except Exception as e:
        logger.error(f"NED error: {str(e)}")
        return HybridState(
            query_text=state.query_text,
            query_type=state.query_type,
            result="",
            error=f"NED processing error: {str(e)}",
            metadata=state.metadata
        )

# Routing Function
def route_query_type(state: HybridState) -> str:
    if state.error or state.prompt:
        logger.info(f"Routing to END due to error='{state.error}' or prompt='{state.prompt}'")
        return END
    if state.query_type == "knowledge_qa":
        return "knowledge_qa"
    elif state.query_type == "named_entity_disambiguation":
        return "named_entity_disambiguation"
    logger.warning(f"Unknown query_type: {state.query_type}")
    return END

# Initial Workflow
initial_workflow = StateGraph(HybridState)
initial_workflow.add_node("classify_query", classify_query_node)
initial_workflow.add_node("check_metadata", check_metadata_node)
initial_workflow.add_edge("classify_query", "check_metadata")
initial_workflow.add_edge("check_metadata", END)
initial_workflow.set_entry_point("classify_query")
initial_app = initial_workflow.compile()

# Main Workflow
main_workflow = StateGraph(HybridState)
main_workflow.add_node("knowledge_qa", knowledge_qa_node)
main_workflow.add_node("named_entity_disambiguation", named_entity_disambiguation_node)
main_workflow.add_conditional_edges(
    "__start__",
    route_query_type,
    {
        "knowledge_qa": "knowledge_qa",
        "named_entity_disambiguation": "named_entity_disambiguation",
        END: END
    }
)
main_workflow.add_edge("knowledge_qa", END)
main_workflow.add_edge("named_entity_disambiguation", END)
main_workflow.set_entry_point("knowledge_qa")
main_app = main_workflow.compile()

# Entry Points
def process_initial_query(query_input: str, metadata: Optional[Dict] = None) -> Dict:
    query_text = query_input.strip()
    logger.info(f"Initial query: query='{query_text}', metadata={metadata}")
    initial_state = HybridState(query_text=query_text, metadata=metadata)
    final_state = initial_app.invoke(initial_state)
    if final_state['prompt']:
        logger.info(f"Prompt returned: {final_state['prompt']}")
        return {"prompt": final_state['prompt'], "query_type": final_state['query_type'], "error": final_state['error']}
    logger.info(f"Query classified: query_type={final_state['query_type']}")
    return {"query_type": final_state['query_type'], "error": final_state['error']}

def process_query(query_input: str, metadata: Optional[Dict] = None, query_type: Optional[str] = None) -> Dict:
    query_text = query_input.strip()
    logger.info(f"Processing query: query='{query_text}', metadata={metadata}, query_type={query_type}")
    if not query_type:
        initial_result = process_initial_query(query_input, metadata)
        if initial_result.get('prompt'):
            return {"error": initial_result['prompt'], "result": None}
        query_type = initial_result['query_type']

    initial_state = HybridState(query_text=query_text, query_type=query_type, metadata=metadata)
    final_state = main_app.invoke(initial_state)
    logger.info(f"Query result: result='{final_state['result']}', error='{final_state['error']}'")
    return {"result": final_state['result'], "error": final_state['error'] or None}