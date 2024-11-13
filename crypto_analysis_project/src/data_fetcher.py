import aiohttp
import logging
from typing import List, Dict, Any
import json
import asyncio
from datetime import datetime, timedelta
from aiohttp import TCPConnector
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class CryptoDataFetcher:
    def __init__(self, config):
        self.config = config
        self.coingecko_api = "https://api.coingecko.com/api/v3"
        self.last_request_time = datetime.now()
        self.rate_limit_delay = 1.5
        self.max_retries = 3
        self._session = None
        self._connector = None
        self._lock = asyncio.Lock()

    @property
    async def session(self):
        """Get or create session with lock protection"""
        async with self._lock:
            if self._session is None or self._session.closed:
                if self._connector is not None:
                    await self._connector.close()
                self._connector = TCPConnector(limit=10, force_close=True)
                self._session = aiohttp.ClientSession(connector=self._connector)
            return self._session

    async def close(self):
        """Close session and connector"""
        async with self._lock:
            if self._session and not self._session.closed:
                await self._session.close()
            if self._connector is not None:
                await self._connector.close()
            self._session = None
            self._connector = None

    @asynccontextmanager
    async def get_session(self):
        """Context manager for session handling"""
        try:
            session = await self.session
            yield session
        except Exception as e:
            logger.error(f"Session error: {str(e)}")
            await self.close()
            raise
    
    async def _make_request(self, url: str, params: Dict) -> Dict:
        """Make API request with rate limiting and retry logic"""
        for attempt in range(self.max_retries):
            try:
                # Ensure rate limit delay
                now = datetime.now()
                time_since_last_request = (now - self.last_request_time).total_seconds()
                if time_since_last_request < self.rate_limit_delay:
                    await asyncio.sleep(self.rate_limit_delay - time_since_last_request)

                async with self.get_session() as session:
                    async with session.get(url, params=params, timeout=30) as response:
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

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Request failed, attempt {attempt + 1} of {self.max_retries}: {str(e)}")
                await self.close()  # Close the failed session
                if attempt == self.max_retries - 1:
                    raise Exception("Connection error.")
                await asyncio.sleep(self.rate_limit_delay * (attempt + 1))

        raise Exception(f"Failed after {self.max_retries} attempts")

    async def fetch_market_rankings(self, limit: int = 10) -> List[str]:
        """Fetch top cryptocurrencies by market cap"""
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
        """Fetch market data for a specific cryptocurrency"""
        try:
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
        Using CryptoCompare News API as an example
        """
        try:
            url = f"{self.coingecko_api}/coins/{symbol.lower()}/status_updates"
            params = {
                'per_page': '10',
                'page': '1'
            }
            
            try:
                data = await self._make_request(url, params)
                return data.get('status_updates', [])
            except Exception:
                # If status updates fail, return empty list rather than failing
                logger.warning(f"Could not fetch news data for {symbol}, continuing without news")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching news data for {symbol}: {str(e)}")
            return []  # Return empty list on error to not break the analysis

    async def __aenter__(self):
        """Async context manager entry"""
        await self.session
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

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