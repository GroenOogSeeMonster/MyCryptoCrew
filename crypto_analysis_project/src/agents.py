import json
import logging
from typing import Dict, List
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from .config import APIConfig
from langchain_openai import ChatOpenAI
from .data_fetcher import CryptoDataFetcher
import asyncio
import time
from .trading_client import BybitDemoClient
from .llm_manager import LLMManager

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class CryptoAnalysisAgents:
    def __init__(self, config: APIConfig):
        self.config = config
        self.llm_manager = LLMManager(
            api_key=config.openai_key,
            model_name="gpt-3.5-turbo-16k",
            temperature=0.7
        )
        self.data_fetcher = CryptoDataFetcher(config)
        self.prompts = self._create_prompts()
        self.top_cryptos_cache = {}
        self.cache_timestamp = None
        self.cache_duration = 3600
        
        self.trading_client = BybitDemoClient(
            api_key=config.bybit_demo_key,
            api_secret=config.bybit_demo_secret
        )
        self.trade_history = []

    def _create_prompts(self) -> Dict[str, str]:
        """Create analysis prompts"""
        return {
            "technical": self._get_technical_prompt(),
            "financial": self._get_financial_prompt(),
            "legal": self._get_legal_prompt(),
            "market": self._get_market_prompt()
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

    async def analyze_crypto(self, uuid: str) -> Dict:
        """Analyze cryptocurrency data for the given UUID"""
        try:
            # Fetch market data first using UUID
            market_data = await self.data_fetcher.fetch_market_data(uuid)
            if not market_data:
                raise ValueError(f"No market data available for UUID {uuid}")

            # Process market data for analysis
            processed_market_data = {}
            for key, value in market_data.items():
                try:
                    if isinstance(value, str):
                        if '%' in value:
                            value = float(value.replace('%', ''))
                        elif any(symbol in value for symbol in ['$', '€', '£']):
                            value = float(value.replace('$', '').replace('€', '').replace('£', '').replace(',', ''))
                        elif value.replace('.', '', 1).replace('-', '', 1).isdigit():
                            value = float(value)
                    processed_market_data[key] = value
                except (ValueError, TypeError):
                    processed_market_data[key] = value

            # Start news fetch task early
            news_task = asyncio.create_task(self.data_fetcher.fetch_news_data(uuid))

            # Prepare analysis variables
            variables = {
                'crypto': market_data.get('name', ''),
                'market_data': json.dumps(processed_market_data, indent=2),
                'coin_data': json.dumps(processed_market_data, indent=2)
            }

            # Create and execute all analysis tasks concurrently
            analyses = {}
            analysis_tasks = [
                self.llm_manager.run_analysis(prompt, variables)
                for analysis_type, prompt in self.prompts.items()
            ]

            # Wait for all analyses with timeout
            try:
                analysis_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
                for analysis_type, result in zip(self.prompts.keys(), analysis_results):
                    if isinstance(result, Exception):
                        logger.warning(f"Failed to run {analysis_type} analysis: {str(result)}")
                        analyses[analysis_type] = f"Analysis failed: {str(result)}"
                    else:
                        analyses[analysis_type] = result
            except Exception as e:
                logger.error(f"Error during analysis gathering: {str(e)}")
                analyses = {"error": str(e)}

            # Get news data from earlier task
            try:
                news_data = await news_task
            except Exception as e:
                logger.warning(f"Failed to fetch news data: {str(e)}")
                news_data = []

            return {
                "market_data": processed_market_data,
                "analyses": analyses,
                "news_data": news_data,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Error in analyze_crypto: {str(e)}")
            logger.exception("Full traceback:")
            raise

    def _calculate_technical_score(self, analysis: str) -> float:
        """Extract technical score from analysis text"""
        try:
            logger.debug(f"Calculating technical score from analysis: {analysis}")
            # Look for score pattern in the text (e.g., "Score: 7.5" or "score: 8")
            import re
            scores = []
            score_pattern = r'(?i)score:\s*(\d+(?:\.\d+)?)'
            matches = re.finditer(score_pattern, analysis)
            
            for match in matches:
                try:
                    score = float(match.group(1))
                    scores.append(score)
                except ValueError as e:
                    logger.warning(f"Failed to convert score to float: {match.group(1)}")
                    continue
            
            if not scores:
                logger.warning("No valid scores found in analysis, using default score")
                return 5.0
                
            # Average all found scores
            avg_score = sum(scores) / len(scores)
            logger.debug(f"Calculated technical score: {avg_score}")
            return min(max(avg_score, 0), 10)  # Ensure score is between 0 and 10
            
        except Exception as e:
            logger.error(f"Error calculating technical score: {str(e)}")
            return 5.0  # Default score on error

    def _calculate_market_score(self, analysis: str) -> float:
        """Extract market score from analysis text"""
        try:
            logger.debug(f"Calculating market score from analysis: {analysis}")
            # Look for score pattern in the text (e.g., "Score: 7.5" or "score: 8")
            import re
            scores = []
            score_pattern = r'(?i)score:\s*(\d+(?:\.\d+)?)'
            matches = re.finditer(score_pattern, analysis)
            
            for match in matches:
                try:
                    score = float(match.group(1))
                    scores.append(score)
                except ValueError as e:
                    logger.warning(f"Failed to convert score to float: {match.group(1)}")
                    continue
            
            if not scores:
                logger.warning("No valid scores found in analysis, using default score")
                return 5.0
                
            # Average all found scores
            avg_score = sum(scores) / len(scores)
            logger.debug(f"Calculated market score: {avg_score}")
            return min(max(avg_score, 0), 10)  # Ensure score is between 0 and 10
            
        except Exception as e:
            logger.error(f"Error calculating market score: {str(e)}")
            return 5.0  # Default score on error

    def _calculate_volatility(self, market_data: Dict) -> float:
        """
        Calculate volatility from market data.
        Returns a value between 0 and 1.
        """
        try:
            logger.debug(f"Calculating volatility with market_data: {market_data}")
            
            if not isinstance(market_data, dict):
                logger.warning(f"Market data is not a dictionary: {type(market_data)}")
                return 0.5
            
            # Coinranking API uses 'change' field for 24h price change
            if 'change' not in market_data:
                logger.warning("'change' field not found in market data")
                return 0.5
            
            change = market_data['change']
            logger.debug(f"24h change value: {change} (type: {type(change)})")
            
            # Convert to float if it's a string
            if isinstance(change, str):
                change = float(change.replace('%', '').replace(',', ''))
            
            # Convert percentage to decimal and normalize
            volatility = abs(float(change)) / 100
            # Cap at 1.0 for extremely volatile assets
            return min(volatility, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {str(e)}")
            logger.exception("Volatility calculation error:")
            return 0.5  # Default to medium volatility on error

    def _generate_trade_recommendation(self, technical_score: float, market_score: float, volatility: float) -> Dict:
        """
        Generate trading recommendations based on analysis scores.
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

    async def execute_trading_strategy(self, risk_level: str, leverage_amount: float) -> Dict:
        """Execute trading strategy on top cryptocurrencies with specified risk and leverage"""
        try:
            # Removed context manager
            top_cryptos = await self.get_top_cryptocurrencies()
            
            # Analyze each cryptocurrency with delay between requests
            opportunities = []
            for crypto in top_cryptos:
                try:
                    logger.info(f"Analyzing trading opportunity for {crypto}")
                    analysis = await self.analyze_trading_opportunity(crypto, risk_level)
                    opportunities.append(analysis)
                    logger.info(f"Completed analysis for {crypto}: {analysis}")
                    # Add small delay between analyses
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error analyzing {crypto}: {str(e)}")
                    continue
            
            if not opportunities:
                raise Exception("No valid opportunities found")
            
            # Filter and execute trades based on opportunities
            for opportunity in opportunities:
                if self._should_execute_trade(opportunity, risk_level):
                    logger.info(f"Executing trade for {opportunity['symbol']}")
                    await self._place_trade(opportunity, leverage_amount)
            
            # Generate trading report
            report = self._generate_trading_report(opportunities)
            logger.info(f"Trading strategy execution report: {report}")
            
            return report
                
        except Exception as e:
            logger.error(f"Error executing trading strategy: {str(e)}")
            raise

    async def analyze_trading_opportunity(self, coin: Dict[str, str], risk_level: str) -> Dict:
        """Analyze trading opportunities for a specific cryptocurrency"""
        uuid = coin['uuid']
        symbol = coin['symbol']
        
        try:
            # Fetch market data
            market_data = await self.data_fetcher.fetch_market_data(uuid)
            logger.debug(f"Raw market data for {symbol}: {market_data}")
            
            # Run analysis
            analysis = await self.analyze_crypto(uuid)
            if not analysis or 'analyses' not in analysis:
                raise ValueError(f"Invalid analysis data received for {symbol}")
            
            # Calculate scores
            technical_score = self._calculate_technical_score(analysis['analyses'].get('technical', ''))
            market_score = self._calculate_market_score(analysis['analyses'].get('market', ''))
            
            # Calculate volatility from market data
            volatility = self._calculate_volatility(market_data)
            
            # Generate trade recommendation
            trade_recommendation = {
                'action': 'buy' if technical_score > 7 and market_score > 7 else 'hold',
                'confidence': min((technical_score + market_score) / 2, 10),
                'size': 0.1,  # Default position size
                'entry_price': float(market_data.get('price', 0)),
                'stop_loss': float(market_data.get('price', 0)) * 0.95,  # 5% stop loss
                'take_profit': float(market_data.get('price', 0)) * 1.1  # 10% take profit
            }
            
            return {
                'symbol': symbol,
                'uuid': uuid,
                'technical_score': technical_score,
                'market_score': market_score,
                'volatility': volatility,
                'market_data': market_data,
                'trade_recommendation': trade_recommendation,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trading opportunity for {symbol}: {str(e)}")
            raise

    def _should_execute_trade(self, opportunity: Dict, risk_level: str) -> bool:
        """Determine if a trade should be executed based on analysis and risk level"""
        min_score = 7.0 if risk_level == 'high' else 6.0 if risk_level == 'med' else 5.0
        should_trade = (opportunity['technical_score'] > min_score and
                        opportunity['market_score'] > min_score and
                        opportunity['volatility'] < 0.5)
        logger.info(f"Should execute trade for {opportunity['symbol']}? {'Yes' if should_trade else 'No'}")
        return should_trade

    async def _place_trade(self, opportunity: Dict, leverage_amount: float):
        """Place trade on Bybit demo account with specified leverage"""
        recommendation = opportunity['trade_recommendation']
        if recommendation['action'] == 'buy':
            try:
                logger.info(f"Placing trade for {opportunity['symbol']} with leverage amount: {leverage_amount}")
                await self.trading_client.create_order(
                    symbol=opportunity['symbol'],
                    side='Buy',
                    quantity=recommendation['size'] * leverage_amount,
                    price=recommendation['entry_price'],
                    stop_loss=recommendation['stop_loss'],
                    take_profit=recommendation['take_profit']
                )
                self.trade_history.append(opportunity)
                logger.info(f"Successfully placed trade for {opportunity['symbol']}")
            except Exception as e:
                logger.error(f"Error placing trade for {opportunity['symbol']}: {str(e)}")
                raise

    async def get_top_cryptocurrencies(self, limit: int = 10) -> List[Dict[str, str]]:
        """Fetch and cache top cryptocurrencies by market cap"""
        # Updated return type annotation
        current_time = time.time()
        if not self.cache_timestamp or current_time - self.cache_timestamp > self.cache_duration:
            market_data = await self.data_fetcher.fetch_market_rankings(limit=limit)
            self.top_cryptos_cache = market_data
            self.cache_timestamp = current_time
        return self.top_cryptos_cache

    def generate_final_report(self) -> Dict:
        """Generate a final report of all trades made during the session"""
        try:
            total_trades = len(self.trade_history)
            successful_trades = len([trade for trade in self.trade_history if trade['trade_recommendation']['action'] == 'buy'])
            profit_trades = len([trade for trade in self.trade_history if trade.get('profit', 0) > 0])
            
            report = {
                'total_trades': total_trades,
                'successful_trades': successful_trades,
                'profit_trades': profit_trades,
                'trade_history': [
                    {
                        'symbol': trade['symbol'],
                        'action': trade['trade_recommendation']['action'],
                        'confidence': trade['trade_recommendation']['confidence'],
                        'profit': trade.get('profit', 0)
                    }
                    for trade in self.trade_history
                ]
            }
            logger.info(f"Final Trading Report: {report}")
            return report
        except Exception as e:
            logger.error(f"Error generating final report: {str(e)}")
            return {'error': str(e)}

    def _generate_trading_report(self, opportunities: List[Dict]) -> Dict:
        """Generate a report of trading opportunities and actions taken"""
        try:
            return {
                'timestamp': time.time(),
                'opportunities_analyzed': len(opportunities),
                'opportunities': [{
                    'symbol': opp['symbol'],
                    'technical_score': opp['technical_score'],
                    'market_score': opp['market_score'],
                    'volatility': opp['volatility'],
                    'recommendation': opp['trade_recommendation']['action']
                } for opp in opportunities],
                'active_trades': len([opp for opp in opportunities 
                                    if opp['trade_recommendation']['action'] in ['buy', 'sell']]),
                'total_trades': len(self.trade_history)
            }
        except Exception as e:
            logger.error(f"Error generating trading report: {str(e)}")
            return {
                'error': str(e),
                'timestamp': time.time(),
                'opportunities_analyzed': 0,
                'opportunities': [],
                'active_trades': 0,
                'total_trades': len(self.trade_history)
            }
