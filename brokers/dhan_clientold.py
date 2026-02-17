import json
from dhanhq import dhanhq
from config.settings import client_id, access_token
from utils.logger import get_logger

logger = get_logger(__name__)


class BrokerClient:
    """API wrapper for DHAN with detailed logging and safe parsing."""

    def __init__(self):
        try:
            self.dhan = dhanhq(client_id, access_token)
            logger.info("Broker client initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing broker client: {e}", exc_info=True)
            raise

    def log_api_call(self, api_name, response):
        """Logs API name and response safely."""
        try:
            logger.info(f"API Call: {api_name} | Response: {json.dumps(response, indent=2)}")
        except Exception:
            logger.info(f"API Call: {api_name} | Response (raw): {response}")

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

    def get_ltp(self, exchange, security_id):
        """Fetch last traded price for given instrument."""
        api_name = f"get_ltp_{security_id}"
        try:
            data = self.dhan.ohlc_data({exchange: [security_id]})
            self.log_api_call(api_name, data)

            # SDK usually returns dict {exchange: [{...}]}
            if not data or exchange not in data:
                logger.warning(f"{api_name}: No data returned")
                return None

            ltp = data[exchange][0].get("last_price")
            logger.info(f"LTP for {security_id} => {ltp}")
            return ltp
        except Exception as e:
            logger.error(f"{api_name} error: {e}", exc_info=True)
            return None

    def place_order(
        self,
        security_id,
        exchange,
        qty,
        txn_type,
        product_type="INTRA",
        order_type="MARKET",
        price=0,
    ):
        """Place an order on DHAN."""
        api_name = f"place_order_{security_id}"
        try:
            order = self.dhan.place_order(
                security_id=security_id,
                exchange_segment=getattr(self.dhan, exchange),
                transaction_type=getattr(self.dhan, txn_type),
                quantity=qty,
                order_type=getattr(self.dhan, order_type),
                product_type=getattr(self.dhan, product_type),
                price=price,
            )
            self.log_api_call(api_name, order)
            logger.info(f"Order placed successfully: {order}")
            return order
        except Exception as e:
            logger.error(f"{api_name} error: {e}", exc_info=True)
            return None
