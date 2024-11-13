import asyncio
import logging
from datetime import datetime, timedelta
from .config import APIConfig
from .agents import CryptoAnalysisAgents
from typing import Dict
import signal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def format_trading_report(report: Dict) -> str:
    """Format the trading report into a readable string"""
    if 'error' in report:
        return f"Error generating report: {report['error']}"

    performance = report['performance_metrics']
    
    summary = [
        "\n=== Trading Session Summary ===",
        f"\nTotal Trades Analyzed: {report['total_trades']}",
        f"Successful Trade Executions: {report['successful_trades']} ({performance['success_rate']:.1f}%)",
        f"Profitable Trades: {report['profit_trades']} ({performance['profit_rate']:.1f}%)",
        f"Total Profit/Loss: ${report['total_profit_loss']:.2f}",
        f"Average Profit per Trade: ${performance['average_profit_per_trade']:.2f}",
        "\nDetailed Trade History:",
    ]

    for trade in report['trade_history']:
        analysis = trade.get('analysis_factors', {})
        summary.append(
            f"\n- {trade['symbol']} ({trade['timestamp']}): "
            f"Action: {trade['action'].upper()}, "
            f"Confidence: {trade['confidence']:.2%}, "
            f"Risk Level: {trade['risk_level']}, "
            f"Profit/Loss: ${trade.get('profit', 0):.2f}"
        )
        if analysis:
            summary.append(f"  Analysis Factors: {', '.join(f'{k}: {v}' for k, v in analysis.items())}")

    return "\n".join(summary)

class TradingSession:
    def __init__(self, analyzer: CryptoAnalysisAgents):
        self.analyzer = analyzer
        self.is_running = True
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal. Stopping trading session...")
        self.stop()

    def stop(self):
        """Stop the trading session"""
        self.is_running = False

    async def cleanup(self):
        """Cleanup resources"""
        try:
            # Cancel any pending orders
            active_orders = self.analyzer.trading_client.get_active_orders()
            for order_id in active_orders:
                if active_orders[order_id]['status'] == 'ACTIVE':
                    await self.analyzer.trading_client.cancel_order(order_id)
            
            # Close any open sessions
            if hasattr(self.analyzer.data_fetcher, 'close'):
                await self.analyzer.data_fetcher.close()
            
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

async def main():
    config = APIConfig()
    analyzer = CryptoAnalysisAgents(config)
    session = TradingSession(analyzer)

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
        while datetime.now() < end_time and session.is_running:
            try:
                report = await analyzer.execute_trading_strategy(risk_level, leverage_amount)
                logger.info(f"Strategy execution completed: {report}")
                
                # Wait for next iteration or until end time
                wait_time = min(300, (end_time - datetime.now()).total_seconds())
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Error in trading strategy: {str(e)}")
                if datetime.now() < end_time:
                    await asyncio.sleep(60)  # Wait before retrying

        # Trading session ended - cleanup and report
        logger.info("Trading session completed. Generating final report...")
        
        # Stop trading and cleanup
        session.stop()
        await session.cleanup()
        
        # Generate and display final report
        final_report = analyzer.generate_final_report()
        formatted_report = format_trading_report(final_report)
        print(formatted_report)
        
        # Log report to file
        logging.info("Final Trading Report:\n%s", formatted_report)
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        await session.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
