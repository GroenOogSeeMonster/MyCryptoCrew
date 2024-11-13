import logging
import asyncio
from typing import Dict, Any
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
        try:
            llm = ChatOpenAI(
                api_key=self.api_key,
                temperature=self.temperature,
                model_name=self.model_name,
                request_timeout=30,
                max_retries=3
            )
            logger.info(f"LLM created successfully with model: {self.model_name}")
            return llm
        except Exception as e:
            logger.error(f"Error creating LLM instance: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((openai.APIError, openai.APIConnectionError, openai.RateLimitError)),
        reraise=True
    )
    async def run_analysis(self, prompt_template: str, variables: Dict[str, Any]) -> str:
        """Run LLM analysis with retry mechanism"""
        try:
            prompt = PromptTemplate(
                input_variables=list(variables.keys()),
                template=prompt_template
            )
            chain = prompt | self.llm
            logger.info(f"Running analysis with variables: {variables}")
            response = await chain.ainvoke(variables)
            logger.info(f"LLM analysis completed successfully: {response}")
            return response.content
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit error: {str(e)}")
            raise
        except openai.APIConnectionError as e:
            logger.warning(f"API connection error: {str(e)}")
            raise
        except openai.APIError as e:
            logger.warning(f"API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in LLM analysis: {str(e)}")
            raise
    
    async def retryable_analysis(self, prompt_template: str, variables: Dict[str, Any], max_retries: int = 3) -> str:
        """Run LLM analysis with manual retry logic for better control"""
        for attempt in range(max_retries):
            try:
                response = await self.run_analysis(prompt_template, variables)
                return response
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    logger.error("Max retries reached, analysis failed.")
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

    def set_model(self, model_name: str):
        """Set a different model for the LLM"""
        try:
            self.model_name = model_name
            self.llm = self._create_llm()
            logger.info(f"Model updated to: {model_name}")
        except Exception as e:
            logger.error(f"Error updating model: {str(e)}")
            raise

    def set_temperature(self, temperature: float):
        """Set a different temperature for the LLM"""
        try:
            self.temperature = temperature
            self.llm = self._create_llm()
            logger.info(f"Temperature updated to: {temperature}")
        except Exception as e:
            logger.error(f"Error updating temperature: {str(e)}")
            raise
