import json
from datetime import datetime
from dhanhq import dhanhq
from brokers.base_client import BaseBrokerClient
from config.TradeFriendSettings import client_id, access_token
from utils.logger import get_logger, get_order_logger

logger = get_logger(__name__)
order_logger = get_order_logger()

class DhanClient(BaseBrokerClient):
    def __init__(self):
        """
        Initialize Dhan client using credentials from settings.py
        """
        try:
            self.dhan = dhanhq(client_id, access_token)
            logger.info("Dhan broker client initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing Dhan client: {e}", exc_info=True)
            raise

    # ---------------------------------------------------------
    # ORDER FUNCTIONS
    # ---------------------------------------------------------
    # --------------------------------------------------
    # GENERIC PLACE ORDER
    # --------------------------------------------------
    def place_order(
        self,
        security_id: str,
        exchange_segment: str,
        transaction_type: str,
        quantity: int,
        order_type: str,
        product_type: str,
        price: float = 0,
        trigger_price: float = 0,
        disclosed_quantity: int = 0,
        after_market_order: bool = False,
        validity: str = "DAY",
        amo_time: str = "OPEN",
        bo_profit_value=None,
        bo_stop_loss_Value=None,
        tag: str = None
    ) -> bool:

        try:
            payload = {
                "security_id": security_id,
                "exchange_segment": exchange_segment,
                "transaction_type": transaction_type,
                "quantity": quantity,
                "order_type": order_type,
                "product_type": product_type,
                "price": price,
                "trigger_price": trigger_price,
                "disclosed_quantity": disclosed_quantity,
                "after_market_order": after_market_order,
                "validity": validity,
                "amo_time": amo_time,
                "bo_profit_value": bo_profit_value,
                "bo_stop_loss_Value": bo_stop_loss_Value,
                "tag": tag
            }

            logger.info(
                f"[{datetime.now().isoformat()}] "
                f"📤 DHAN REQUEST → {payload}"
            )

            response = self.dhan.place_order(**payload)

            logger.info(
                f"[{datetime.now().isoformat()}] "
                f"📥 DHAN RESPONSE → {response}"
            )

            if response and isinstance(response, dict):
                status = response.get("status")
                if status == "success":
                    return True

            return False

        except Exception:
            logger.exception("❌ Dhan SDK place_order failed")
            return False
    # ---------------------------------------------------------
    # HOLDINGS
    # ---------------------------------------------------------
    def get_holdings(self):
        """Fetch and return holdings safely."""
        try:
            response = self.dhan.get_holdings()
            logger.debug(f"Raw holdings API response: {response}")

            if not response or not isinstance(response, dict):
                logger.warning("Holdings API returned empty or invalid response.")
                return []

            holdings = response.get("data", [])
            if not holdings:
                logger.info("Holdings list is empty.")
                return []

            logger.info(f"Fetched {len(holdings)} holdings from API.")
            return holdings

        except Exception as e:
            logger.error(f"get_holdings error: {e}", exc_info=True)
            return []
