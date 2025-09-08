from core.llm import llm
import logging

logger = logging.getLogger(__name__)

def classify_task_type(query):
    """
    Use LLM to classify the query as 'NED', 'PVI', or 'KQA'.
    
    Args:
        query (str): The user's query text
        
    Returns:
        str: One of 'NED', 'PVI', or 'KQA'
    """
    try:
        classification_prompt = f"""
            You are a Salesforce Task Classifier Agent in a CRM automation system. 
            Your job is to classify user queries into one of the following three categories based on their intent and wording:

            1. NED (Named Entity Disambiguation)  
            These queries refer to specific products that the customer has already purchased. 
            They often include time filters or product descriptions.  
            Examples:  
            - "Display the waterproof hiking boots I purchased three days back"  
            - "Can you display the adjustable weight dumbbells I purchased a month ago?"  
            - "Can you display the women's trail jacket I purchased a fortnight ago?"

            2. PVI (Policy Violation Identification)  
            These queries question whether an agent followed company policy during a specific interaction or case.  
            Examples:  
            - "Did the agent breach the policy in this situation?"  
            - "Did the agent breach the policy in this instance?"  
            - "Did the agent breach the policy?"

            3. KQA (Knowledge Question Answering)  
            These are general knowledge-based questions not tied to a specific purchase or agent behavior. 
            They often relate to product features, company policies, or usage instructions.  
            Examples:  
            - "What technology features do Shoes & Clothings golf shoes have?"  
            - "What is the time frame for being eligible for a full refund with Shoes & Clothings?"  
            - "How can I store my yoga straps to prolong their life?"

            Now classify the following user query into **only one** of the above categories.  
            User Query: "{query}"

            Respond with exactly one word: NED, PVI, or KQA.
            """

        # Get classification from LLM
        response = llm.invoke(classification_prompt)
        classification = response.content.strip().upper()
        
        # Validate the response
        if classification in ['NED', 'PVI', 'KQA']:
            logger.info(f"Query '{query}' classified as: {classification}")
            return classification
        else:
            logger.warning(f"Invalid classification '{classification}' for query '{query}', defaulting to KQA")
            return "KQA"
            
    except Exception as e:
        logger.error(f"Error in LLM classification for query '{query}': {str(e)}")
        # Fallback to simple keyword-based classification
        return _fallback_classification(query)

def _fallback_classification(query):
    """
    Fallback classification using simple keyword matching when LLM fails.
    """
    query_lower = query.lower()

    # NED keywords — related to past purchases and display requests
    ned_keywords = [
        'i purchased', 'bought', 'show my', 'display the', 'my order', 
        'purchased last', 'purchased a month ago', 'purchased three days ago',
        'purchased recently', 'display product i bought', 'show product i ordered'
    ]
    if any(keyword in query_lower for keyword in ned_keywords):
        return "NED"

    # PVI keywords — checking if agent followed policy
    pvi_keywords = [
        'breach the policy', 'violate the policy', 'policy violation', 
        'did the agent', 'agent follow policy', 'policy breach', 
        'agent violate', 'agent fault'
    ]
    if any(keyword in query_lower for keyword in pvi_keywords):
        return "PVI"

    # Default to KQA — general product, refund, or how-to questions
    return "KQA"
