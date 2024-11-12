import asyncio
import logging
from .config import APIConfig
from .agents import CryptoAnalysisAgents

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    config = APIConfig()
    analyzer = CryptoAnalysisAgents(config)
    result = await analyzer.analyze_crypto("bitcoin")
    print(result)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}") 