from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()
DEEPINFRA_API_KEY = os.getenv('DEEPINFRA_API_KEY')

# Available models
AVAILABLE_MODELS = {
    "70b": "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "405b": "meta-llama/Meta-Llama-3.1-405B-Instruct"
}

def get_llm(model_name: str = "70b") -> ChatOpenAI:
    """
    Get LLM instance for the specified model.
    
    Args:
        model_name: Either "70b" or "405b"
    
    Returns:
        ChatOpenAI instance configured for the specified model
    """
    if model_name not in AVAILABLE_MODELS:
        raise ValueError(f"Model '{model_name}' not supported. Available models: {list(AVAILABLE_MODELS.keys())}")
    
    return ChatOpenAI(
        api_key=DEEPINFRA_API_KEY,
        base_url="https://api.deepinfra.com/v1/openai",
        model=AVAILABLE_MODELS[model_name],
    )

# Default LLM instance for backward compatibility
llm = get_llm("70b")