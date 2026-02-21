import logging

from brokers.tradefriend_broker_adapter import TradeFriendBrokerAdapter
from brokers.dhan_client import DhanClient
from models.tradefriend_order_models import TradeFriendOrderRequest
from models.tradefriend_execution_result import TradeFriendExecutionResult
from db.TradeFriendDhanInstrumentRepo import TradeFriendDhanInstrumentRepo

logger = logging.getLogger(__name__)


class TradeFriendDhanOrderAdapter(TradeFriendBrokerAdapter):

    BROKER_NAME = "DHAN"
    EXCHANGE = "NSE_EQ"
    PRODUCT = "INTRADAY"
    ORDER_TYPE = "MARKET"

    def __init__(self):
        self.client = DhanClient()
        self.instrument_repo = TradeFriendDhanInstrumentRepo()

    # --------------------------------------------------
    # PLACE ORDER
    # --------------------------------------------------
    def place_order(
        self,
        order: TradeFriendOrderRequest
    ) -> TradeFriendExecutionResult:

        if order.qty <= 0:
            return TradeFriendExecutionResult(
                success=False,
                broker_order_id=None,
                raw_response=None,
                error="Invalid quantity"
            )

        # Resolve security_id internally
        security_id = self.instrument_repo.resolve_security_id(order.symbol)

        if not security_id:
            return TradeFriendExecutionResult(
                success=False,
                broker_order_id=None,
                raw_response=None,
                error=f"Security ID not found for {order.symbol}"
            )

        try:
            logger.info(
                f"📤 DHAN ORDER | Symbol={order.symbol} | Qty={order.qty} | Side={order.side}"
            )

            result = self.client.place_order(
                security_id=security_id,
                side=order.side,
                quantity=order.qty,
                exchange_segment=self.EXCHANGE,
                product_type=self.PRODUCT,
                order_type=self.ORDER_TYPE,
                tag=order.tag
            )

            if not result.get("success"):
                return TradeFriendExecutionResult(
                    success=False,
                    broker_order_id=None,
                    raw_response=result,
                    error=result.get("error")
                )

            return TradeFriendExecutionResult(
                success=True,
                broker_order_id=result.get("broker_order_id"),
                raw_response=result.get("raw_response"),
                error=None
            )

        except Exception as e:
            logger.exception("❌ DHAN ORDER FAILED")

            return TradeFriendExecutionResult(
                success=False,
                broker_order_id=None,
                raw_response=None,
                error=str(e)
            )