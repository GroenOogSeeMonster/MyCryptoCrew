import asyncio
import logging
from .config import APIConfig
from .agents import CryptoAnalysisAgents

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    config = APIConfig()
    analyzer = CryptoAnalysisAgents(config)
    
    # Run continuous trading strategy
    while True:
        try:
            report = await analyzer.execute_trading_strategy()
            logger.info(f"Strategy execution completed: {report}")
            
            # Wait for next iteration
            await asyncio.sleep(300)  # Run every 5 minutes
            
        except Exception as e:
            logger.error(f"Error in trading strategy: {str(e)}")
            await asyncio.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}") 