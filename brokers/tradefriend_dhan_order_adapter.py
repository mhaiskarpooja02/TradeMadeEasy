import logging

from brokers.dhan_client import DhanClient
from db.TradeFriendDhanInstrumentRepo import TradeFriendDhanInstrumentRepo
from db.TradeFriendOrderAuditRepo import TradeFriendOrderAuditRepo

logger = logging.getLogger(__name__)


class TradeFriendDhanOrderAdapter:
    """
    PURPOSE:
    - Place LIVE orders via Dhan
    - Resolve security_id via TradeFriendDhanInstrumentRepo
    - Record every attempt in TradeFriendOrderAuditRepo
    """

    BROKER_NAME = "DHAN"
    EXCHANGE = "NSE_EQ"
    PRODUCT = "INTRADAY"
    ORDER_TYPE = "MARKET"

    def __init__(self):
        self.client = DhanClient()
        self.instrument_repo = TradeFriendDhanInstrumentRepo()
        self.audit_repo = TradeFriendOrderAuditRepo()

    # --------------------------------------------------
    # PLACE ORDER (OMS ENTRY POINT)
    # --------------------------------------------------
    def place_order(
        self,
        trade_id: int,
        symbol: str,
        qty: int,
        side: str = "BUY",
        tag: str = None,
        order_mode: str = "LIVE"
    ) -> bool:
        """
        OMS-compatible execution.

        Args:
            trade_id (int): swing_trade id
            symbol (str): SBIN-EQ
            qty (int): quantity
            side (str): BUY (only)
            tag (str): correlation tag
            order_mode (str): LIVE / PAPER
        """

        if qty <= 0:
            logger.error(f"Invalid qty: {qty}")
            return False

        if side != "BUY":
            logger.error("Dhan adapter currently supports BUY only")
            return False

        # --------------------------------------------------
        # RESOLVE SECURITY ID
        # --------------------------------------------------
        security_id = self.instrument_repo.resolve_security_id(symbol)
        if not security_id:
            logger.error(f"Dhan security_id not found for {symbol}")
            return False

        # --------------------------------------------------
        # PREPARE REQUEST PAYLOAD (FOR AUDIT)
        # --------------------------------------------------
        request_payload = {
            "symbol": symbol,
            "security_id": security_id,
            "qty": qty,
            "side": side,
            "exchange_segment": self.EXCHANGE,
            "order_type": self.ORDER_TYPE,
            "product_type": self.PRODUCT,
            "tag": tag
        }

        # --------------------------------------------------
        # AUDIT: ATTEMPT
        # --------------------------------------------------
        audit_id = self.audit_repo.log_attempt(
            trade_id=trade_id,
            symbol=symbol,
            broker=self.BROKER_NAME,
            order_mode=order_mode,
            side=side,
            qty=qty,
            resolved_id=security_id,
            exchange=self.EXCHANGE,
            product=self.PRODUCT,
            order_type=self.ORDER_TYPE,
            request_payload=request_payload
        )

        # --------------------------------------------------
        # EXECUTE ORDER
        # --------------------------------------------------
        try:
            logger.info(
                f"📤 DHAN ORDER | Symbol={symbol} | Qty={qty} | SID={security_id}"
            )

            result = self.client.place_order(
                security_id=security_id,
                qty=qty,
                tag=tag
            )

            if not result:
                raise Exception("Dhan order rejected")

            # --------------------------------------------------
            # AUDIT: SUCCESS
            # --------------------------------------------------
            self.audit_repo.log_result(
                audit_id=audit_id,
                status="SUCCESS",
                response_payload={"status": "success"}
            )

            logger.info(
                f"✅ DHAN order placed | Symbol={symbol} | Qty={qty}"
            )
            return True

        except Exception as e:
            logger.exception("❌ DHAN order failed")

            # --------------------------------------------------
            # AUDIT: FAILURE
            # --------------------------------------------------
            self.audit_repo.log_result(
                audit_id=audit_id,
                status="FAILED",
                error_message=str(e)
            )
            return False
