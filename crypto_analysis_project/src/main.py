import asyncio
import logging
from datetime import datetime, timedelta
from .config import APIConfig
from .agents import CryptoAnalysisAgents

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    config = APIConfig()
    analyzer = CryptoAnalysisAgents(config)

    # Prompt user for trading parameters
    try:
        trading_duration = int(input("Enter the trading duration in minutes: "))
        risk_level = input("Enter the risk level (low, med, high): ").lower()
        leverage_amount = float(input("Enter the amount to leverage from the account wallet (in USD): "))
        
        if risk_level not in ['low', 'med', 'high']:
            raise ValueError("Risk level must be 'low', 'med', or 'high'")
        if leverage_amount <= 0:
            raise ValueError("Leverage amount must be greater than 0")
            
    except ValueError as e:
        logger.error(f"Invalid input: {str(e)}")
        return

    # Set end time for trading
    end_time = datetime.now() + timedelta(minutes=trading_duration)
    
    logger.info(f"Starting trading session for {trading_duration} minutes with risk level '{risk_level}' and leverage amount ${leverage_amount}")

    try:
        # Run continuous trading strategy until end time
        while datetime.now() < end_time:
            try:
                report = await analyzer.execute_trading_strategy(risk_level, leverage_amount)
                logger.info(f"Strategy execution completed: {report}")
                
                # Wait for next iteration
                await asyncio.sleep(300)  # Run every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in trading strategy: {str(e)}")
                await asyncio.sleep(60)  # Wait before retrying

        # Trading session ended
        logger.info("Trading session completed. Generating final report...")
        final_report = analyzer.generate_final_report()
        logger.info(f"Final Trading Report: {final_report}")
        
    except KeyboardInterrupt:
        logger.info("Trading session interrupted by user. Generating final report...")
        final_report = analyzer.generate_final_report()
        logger.info(f"Final Trading Report: {final_report}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
