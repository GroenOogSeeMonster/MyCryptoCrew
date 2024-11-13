import aiohttp
import logging
from typing import List, Dict, Any
import asyncio
from aiohttp import TCPConnector
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class CryptoDataFetcher:
    def __init__(self, config):
        self.config = config
        self.coinranking_api_url = "https://api.coinranking.com/v2"
        self.api_key = config.coinranking_api_key
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

    async def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make API request with retry logic"""
        for attempt in range(self.max_retries):
            try:
                headers = {
                    'x-access-token': self.api_key
                }
                async with self.get_session() as session:
                    async with session.get(f"{self.coinranking_api_url}{endpoint}", 
                                         headers=headers, 
                                         params=params, 
                                         timeout=30) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_msg = f"Error: {response.status}"
                            logger.error(error_msg)
                            raise Exception(error_msg)

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Request failed, attempt {attempt + 1} of {self.max_retries}: {str(e)}")
                await self.close()  # Close the failed session
                if attempt == self.max_retries - 1:
                    raise Exception("Connection error.")
                await asyncio.sleep(1 * (attempt + 1))

        raise Exception(f"Failed after {self.max_retries} attempts")

    async def fetch_market_rankings(self, limit: int = 10) -> List[Dict[str, str]]:
        """Fetch top cryptocurrencies by market cap and cache their UUIDs"""
        try:
            endpoint = "/coins"
            params = {
                'limit': limit
            }
            
            data = await self._make_request(endpoint, params)
            return [{'symbol': coin['symbol'].upper(), 'uuid': coin['uuid']} for coin in data['data']['coins']]
        except Exception as e:
            logger.error(f"Error in fetch_market_rankings: {str(e)}")
            raise

    async def fetch_market_data(self, uuid: str) -> Dict[str, Any]:
        """Fetch market data for a specific cryptocurrency"""
        try:
            endpoint = f"/coin/{uuid}"
            data = await self._make_request(endpoint)
            return data['data']['coin']
        except Exception as e:
            logger.error(f"Error fetching market data for UUID {uuid}: {str(e)}")
            raise

    async def fetch_news_data(self, symbol: str) -> List[Dict]:
        """Fetch recent news data for a specific cryptocurrency"""
        # CoinRanking does not directly provide news data, so this function might need adjustments or removal.
        return []  # Return empty list for now to avoid breaking the analysis

    async def __aenter__(self):
        """Async context manager entry"""
        await self.session
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
