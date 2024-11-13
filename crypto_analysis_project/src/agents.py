import json
import logging
from typing import Dict, List
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from src.config import APIConfig, SelectionConfig
from langchain_openai import ChatOpenAI
from src.data_fetcher import CryptoDataFetcher
import asyncio
import time
from src.trading_client import BybitDemoClient
from src.llm_manager import LLMManager
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
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
        self.risk_parameters = {
            'low': {
                'min_score': 8.0,
                'max_volatility': 0.3,
                'position_size_multiplier': 0.5,
                'stop_loss_percentage': 0.02,  # 2%
                'take_profit_percentage': 0.04,  # 4%
                'leverage_multiplier': 1
            },
            'med': {
                'min_score': 7.0,
                'max_volatility': 0.5,
                'position_size_multiplier': 0.75,
                'stop_loss_percentage': 0.05,  # 5%
                'take_profit_percentage': 0.1,  # 10%
                'leverage_multiplier': 2
            },
            'high': {
                'min_score': 6.0,
                'max_volatility': 0.7,
                'position_size_multiplier': 1.0,
                'stop_loss_percentage': 0.1,  # 10%
                'take_profit_percentage': 0.2,  # 20%
                'leverage_multiplier': 3
            }
        }
        self.trading_history = []
        self.total_trades_analyzed = 0
        self.successful_trades = 0
        self.profit_trades = 0
        self.total_profit_loss = 0.0
        self.selection_config = config.selection_config
        
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
                
            avg_score = sum(scores) / len(scores)
            return min(max(avg_score, 0), 10)
            
        except Exception as e:
            logger.error(f"Error calculating technical score: {str(e)}")
            return 5.0

    def _calculate_market_score(self, analysis: str) -> float:
        """Extract market score from analysis text"""
        try:
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
                
            avg_score = sum(scores) / len(scores)
            return min(max(avg_score, 0), 10)
            
        except Exception as e:
            logger.error(f"Error calculating market score: {str(e)}")
            return 5.0

    def _calculate_volatility(self, market_data: Dict) -> float:
        """Calculate volatility from market data"""
        try:
            if not isinstance(market_data, dict):
                logger.warning(f"Market data is not a dictionary: {type(market_data)}")
                return 0.5
            
            if 'change' not in market_data:
                logger.warning("'change' field not found in market data")
                return 0.5
            
            change = market_data['change']
            
            if isinstance(change, str):
                change = float(change.replace('%', '').replace(',', ''))
            
            volatility = abs(float(change)) / 100
            return min(volatility, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {str(e)}")
            logger.exception("Volatility calculation error:")
            return 0.5

    def _generate_trade_recommendation(self, technical_score: float, market_score: float, volatility: float, risk_level: str = 'low') -> Dict:
        """Generate trading recommendations based on analysis scores and risk level"""
        try:
            risk_params = self.risk_parameters[risk_level]
            
            # Calculate overall score (weighted average)
            overall_score = (technical_score * 0.4 + market_score * 0.6)
            
            # Calculate position size based on volatility and risk level
            base_position_size = 100  # Base position size in USD
            adjusted_position_size = (
                base_position_size * 
                risk_params['position_size_multiplier'] * 
                (1 - volatility)
            )

            # Generate recommendation based on risk parameters
            if overall_score >= risk_params['min_score'] and volatility <= risk_params['max_volatility']:
                return {
                    'action': 'buy',
                    'confidence': overall_score / 10,
                    'size': adjusted_position_size,
                    'entry_price': None,  # To be filled with current market price
                    'stop_loss_percentage': risk_params['stop_loss_percentage'],
                    'take_profit_percentage': risk_params['take_profit_percentage'],
                    'leverage_multiplier': risk_params['leverage_multiplier']
                }
            elif overall_score <= (risk_params['min_score'] - 2.0):
                return {
                    'action': 'sell',
                    'confidence': (10 - overall_score) / 10,
                    'size': adjusted_position_size,
                    'entry_price': None,
                    'stop_loss_percentage': risk_params['stop_loss_percentage'],
                    'take_profit_percentage': risk_params['take_profit_percentage'],
                    'leverage_multiplier': risk_params['leverage_multiplier']
                }
            else:
                return {
                    'action': 'hold',
                    'confidence': 0.5,
                    'size': 0,
                    'entry_price': None,
                    'stop_loss_percentage': 0,
                    'take_profit_percentage': 0,
                    'leverage_multiplier': 1
                }
        except Exception as e:
            logger.error(f"Error generating trade recommendation: {str(e)}")
            return {
                'action': 'hold',
                'confidence': 0,
                'size': 0,
                'entry_price': None,
                'stop_loss_percentage': 0,
                'take_profit_percentage': 0,
                'leverage_multiplier': 1
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
            
            # Track the trading decision
            trade_result = {
                'symbol': opportunity['symbol'],
                'action': opportunity['trade_recommendation']['action'],
                'confidence': opportunity['trade_recommendation']['confidence'],
                'timestamp': datetime.now().isoformat(),
                'risk_level': risk_level,
                'analysis_factors': opportunity['trade_recommendation'].get('analysis_factors', {}),
                'profit': opportunity['trade_recommendation'].get('profit', 0.0)
            }
            
            self.total_trades_analyzed += 1
            
            if opportunity['trade_recommendation']['action'] == 'buy':
                self.successful_trades += 1
                
            if opportunity['trade_recommendation']['profit'] > 0:
                self.profit_trades += 1
                self.total_profit_loss += opportunity['trade_recommendation']['profit']
            
            self.trading_history.append(trade_result)
            
            return trade_result
                
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
            
            # Generate trade recommendation with risk level
            current_price = float(market_data.get('price', 0))
            recommendation = self._generate_trade_recommendation(
                technical_score, 
                market_score, 
                volatility,
                risk_level
            )
            
            # Add price-based stop loss and take profit
            if recommendation['action'] in ['buy', 'sell']:
                recommendation['entry_price'] = current_price
                recommendation['stop_loss'] = current_price * (1 - recommendation['stop_loss_percentage'])
                recommendation['take_profit'] = current_price * (1 + recommendation['take_profit_percentage'])
            
            return {
                'symbol': symbol,
                'uuid': uuid,
                'technical_score': technical_score,
                'market_score': market_score,
                'volatility': volatility,
                'market_data': market_data,
                'trade_recommendation': recommendation,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trading opportunity for {symbol}: {str(e)}")
            raise

    def _should_execute_trade(self, opportunity: Dict, risk_level: str) -> bool:
        """Determine if a trade should be executed based on analysis and risk level"""
        risk_params = self.risk_parameters[risk_level]
        
        should_trade = (
            opportunity['technical_score'] > risk_params['min_score'] and
            opportunity['market_score'] > risk_params['min_score'] and
            opportunity['volatility'] < risk_params['max_volatility']
        )
        
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
        """Fetch and cache top cryptocurrencies by market cap with filtering"""
        current_time = time.time()
        if not self.cache_timestamp or current_time - self.cache_timestamp > self.cache_duration:
            market_data = await self.data_fetcher.fetch_market_rankings(
                limit=limit,
                selection_config=self.selection_config
            )
            self.top_cryptos_cache = market_data
            self.cache_timestamp = current_time
            
            # Log selection results
            logger.info(f"Selected {len(market_data)} cryptocurrencies for analysis:")
            for crypto in market_data:
                logger.info(f"Selected {crypto['symbol']}: "
                          f"Market Cap: ${crypto.get('market_cap', 0):,.2f}, "
                          f"Volume: ${crypto.get('volume_24h', 0):,.2f}, "
                          f"Volatility: {crypto.get('volatility', 0):.2%}")
                
        return self.top_cryptos_cache

    def update_selection_criteria(self, **kwargs):
        """Update selection criteria dynamically"""
        for key, value in kwargs.items():
            if hasattr(self.selection_config, key):
                setattr(self.selection_config, key, value)
                logger.info(f"Updated selection criteria: {key} = {value}")
            else:
                logger.warning(f"Unknown selection criteria: {key}")
        
        # Clear cache to force refresh with new criteria
        self.cache_timestamp = None

    def generate_final_report(self) -> Dict:
        """Generate a comprehensive final trading report"""
        return {
            'total_trades': self.total_trades_analyzed,
            'successful_trades': self.successful_trades,
            'profit_trades': self.profit_trades,
            'total_profit_loss': self.total_profit_loss,
            'trade_history': self.trading_history,
            'performance_metrics': {
                'success_rate': (self.successful_trades / self.total_trades_analyzed * 100) if self.total_trades_analyzed > 0 else 0,
                'profit_rate': (self.profit_trades / self.total_trades_analyzed * 100) if self.total_trades_analyzed > 0 else 0,
                'average_profit_per_trade': (self.total_profit_loss / self.total_trades_analyzed) if self.total_trades_analyzed > 0 else 0
            }
        }

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

    async def force_best_trade(self, leverage_amount: float) -> Dict:
        """Force a trade on the most promising cryptocurrency with aggressive parameters"""
        try:
            logger.info("Analyzing market for forced trade opportunity...")
            
            # Get top cryptocurrencies with relaxed selection criteria
            original_config = self.selection_config
            relaxed_config = SelectionConfig()
            relaxed_config.min_market_cap = original_config.min_market_cap / 2
            relaxed_config.min_daily_volume = original_config.min_daily_volume / 2
            relaxed_config.max_volatility = 0.5  # Allow higher volatility
            
            self.selection_config = relaxed_config
            top_cryptos = await self.get_top_cryptocurrencies(limit=5)
            self.selection_config = original_config
            
            # Analyze each cryptocurrency
            opportunities = []
            for crypto in top_cryptos:
                analysis = await self.analyze_trading_opportunity(crypto, 'high')
                
                # Calculate comprehensive score
                score = (
                    analysis['technical_score'] * 0.4 +
                    analysis['market_score'] * 0.4 +
                    (1 - analysis['volatility']) * 0.2  # Lower volatility is better
                )
                
                analysis['comprehensive_score'] = score
                opportunities.append(analysis)
                
                logger.info(f"Analyzed {crypto['symbol']}: Score = {score:.2f}")
                await asyncio.sleep(0.5)
            
            if not opportunities:
                raise Exception("No viable trading opportunities found")
            
            # Select best opportunity
            best_opportunity = max(opportunities, key=lambda x: x['comprehensive_score'])
            
            # Generate aggressive trade parameters
            current_price = float(best_opportunity['market_data']['price'])
            position_size = leverage_amount * 0.95  # Use 95% of available leverage
            
            # Place aggressive trade
            logger.info(f"Executing forced trade on {best_opportunity['symbol']}")
            order = await self.trading_client.create_order(
                symbol=best_opportunity['symbol'],
                side='Buy',
                quantity=position_size / current_price,
                price=current_price,
                stop_loss=current_price * 0.90,  # 10% stop loss
                take_profit=current_price * 1.20  # 20% take profit
            )
            
            # Record trade
            trade_result = {
                'symbol': best_opportunity['symbol'],
                'action': 'buy',
                'entry_price': current_price,
                'position_size': position_size,
                'comprehensive_score': best_opportunity['comprehensive_score'],
                'technical_score': best_opportunity['technical_score'],
                'market_score': best_opportunity['market_score'],
                'volatility': best_opportunity['volatility'],
                'timestamp': datetime.now().isoformat(),
                'order_id': order.get('orderId'),
                'stop_loss': current_price * 0.90,
                'take_profit': current_price * 1.20
            }
            
            self.trade_history.append(trade_result)
            logger.info(f"Forced trade executed: {trade_result}")
            
            return trade_result
            
        except Exception as e:
            logger.error(f"Error executing forced trade: {str(e)}")
            raise

