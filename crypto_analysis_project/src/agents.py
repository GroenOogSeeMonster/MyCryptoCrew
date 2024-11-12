import json
import logging
from typing import Dict
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from .config import APIConfig
from langchain_openai import ChatOpenAI
from .data_fetcher import CryptoDataFetcher
import asyncio

logger = logging.getLogger(__name__)

class CryptoAnalysisAgents:
    def __init__(self, config: APIConfig):
        self.config = config
        self.llm = ChatOpenAI(
            api_key=config.openai_key,
            temperature=0.7,
            model_name="gpt-3.5-turbo-16k"
        )
        self.data_fetcher = CryptoDataFetcher(config)  # Initialize data_fetcher first
        self.agents = self._create_agents()

    def _create_agents(self) -> Dict[str, LLMChain]:
        prompts = {
            "technical": (self._get_technical_prompt(), ['crypto', 'market_data']),
            "financial": (self._get_financial_prompt(), ['crypto', 'market_data']),
            "legal": (self._get_legal_prompt(), ['coin_data']),
            "market": (self._get_market_prompt(), ['coin_data']),
        }

        return {
            name: LLMChain(
                llm=self.llm,
                prompt=PromptTemplate(
                    input_variables=variables,
                    template=prompt
                )
            )
            for name, (prompt, variables) in prompts.items()
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

    def _get_legal_prompt(self) -> str:
        return """
        Analyze the legal and regulatory aspects of the following cryptocurrency:
        {coin_data}
        
        Please consider:
        1. Current regulatory status
        2. Compliance with major jurisdictions
        3. Any pending regulatory issues
        4. Legal risks and challenges
        
        Provide a detailed analysis in a clear, structured format.
        """

    def _get_market_prompt(self) -> str:
        return """
        Provide a comprehensive market analysis for the following cryptocurrency:
        {coin_data}
        
        Please analyze:
        1. Current market position and price trends
        2. Trading volume and liquidity
        3. Market capitalization and dominance
        4. Key market indicators and metrics
        5. Recent market movements and potential catalysts
        
        Present the analysis in a clear, structured format with key insights highlighted.
        """

    async def analyze_crypto(self, symbol: str) -> Dict:
        """
        Analyze cryptocurrency data for the given symbol
        """
        try:
            # Fetch data concurrently
            market_data, news_data = await asyncio.gather(
                self.data_fetcher.fetch_market_data(symbol),
                self.data_fetcher.fetch_news_data(symbol)
            )
            
            # Run analysis with each agent
            analyses = {}
            for agent_name, agent in self.agents.items():
                if agent_name in ["technical", "financial"]:
                    analyses[agent_name] = await agent.arun(
                        crypto=symbol,
                        market_data=str(market_data)
                    )
                else:  # legal and market analyses
                    analyses[agent_name] = await agent.arun(
                        coin_data=str(market_data)
                    )
            
            return {
                "symbol": symbol,
                "market_data": market_data,
                "news_data": news_data,
                "analyses": analyses
            }
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {str(e)}")
            raise