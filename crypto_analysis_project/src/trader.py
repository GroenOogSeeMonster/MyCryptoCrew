import logging
from typing import Dict
from pybit.unified_trading import HTTP
from .config import APIConfig

logger = logging.getLogger(__name__)

class BybitDemoTrader:
    def __init__(self, config: APIConfig):
        self.session = HTTP(
            testnet=True,
            api_key=config.bybit_key,
            api_secret=config.bybit_secret
        )

    def execute_demo_trade(self, crypto: str, analysis: Dict) -> Dict:
        try:
            # Example demo trade
            order = self.session.place_order(
                category="spot",
                symbol=f"{crypto}USDT",
                side="Buy",
                orderType="Limit",
                qty="0.001",
                price="30000"
            )
            return {"status": "success", "order": order}
        except Exception as e:
            logger.error(f"Demo trading error: {e}")
            return {"status": "error", "message": str(e)} 