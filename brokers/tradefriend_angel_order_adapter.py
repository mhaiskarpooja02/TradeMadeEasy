# brokers/tradefriend_angel_order_adapter.py

import logging
import pyotp
from SmartApi import SmartConnect

from config.TradeFriendSettings import api_key, username, pin, totp_qr
from db.TradeFriendinstrument_db import TradeFindDB

logger = logging.getLogger(__name__)


class TradeFriendAngelOrderAdapter:
    """
    PURPOSE:
    - Place LIVE orders via AngelOne SmartAPI
    - NSE Equity only
    - Token resolution strictly from TradeFindDB
    - OMS-compatible adapter
    """

    EXCHANGE = "NSE"
    VARIETY = "NORMAL"
    DEFAULT_PRODUCT = "INTRADAY"
    DEFAULT_ORDER_TYPE = "MARKET"
    DURATION = "DAY"

    def __init__(self):
        self.client = None
        self.instrument_repo = TradeFindDB()
        self._login()

    # --------------------------------------------------
    # LOGIN
    # --------------------------------------------------
    def _login(self):
        try:
            smart = SmartConnect(api_key)
            totp = pyotp.TOTP(totp_qr).now()

            data = smart.generateSession(username, pin, totp)
            if not data.get("status"):
                raise Exception(data)

            smart.generateToken(data["data"]["refreshToken"])
            self.client = smart

            logger.info("✅ AngelOne login successful")

        except Exception:
            logger.exception("❌ AngelOne login failed")
            self.client = None

    # --------------------------------------------------
    # PLACE ORDER (OMS ENTRY POINT)
    # --------------------------------------------------
    def place_order(self, order: dict) -> bool:
        """
        OMS-compatible order execution.

        Expected order format:
        {
            "symbol": "SBIN-EQ",
            "qty": 2,
            "side": "BUY",
            "order_type": "MARKET",   # optional
            "product": "INTRADAY"     # optional
        }
        """

        if not self.client:
            logger.error("Angel client not initialized")
            return False

        try:
            symbol = order["symbol"]
            qty = int(order["qty"])
            side = order["side"]

            if qty <= 0:
                raise ValueError(f"Invalid qty: {qty}")

            resolved = self.instrument_repo.resolve_active_symbol(symbol)
            if not resolved:
                raise Exception(f"Token not found in DB for {symbol}")

            params = {
                "variety": self.VARIETY,
                "tradingsymbol": resolved["symbol"],
                "symboltoken": resolved["token"],
                "transactiontype": side,
                "exchange": self.EXCHANGE,
                "ordertype": order.get("order_type", self.DEFAULT_ORDER_TYPE),
                "producttype": order.get("product", self.DEFAULT_PRODUCT),
                "duration": self.DURATION,
                "price": 0,
                "quantity": qty,
            }

            order_id = self.client.placeOrder(params)

            logger.info(
                f"✅ Angel order placed | "
                f"Symbol={symbol} | Qty={qty} | Side={side} | OrderID={order_id}"
            )
            return True

        except Exception:
            logger.exception("❌ Angel order failed")
            return False
