import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class SelectionConfig:
    def __init__(self):
        self.min_market_cap = 1000000  # $1M minimum market cap
        self.min_daily_volume = 100000  # $100K minimum daily volume
        self.max_volatility = 0.2  # 20% maximum volatility
        self.blacklist = set()  # Blacklisted symbols
        self.whitelist = set()  # Whitelisted symbols (if empty, all non-blacklisted are allowed)
        self.min_price = 0.1  # Minimum price in USD
        self.max_price = 100000  # Maximum price in USD
        self.min_market_maturity = 90  # Minimum days since listing

class APIConfig:
    def __init__(self):
        # Existing API keys
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.coinranking_api_key = os.getenv('COINRANKING_API_KEY')
        
        # Bybit demo credentials
        self.bybit_demo_key = os.getenv('BYBIT_DEMO_API_KEY')
        self.bybit_demo_secret = os.getenv('BYBIT_DEMO_API_SECRET')
        
        # Validate required credentials
        self._validate_credentials()
        
        # Selection criteria
        self.selection_config = SelectionConfig()
    
    def _validate_credentials(self):
        """Validate that all required API credentials are present"""
        required_credentials = {
            'OPENAI_API_KEY': self.openai_key,
            'COINRANKING_API_KEY': self.coinranking_api_key,
            'BYBIT_DEMO_API_KEY': self.bybit_demo_key,
            'BYBIT_DEMO_API_SECRET': self.bybit_demo_secret
        }
        
        missing_credentials = [
            key for key, value in required_credentials.items() 
            if not value
        ]
        
        if missing_credentials:
            raise ValueError(
                f"Missing required API credentials: {', '.join(missing_credentials)}"
            )