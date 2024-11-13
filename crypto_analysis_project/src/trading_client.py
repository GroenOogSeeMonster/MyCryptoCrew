import logging
from typing import Dict, Optional
from pybit.unified_trading import HTTP
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class BybitDemoClient:
    def __init__(self, api_key: str, api_secret: str):
        """Initialize Bybit demo trading client"""
        self.client = HTTP(
            testnet=True,  # Use testnet for demo trading
            api_key=api_key,
            api_secret=api_secret
        )
        self.active_orders = {}

    async def create_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict:
        """
        Place a new order on Bybit demo account
        """
        try:
            # Create the main order
            order_params = {
                "category": "spot",
                "symbol": symbol,
                "side": side,
                "orderType": "Limit",
                "qty": str(quantity),
                "price": str(price),
                "timeInForce": "GTC",
            }

            response = self.client.place_order(**order_params)
            
            if response["retCode"] == 0:
                order_id = response["result"]["orderId"]
                self.active_orders[order_id] = {
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "price": price,
                    "status": "ACTIVE",
                    "timestamp": datetime.now().isoformat()
                }

                # Place stop loss if specified
                if stop_loss:
                    self._place_stop_loss(symbol, side, quantity, stop_loss, order_id)

                # Place take profit if specified
                if take_profit:
                    self._place_take_profit(symbol, side, quantity, take_profit, order_id)

                logger.info(f"Successfully placed order: {order_id}")
                return self.active_orders[order_id]
            else:
                logger.error(f"Failed to place order: {response}")
                raise Exception(f"Order placement failed: {response['retMsg']}")

        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            raise

    def _place_stop_loss(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        parent_order_id: str
    ):
        """Place a stop loss order"""
        try:
            stop_side = "Sell" if side == "Buy" else "Buy"
            stop_params = {
                "category": "spot",
                "symbol": symbol,
                "side": stop_side,
                "orderType": "StopLimit",
                "qty": str(quantity),
                "stopPrice": str(stop_price),
                "price": str(stop_price),  # Trigger price same as stop price
                "timeInForce": "GTC",
            }
            
            response = self.client.place_order(**stop_params)
            
            if response["retCode"] == 0:
                stop_loss_id = response["result"]["orderId"]
                self.active_orders[parent_order_id]["stop_loss_id"] = stop_loss_id
                logger.info(f"Successfully placed stop loss order: {stop_loss_id}")
            else:
                logger.error(f"Failed to place stop loss order: {response}")
                raise Exception(f"Stop loss placement failed: {response['retMsg']}")

        except Exception as e:
            logger.error(f"Error placing stop loss order: {str(e)}")
            raise

    def _place_take_profit(
        self,
        symbol: str,
        side: str,
        quantity: float,
        take_price: float,
        parent_order_id: str
    ):
        """Place a take profit order"""
        try:
            take_side = "Sell" if side == "Buy" else "Buy"
            take_params = {
                "category": "spot",
                "symbol": symbol,
                "side": take_side,
                "orderType": "Limit",
                "qty": str(quantity),
                "price": str(take_price),
                "timeInForce": "GTC",
            }
            
            response = self.client.place_order(**take_params)
            
            if response["retCode"] == 0:
                take_profit_id = response["result"]["orderId"]
                self.active_orders[parent_order_id]["take_profit_id"] = take_profit_id
                logger.info(f"Successfully placed take profit order: {take_profit_id}")
            else:
                logger.error(f"Failed to place take profit order: {response}")
                raise Exception(f"Take profit placement failed: {response['retMsg']}")

        except Exception as e:
            logger.error(f"Error placing take profit order: {str(e)}")
            raise 