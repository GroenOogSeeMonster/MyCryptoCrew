import json
import logging
from typing import Dict
from langchain import LLMChain
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from .config import APIConfig

logger = logging.getLogger(__name__)

class CryptoAnalysisAgents:
    def __init__(self, config: APIConfig):
        self.llm = OpenAI(api_key=config.openai_key)
        self.agents = self._create_agents()

    def _create_agents(self) -> Dict[str, LLMChain]:
        prompts = {
            "technical": self._get_technical_prompt(),
            "financial": self._get_financial_prompt(),
            "legal": self._get_legal_prompt(),
            "market": self._get_market_prompt(),
        }

        return {
            name: LLMChain(
                llm=self.llm,
                prompt=PromptTemplate(
                    input_variables=['crypto', 'market_data'],
                    template=prompt
                )
            )
            for name, prompt in prompts.items()
        }

    def _get_technical_prompt(self) -> str:
        return """Analyze {crypto}'s technical aspects based on the following market data: {market_data}
            1. Consensus mechanism efficiency
            2. Network scalability solutions
            3. Security features and history
            4. Smart contract capabilities
            Output a structured analysis with scores (1-10) for each aspect."""

    def _get_financial_prompt(self) -> str:
        return """Evaluate {crypto}'s financial metrics based on the following market data: {market_data}
            1. Market capitalization trends
            2. Trading volume patterns
            3. Price volatility
            4. Liquidity metrics
            Provide numerical scores (1-10) for each metric."""

    # Add other prompt methods similarly...

    async def analyze_crypto(self, crypto: str, data: Dict) -> Dict:
        results = {}
        for agent_name, agent in self.agents.items():
            try:
                results[agent_name] = await agent.arun(
                    crypto=crypto,
                    market_data=json.dumps(data)
                )
            except Exception as e:
                logger.error(f"Error in {agent_name} analysis: {e}")
                results[agent_name] = None
        return results 