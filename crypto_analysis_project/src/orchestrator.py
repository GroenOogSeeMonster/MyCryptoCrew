import logging
from datetime import datetime
from typing import Dict, List
from .config import APIConfig
from .data_fetcher import CryptoDataFetcher
from .agents import CryptoAnalysisAgents
from .trader import BybitDemoTrader

logger = logging.getLogger(__name__)

class CryptoAnalysisOrchestrator:
    def __init__(self):
        self.config = APIConfig()
        self.data_fetcher = CryptoDataFetcher(self.config)
        self.agents = CryptoAnalysisAgents(self.config)
        self.trader = BybitDemoTrader(self.config)
        
    async def analyze_cryptocurrencies(self, crypto_list: List[str]) -> Dict:
        results = {}
        for crypto in crypto_list:
            data = self.data_fetcher.fetch_crypto_data(crypto)
            analysis = await self.agents.analyze_crypto(crypto, data)
            trade_result = self.trader.execute_demo_trade(crypto, analysis)
            
            results[crypto] = {
                "data": data,
                "analysis": analysis,
                "trade_result": trade_result
            }
            
        return results

    def generate_report(self, results: Dict) -> str:
        report = ["# Cryptocurrency Analysis Report\n"]
        report.append(f"Generated at: {datetime.now().isoformat()}\n")
        
        for crypto, data in results.items():
            report.append(f"## {crypto} Analysis\n")
            report.append("### Technical Analysis\n")
            report.append(f"```\n{data['analysis']['technical']}\n```\n")
            # Add other sections...
            
        return "\n".join(report) 