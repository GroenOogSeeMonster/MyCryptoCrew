import json
import logging
from typing import Dict, List
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from .config import APIConfig
from langchain_openai import ChatOpenAI
from .data_fetcher import CryptoDataFetcher
import asyncio
import time
from .trading_client import BybitDemoClient

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
        self.top_cryptos_cache = {}
        self.cache_timestamp = None
        self.cache_duration = 3600  # Update top cryptos every hour
        
        # Add Bybit demo trading client
        self.trading_client = BybitDemoClient(
            api_key=config.bybit_demo_key,
            api_secret=config.bybit_demo_secret
        )

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

    async def get_top_cryptocurrencies(self, limit: int = 10) -> List[str]:
        """Fetch and cache top cryptocurrencies by market cap"""
        current_time = time.time()
        if (not self.cache_timestamp or 
            current_time - self.cache_timestamp > self.cache_duration):
            market_data = await self.data_fetcher.fetch_market_rankings()
            self.top_cryptos_cache = market_data[:limit]
            self.cache_timestamp = current_time
        return self.top_cryptos_cache

    async def analyze_trading_opportunity(self, symbol: str) -> Dict:
        """Analyze trading opportunities for a specific cryptocurrency"""
        analysis = await self.analyze_crypto(symbol)
        
        # Add trading-specific analysis
        technical_score = self._calculate_technical_score(analysis['analyses']['technical'])
        market_score = self._calculate_market_score(analysis['analyses']['market'])
        volatility = self._calculate_volatility(analysis['market_data'])
        
        return {
            'symbol': symbol,
            'technical_score': technical_score,
            'market_score': market_score,
            'volatility': volatility,
            'trade_recommendation': self._generate_trade_recommendation(
                technical_score, market_score, volatility
            )
        }

    async def execute_trading_strategy(self):
        """Execute trading strategy on top cryptocurrencies"""
        try:
            # Get top cryptocurrencies
            top_cryptos = await self.get_top_cryptocurrencies()
            
            # Analyze each cryptocurrency
            opportunities = []
            for crypto in top_cryptos:
                analysis = await self.analyze_trading_opportunity(crypto)
                opportunities.append(analysis)
            
            # Filter and execute trades based on opportunities
            for opportunity in opportunities:
                if self._should_execute_trade(opportunity):
                    await self._place_trade(opportunity)
            
            # Generate trading report
            report = self._generate_trading_report(opportunities)
            logger.info(f"Trading strategy execution report: {report}")
            
            return report
            
        except Exception as e:
            logger.error(f"Error executing trading strategy: {str(e)}")
            raise

    def _should_execute_trade(self, opportunity: Dict) -> bool:
        """Determine if a trade should be executed based on analysis"""
        return (opportunity['technical_score'] > 7.0 and
                opportunity['market_score'] > 7.0 and
                opportunity['volatility'] < 0.5)

    async def _place_trade(self, opportunity: Dict):
        """Place trade on Bybit demo account"""
        recommendation = opportunity['trade_recommendation']
        if recommendation['action'] == 'buy':
            await self.trading_client.create_order(
                symbol=opportunity['symbol'],
                side='Buy',
                quantity=recommendation['size'],
                price=recommendation['entry_price'],
                stop_loss=recommendation['stop_loss'],
                take_profit=recommendation['take_profit']
            )

    def _calculate_technical_score(self, technical_analysis: str) -> float:
        """
        Calculate technical score from analysis text
        Returns a score between 0 and 10
        """
        try:
            # Extract numerical scores from the technical analysis text
            scores = []
            lines = technical_analysis.split('\n')
            for line in lines:
                # Look for numbers between 1-10 in the text
                if '(' in line and ')' in line:
                    try:
                        score = float(line.split('(')[1].split(')')[0])
                        if 1 <= score <= 10:
                            scores.append(score)
                    except ValueError:
                        continue

            # Return average score, default to 5 if no valid scores found
            return sum(scores) / len(scores) if scores else 5.0

        except Exception as e:
            logger.error(f"Error calculating technical score: {str(e)}")
            return 5.0  # Default to neutral score on error

    def _calculate_market_score(self, market_analysis: str) -> float:
        """
        Calculate market score from analysis text
        Returns a score between 0 and 10
        """
        try:
            # Extract numerical scores from the market analysis text
            scores = []
            lines = market_analysis.split('\n')
            for line in lines:
                # Look for numbers between 1-10 in the text
                if '(' in line and ')' in line:
                    try:
                        score = float(line.split('(')[1].split(')')[0])
                        if 1 <= score <= 10:
                            scores.append(score)
                    except ValueError:
                        continue

            # Return average score, default to 5 if no valid scores found
            return sum(scores) / len(scores) if scores else 5.0

        except Exception as e:
            logger.error(f"Error calculating market score: {str(e)}")
            return 5.0  # Default to neutral score on error

    def _calculate_volatility(self, market_data: Dict) -> float:
        """
        Calculate volatility from market data
        Returns a value between 0 and 1
        """
        try:
            if 'usd_24h_change' in market_data:
                # Convert percentage to decimal and normalize
                volatility = abs(market_data['usd_24h_change']) / 100
                # Cap at 1.0 for extremely volatile assets
                return min(volatility, 1.0)
            return 0.5  # Default medium volatility if data not available

        except Exception as e:
            logger.error(f"Error calculating volatility: {str(e)}")
            return 0.5  # Default to medium volatility on error

    def _generate_trade_recommendation(
        self, 
        technical_score: float, 
        market_score: float, 
        volatility: float
    ) -> Dict:
        """
        Generate trading recommendations based on analysis scores
        """
        try:
            # Calculate overall score (weighted average)
            overall_score = (technical_score * 0.4 + market_score * 0.6)
            
            # Determine position size based on volatility
            # Lower volatility allows for larger position sizes
            base_position_size = 100  # Base position size in USD
            position_size = base_position_size * (1 - volatility)
            
            # Generate recommendation
            if overall_score >= 7.0:
                return {
                    'action': 'buy',
                    'confidence': overall_score / 10,
                    'size': position_size,
                    'entry_price': None,  # To be filled with current market price
                    'stop_loss': None,    # To be calculated based on volatility
                    'take_profit': None   # To be calculated based on volatility
                }
            elif overall_score <= 3.0:
                return {
                    'action': 'sell',
                    'confidence': (10 - overall_score) / 10,
                    'size': position_size,
                    'entry_price': None,
                    'stop_loss': None,
                    'take_profit': None
                }
            else:
                return {
                    'action': 'hold',
                    'confidence': 0.5,
                    'size': 0,
                    'entry_price': None,
                    'stop_loss': None,
                    'take_profit': None
                }

        except Exception as e:
            logger.error(f"Error generating trade recommendation: {str(e)}")
            return {
                'action': 'hold',
                'confidence': 0,
                'size': 0,
                'entry_price': None,
                'stop_loss': None,
                'take_profit': None
            }

    def _generate_trading_report(self, opportunities: List[Dict]) -> Dict:
        """
        Generate a summary report of trading opportunities
        """
        try:
            total_opportunities = len(opportunities)
            buy_signals = len([op for op in opportunities if op['trade_recommendation']['action'] == 'buy'])
            sell_signals = len([op for op in opportunities if op['trade_recommendation']['action'] == 'sell'])
            hold_signals = len([op for op in opportunities if op['trade_recommendation']['action'] == 'hold'])
            
            avg_technical_score = sum(op['technical_score'] for op in opportunities) / total_opportunities
            avg_market_score = sum(op['market_score'] for op in opportunities) / total_opportunities
            avg_volatility = sum(op['volatility'] for op in opportunities) / total_opportunities
            
            return {
                'timestamp': time.time(),
                'total_opportunities': total_opportunities,
                'signals': {
                    'buy': buy_signals,
                    'sell': sell_signals,
                    'hold': hold_signals
                },
                'averages': {
                    'technical_score': avg_technical_score,
                    'market_score': avg_market_score,
                    'volatility': avg_volatility
                },
                'opportunities': [
                    {
                        'symbol': op['symbol'],
                        'action': op['trade_recommendation']['action'],
                        'confidence': op['trade_recommendation']['confidence']
                    }
                    for op in opportunities
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating trading report: {str(e)}")
            return {
                'timestamp': time.time(),
                'error': str(e)
            }