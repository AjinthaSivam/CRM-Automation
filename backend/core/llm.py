from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()
DEEPINFRA_API_KEY = os.getenv('DEEPINFRA_API_KEY')

llm = ChatOpenAI(
    api_key=DEEPINFRA_API_KEY,
    base_url="https://api.deepinfra.com/v1/openai",
    model="meta-llama/Meta-Llama-3.1-70B-Instruct",
)