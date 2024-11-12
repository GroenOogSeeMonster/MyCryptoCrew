import os
from dotenv import load_dotenv

load_dotenv()

class APIConfig:
    def __init__(self):
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.bybit_key = os.getenv('BYBIT_API_KEY')
        self.bybit_secret = os.getenv('BYBIT_API_SECRET')
        self.coingecko_base_url = "https://api.coingecko.com/api/v3"
        
        if not all([self.openai_key, self.bybit_key, self.bybit_secret]):
            raise ValueError("Missing required API keys in environment variables")