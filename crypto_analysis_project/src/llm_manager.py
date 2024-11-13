import logging
import asyncio
from typing import Dict, Any
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import openai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

logger = logging.getLogger(__name__)

class LLMManager:
    def __init__(self, api_key: str, model_name: str = "gpt-3.5-turbo-16k", temperature: float = 0.7):
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.llm = self._create_llm()
        
    def _create_llm(self) -> ChatOpenAI:
        """Create LLM instance with retry mechanism"""
        return ChatOpenAI(
            api_key=self.api_key,
            temperature=self.temperature,
            model_name=self.model_name,
            request_timeout=30,
            max_retries=3
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((openai.APIError, openai.APIConnectionError, openai.RateLimitError)),
        reraise=True
    )
    async def run_analysis(self, prompt_template: str, variables: Dict[str, Any]) -> str:
        """Run LLM analysis with retry mechanism"""
        try:
            chain = LLMChain(
                llm=self.llm,
                prompt=PromptTemplate(
                    input_variables=list(variables.keys()),
                    template=prompt_template
                )
            )
            
            return await chain.arun(**variables)
            
        except Exception as e:
            logger.error(f"Error in LLM analysis: {str(e)}")
            raise 