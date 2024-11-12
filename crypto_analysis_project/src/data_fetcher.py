import logging
from typing import Dict
import requests
from .config import APIConfig
import time
from tenacity import retry, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)

class CryptoDataFetcher:
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(3)
    )
    async def fetch_market_data(self, symbol: str):
        """Fetch market data for a given symbol"""
        try:
            response = self.session.get(
                f"{self.config.coingecko_base_url}/simple/price",
                params={
                    "ids": symbol,
                    "vs_currencies": "usd",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true",
                }
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            raise

    async def fetch_news_data(self, symbol: str):
        """Fetch news data for a given symbol"""
        # Implement news fetching logic here
        return []  # Placeholder return

    def __init__(self, config: APIConfig):
        self.config = config
        self.session = requests.Session()

    def fetch_crypto_data(self, crypto_id: str) -> Dict:
        try:
            response = self.session.get(
                f"{self.config.coingecko_base_url}/coins/{crypto_id}"
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching data for {crypto_id}: {e}")
            return {} 