import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class APIConfig:
    def __init__(self):
        # Existing API keys
        self.openai_key = os.getenv('OPENAI_API_KEY')
        
        # Bybit demo credentials
        self.bybit_demo_key = os.getenv('BYBIT_DEMO_API_KEY')
        self.bybit_demo_secret = os.getenv('BYBIT_DEMO_API_SECRET')
        
        # Validate required credentials
        self._validate_credentials()
    
    def _validate_credentials(self):
        """Validate that all required API credentials are present"""
        required_credentials = {
            'OPENAI_API_KEY': self.openai_key,
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