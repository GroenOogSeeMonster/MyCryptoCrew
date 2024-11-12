import logging
from typing import Dict
import requests
from .config import APIConfig

logger = logging.getLogger(__name__)

class CryptoDataFetcher:
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