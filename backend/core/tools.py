from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
from .salesforce import sf_client

class SOQLQueryInput(BaseModel):
    query: str = Field(..., description="A dynamically generated SOQL query.")
    
class SOQLQueryTool(BaseTool):
    name: str = "SOQL Query Tool"
    description: str = "Executes a SOQL query against Salesforce."
    args_schema: Type[BaseModel] = SOQLQueryInput
    
    def _run(self, query: str) -> str:
        """Execute the SOQL query."""
        try:
            results = sf_client.query(query)
            return results['records']
        except Exception as e:
            return f"Error executing SOQL query: {str(e)}"
        
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
            return f"Error executing SOSL query: {str(e)}"
        
   
    
    
    
