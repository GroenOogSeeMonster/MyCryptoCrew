import asyncio
import logging
from .orchestrator import CryptoAnalysisOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    cryptocurrencies = ['bitcoin', 'ethereum', 'cardano', 'polkadot']
    orchestrator = CryptoAnalysisOrchestrator()
    
    try:
        results = await orchestrator.analyze_cryptocurrencies(cryptocurrencies)
        report = orchestrator.generate_report(results)
        
        with open("reports/crypto_analysis_report.md", "w") as f:
            f.write(report)
            
        logger.info("Analysis complete. Report generated: reports/crypto_analysis_report.md")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 