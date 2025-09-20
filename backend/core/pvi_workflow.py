from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
from typing import List, Dict, Any
from .tools import SOQLQueryTool
from .llm import llm, get_llm
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PVIState(BaseModel):
    query_text: str = ""
    case_id: str = ""
    case_description: str = ""
    case_subject: str = ""
    case_subject_terms: List[str] = []
    knowledge_article_id: str = ""
    knowledge_article_title: str = ""
    error: str = ""
    node_outputs: List[Dict[str, Any]] = []
    model_name: str = "70b"
    
# Query all knowledge articles from Knowledge__kav
def fetch_knowledge_articles() -> List[Dict[str, str]]:
    query = "SELECT Id, Title, Summary FROM Knowledge__kav"
    try:
        result = SOQLQueryTool()._run(query)
        if isinstance(result, list):
            articles = [{"Id": record["Id"], "Title": record.get("Title", ""), "Summary": record.get("Summary", "")} for record in result]
            print(f"Fetched {len(articles)} knowledge articles")
            return articles
        else:
            print(f"Error fetching knowledge articles: Unexpected result format")
            return []
    except Exception as e:
        print(f"Error fetching knowledge articles: {str(e)}")
        return []
    
prompt = ChatPromptTemplate.from_template(
    """You are a Salesforce policy violation analyst. Your task is to analyze a case description and and match it to the most relevant knowledge article summary, based on the issue described.

    Case description: "{case_description}"
    
    Instructions:
    - Match the case to a knowledge article only if the summary addresses the same kind of issue (policy, process, or escalation).
    - For product issues (e.g., size mismatches, incorrect items), match to an article if it explicitly addresses solutions like exchanges, refunds, or replacements.
    - If no article covers the issue or the case is vague/general, return an empty string ("").
    - If multiple articles seem relevant, pick the most specific one.

    Knowledge article summaries:
    {article_summaries}

    Examples:
    - Case description: "The size chart on the website does not match the actual size of the Women's Running Tank Top."
      Expected output: "" (no policy violation, as this is a customer complaint about sizing without clear policy breach)
    - Case description: "I am unable to cancel my order online despite being within the cancellation window and would like assistance."
      Expected output: "ka0Ws000000QrlRIAS" (matches article "How to Handle Order Cancellation Issues with Shoes & Clothings")
    - Case description: "General inquiry about product availability."
      Expected output: "" (no policy violation, general inquiry)

    Return only the article ID or an empty string ("")."""
)

def case_retrieval_node(state: PVIState) -> PVIState:
    try:
        case_id = state.case_id
        soql_query = f"SELECT Description,IssueId__c,Subject FROM Case WHERE Id = '{case_id}'"

        soql_result = SOQLQueryTool()._run(soql_query)
        print(f"SOQL Result: {soql_result}")
        if isinstance(soql_result, list) and len(soql_result) > 0:
            record = soql_result[0]
            case_description = record.get('Description', '')
            case_subject = record.get('Subject', '')
            case_subject_terms = case_subject.split() if case_subject else []
            
            node_output = {
                "case_description": case_description,
                "case_subject": case_subject,
                "case_subject_terms": case_subject_terms,
                "soql_query": soql_query
            }
            node_outputs = state.node_outputs + [{"node": "case_retrieval", "output": node_output}]
            
            return PVIState(
                query_text=state.query_text,
                case_id=state.case_id,
                case_description=case_description,
                case_subject=case_subject,
                case_subject_terms=case_subject_terms,
                knowledge_article_id=state.knowledge_article_id,
                knowledge_article_title=state.knowledge_article_title,
                error=state.error,
                model_name=state.model_name,
                node_outputs=node_outputs
            )
        else:
            node_output = {"error": "No case found for the given ID"}
            node_outputs = state.node_outputs + [{"node": "case_retrieval", "output": node_output}]
            return PVIState(
                query_text=state.query_text,
                case_id=state.case_id,
                case_description=state.case_description,
                case_subject=state.case_subject,
                case_subject_terms=state.case_subject_terms,
                knowledge_article_id=state.knowledge_article_id,
                knowledge_article_title=state.knowledge_article_title,
                error="No case found for the given ID",
                model_name=state.model_name,
                node_outputs=node_outputs
            )

    except Exception as e:
        node_output = {"error": f"Error executing SOQL query: {str(e)}"}
        node_outputs = state.node_outputs + [{"node": "case_retrieval", "output": node_output}]
        return PVIState(
            query_text=state.query_text,
            case_id=state.case_id,
            case_description=state.case_description,
            case_subject=state.case_subject,
            case_subject_terms=state.case_subject_terms,
            knowledge_article_id=state.knowledge_article_id,
            knowledge_article_title=state.knowledge_article_title,
            error=f"Error executing SOQL query: {str(e)}",
            model_name=state.model_name,
            node_outputs=node_outputs
        )

def knowledge_article_retrieval_node(state: PVIState) -> PVIState:
  if state.error:
    print(f"Knowledge Article Node - Error: {state.error}")
    node_output = {"error": state.error}
    node_outputs = state.node_outputs + [{"node": "knowledge_article_retrieval", "output": node_output}]
    return PVIState(
        query_text=state.query_text,
        case_id=state.case_id,
        case_description=state.case_description,
        case_subject=state.case_subject,
        case_subject_terms=state.case_subject_terms,
        knowledge_article_id=state.knowledge_article_id,
        knowledge_article_title=state.knowledge_article_title,
        error=state.error,
        model_name=state.model_name,
        node_outputs=node_outputs
    )

  case_description = state.case_description
  print(f"Case Description: {case_description}")
  if not case_description:
      node_output = {"error": "no case description available"}
      node_outputs = state.node_outputs + [{"node": "knowledge_article_retrieval", "output": node_output}]
      return PVIState(
          query_text=state.query_text,
          case_id=state.case_id,
          case_description=state.case_description,
          case_subject=state.case_subject,
          case_subject_terms=state.case_subject_terms,
          knowledge_article_id=state.knowledge_article_id,
          knowledge_article_title=state.knowledge_article_title,
          error="no case description available",
          model_name=state.model_name,
          node_outputs=node_outputs
      )
  
  KNOWLEDGE_ARTICLES = fetch_knowledge_articles()

  if not KNOWLEDGE_ARTICLES:
      node_output = {"error": "no knowledge articles available"}
      node_outputs = state.node_outputs + [{"node": "knowledge_article_retrieval", "output": node_output}]
      return PVIState(
          query_text=state.query_text,
          case_id=state.case_id,
          case_description=state.case_description,
          case_subject=state.case_subject,
          case_subject_terms=state.case_subject_terms,
          knowledge_article_id=state.knowledge_article_id,
          knowledge_article_title=state.knowledge_article_title,
          error="no knowledge articles available",
          model_name=state.model_name,
          node_outputs=node_outputs
      )

  # Prepare article titles for LLM
  article_summaries = "\n".join([f"{article['Id']}: {article['Title']} - {article['Summary']}" for article in KNOWLEDGE_ARTICLES])
  print(f"Article Summaries: {article_summaries}")

  try:
      # Call LLM to select the most relevant article
      current_llm = get_llm(state.model_name)
      response = current_llm.invoke(
          prompt.format(
              case_description=case_description,
              article_summaries=article_summaries
          )
      )
      print(f"Response: {response}")
      knowledge_article_id = response.content.strip()
      # Validate the ID and fetch title
      knowledge_article_title = ""
      if knowledge_article_id:
          for article in KNOWLEDGE_ARTICLES:
              if article["Id"] == knowledge_article_id:
                  knowledge_article_title = article["Title"]
                  break
          else:
              knowledge_article_id = ""  # Invalid ID, reset
      
      node_output = {
          "knowledge_article_id": knowledge_article_id,
          "knowledge_article_title": knowledge_article_title,
          "available_articles_count": len(KNOWLEDGE_ARTICLES),
          "model_used": state.model_name
      }
      node_outputs = state.node_outputs + [{"node": "knowledge_article_retrieval", "output": node_output}]
      
      return PVIState(
          query_text=state.query_text,
          case_id=state.case_id,
          case_description=state.case_description,
          case_subject=state.case_subject,
          case_subject_terms=state.case_subject_terms,
          knowledge_article_id=knowledge_article_id,
          knowledge_article_title=knowledge_article_title,
          error=state.error,
          model_name=state.model_name,
          node_outputs=node_outputs
      )
  except Exception as e:
      node_output = {"error": f"error in LLM processing: {str(e)}"}
      node_outputs = state.node_outputs + [{"node": "knowledge_article_retrieval", "output": node_output}]
      return PVIState(
          query_text=state.query_text,
          case_id=state.case_id,
          case_description=state.case_description,
          case_subject=state.case_subject,
          case_subject_terms=state.case_subject_terms,
          knowledge_article_id="",
          knowledge_article_title="",
          error=f"error in LLM processing: {str(e)}",
          model_name=state.model_name,
          node_outputs=node_outputs
      )

pvi_workflow = StateGraph(PVIState)

pvi_workflow.add_node("case_retrieval", case_retrieval_node)
pvi_workflow.add_node("knowledge_article_retrieval", knowledge_article_retrieval_node)

pvi_workflow.add_edge("case_retrieval", "knowledge_article_retrieval")
pvi_workflow.add_edge("knowledge_article_retrieval", END)

pvi_workflow.set_entry_point("case_retrieval")

pvi_app = pvi_workflow.compile()
