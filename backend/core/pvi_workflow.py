from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
from typing import List, Dict
from .tools import SOQLQueryTool
from .llm import llm
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
    
# Query all knowledge articles from Knowledge__kav
def fetch_knowledge_articles() -> List[Dict[str, str]]:
    query = "SELECT Id, Title FROM Knowledge__kav"
    try:
        result = SOQLQueryTool()._run(query)
        if isinstance(result, list):
            articles = [{"Id": record["Id"], "Title": record.get("Title", "")} for record in result]
            print(f"Fetched {len(articles)} knowledge articles")
            return articles
        else:
            print(f"Error fetching knowledge articles: Unexpected result format")
            return []
    except Exception as e:
        print(f"Error fetching knowledge articles: {str(e)}")
        return []
    
prompt = ChatPromptTemplate.from_template(
    """You are a Salesforce policy violation analyst. Your task is to analyze a case description and determine if it indicates a policy violation by matching it to the most relevant knowledge article title from a provided list. Return only the ID of the most relevant article, or an empty string ("") if the description does not indicate a policy violation or no article is relevant. If multiple articles seem relevant, choose the most specific match based on the description. Ensure the returned ID exactly matches one of the provided article IDs.

    Case description: "{case_description}"

    Knowledge article titles:
    {article_titles}

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
        if isinstance(soql_result, list) and len(soql_result) > 0:
            record = soql_result[0]
            case_description = record.get('Description', '')
            case_subject = record.get('Subject', '')
            case_subject_terms = case_subject.split() if case_subject else []
        else:
            state.error = "No case found for the given ID"
            return state

        state.case_description = case_description
        state.case_subject = case_subject
        state.case_subject_terms = case_subject_terms

    except Exception as e:
        state.error = f"Error executing SOQL query: {str(e)}"
        return state

    return state

def knowledge_article_retrieval_node(state: PVIState) -> PVIState:
  if state.error:
    print(f"Knowledge Article Node - Error: {state.error}")
    return state

  # case_subject = state.case_subject
  # if not case_subject:
  #     state.error = "no case subject available"
  #     return state

  case_description = state.case_description
  if not case_description:
      state.error = "no case description available"
      return state
  
  KNOWLEDGE_ARTICLES = fetch_knowledge_articles()

  if not KNOWLEDGE_ARTICLES:
      state.error = "no knowledge articles available"
      return state

  # Prepare article titles for LLM
  article_titles = "\n".join([f"{article['Id']}: {article['Title']}" for article in KNOWLEDGE_ARTICLES])

  try:
      # Call LLM to select the most relevant article
      response = llm.invoke(
          prompt.format(
              # case_subject=case_subject,
              case_description=case_description,
              article_titles=article_titles
          )
      )
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
  except Exception as e:
      state.error = f"error in LLM processing: {str(e)}"
      knowledge_article_id = ""
      knowledge_article_title = ""

  state.knowledge_article_id = knowledge_article_id
  state.knowledge_article_title = knowledge_article_title
  return state

pvi_workflow = StateGraph(PVIState)

pvi_workflow.add_node("case_retrieval", case_retrieval_node)
pvi_workflow.add_node("knowledge_article_retrieval", knowledge_article_retrieval_node)

pvi_workflow.add_edge("case_retrieval", "knowledge_article_retrieval")
pvi_workflow.add_edge("knowledge_article_retrieval", END)

pvi_workflow.set_entry_point("case_retrieval")

pvi_app = pvi_workflow.compile()
