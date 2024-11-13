import aiohttp
import logging
from typing import List, Dict, Any
import json
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CryptoDataFetcher:
    def __init__(self, config):
        self.config = config
        self.coingecko_api = "https://api.coingecko.com/api/v3"
        self.last_request_time = datetime.now()
        self.rate_limit_delay = 1.5  # Delay between requests in seconds
        self.max_retries = 3

    async def _make_request(self, url: str, params: Dict) -> Dict:
        """
        Make API request with rate limiting and retry logic
        """
        for attempt in range(self.max_retries):
            try:
                # Ensure rate limit delay
                now = datetime.now()
                time_since_last_request = (now - self.last_request_time).total_seconds()
                if time_since_last_request < self.rate_limit_delay:
                    await asyncio.sleep(self.rate_limit_delay - time_since_last_request)

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as response:
                        self.last_request_time = datetime.now()

                        if response.status == 200:
                            return await response.json()
                        elif response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', self.rate_limit_delay * 2))
                            logger.warning(f"Rate limit hit, waiting {retry_after} seconds")
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            error_msg = f"Error: {response.status}"
                            logger.error(error_msg)
                            raise Exception(error_msg)

            except aiohttp.ClientError as e:
                if attempt == self.max_retries - 1:
                    raise
                logger.warning(f"Request failed, attempt {attempt + 1} of {self.max_retries}: {str(e)}")
                await asyncio.sleep(self.rate_limit_delay * (attempt + 1))

        raise Exception(f"Failed after {self.max_retries} attempts")

    async def fetch_market_rankings(self, limit: int = 10) -> List[str]:
        """
        Fetch top cryptocurrencies by market cap from CoinGecko
        """
        try:
            url = f"{self.coingecko_api}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',
                'per_page': str(limit),
                'page': '1',
                'sparkline': 'false'
            }
            
            data = await self._make_request(url, params)
            return [coin['symbol'].upper() for coin in data]
                    
        except Exception as e:
            logger.error(f"Error in fetch_market_rankings: {str(e)}")
            raise

    async def fetch_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch market data for a specific cryptocurrency
        """
        try:
            # Convert symbol to lowercase for CoinGecko API
            symbol_lower = symbol.lower()
            url = f"{self.coingecko_api}/simple/price"
            params = {
                'ids': symbol_lower,
                'vs_currencies': 'usd',
                'include_24hr_vol': 'true',
                'include_24hr_change': 'true',
                'include_market_cap': 'true'
            }
            
            data = await self._make_request(url, params)
            return data.get(symbol_lower, {})
                    
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {str(e)}")
            raise

    async def fetch_news_data(self, symbol: str) -> List[Dict]:
        """
        Fetch recent news data for a specific cryptocurrency
        """
        try:
            # Implement news fetching logic here
            # This is a placeholder that returns empty list
            return []
            
        except Exception as e:
            logger.error(f"Error fetching news data for {symbol}: {str(e)}")
            raise

    def _calculate_volatility(self, market_data: Dict) -> float:
        """
        Calculate volatility from market data
        Returns a value between 0 and 1
        """
        try:
            if 'usd_24h_change' in market_data:
                # Convert percentage to decimal and normalize
                return abs(market_data['usd_24h_change']) / 100
            return 0.5  # Default medium volatility if data not available
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {str(e)}")
            return 0.5  # Default to medium volatility on error