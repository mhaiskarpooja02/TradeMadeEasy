import logging

from brokers.tradefriend_broker_adapter import TradeFriendBrokerAdapter
from brokers.dhan_client import DhanClient
from models.tradefriend_order_models import TradeFriendOrderRequest
from models.tradefriend_execution_result import TradeFriendExecutionResult
from db.TradeFriendDhanInstrumentRepo import TradeFriendDhanInstrumentRepo

logger = logging.getLogger("broker_orders")


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

        try:
            # --------------------------------------------------
            # BASIC VALIDATION
            # --------------------------------------------------
            if order.qty <= 0:
                logger.warning(
                    f"⚠ DHAN Invalid quantity | Symbol={order.symbol} | Qty={order.qty}"
                )
                return TradeFriendExecutionResult.failure(
                    error="Invalid quantity"
                )

            if order.side not in ["BUY", "SELL"]:
                logger.warning(
                    f"⚠ DHAN Invalid side | {order.side}"
                )
                return TradeFriendExecutionResult.failure(
                    error="Invalid side"
                )

            # --------------------------------------------------
            # RESOLVE SECURITY
            # --------------------------------------------------
            instrument = self.instrument_repo.get_active(order.symbol)

            if not instrument:
                logger.error(
                    f"❌ DHAN Security not found | Symbol={order.symbol}"
                )
                return TradeFriendExecutionResult.failure(
                    error=f"Security not found for {order.symbol}"
                )

            security_id = instrument["security_id"]

            logger.info(
                f"📤 DHAN place_order | Symbol={order.symbol} | "
                f"SecurityID={security_id} | Qty={order.qty} | Side={order.side}"
            )

            # --------------------------------------------------
            # CALL DHAN CLIENT
            # --------------------------------------------------
            response = self.client.place_order(
                security_id=security_id,
                side=order.side,
                quantity=order.qty,
                exchange_segment=self.EXCHANGE,
                product_type=self.PRODUCT,
                order_type=self.ORDER_TYPE,
                tag=order.tag
            )

            logger.info(f"📨 DHAN Raw Response → {response}")

            # --------------------------------------------------
            # DEFENSIVE RESPONSE VALIDATION
            # --------------------------------------------------
            if response is None:
                raise Exception("Dhan returned None response")

            if not isinstance(response, dict):
                raise Exception(f"Unexpected Dhan response type: {type(response)}")

            success = response.get("success")

            if not success:
                error_msg = response.get("error") or response.get("message") or "Unknown Dhan error"
                raise Exception(error_msg)

            broker_order_id = response.get("broker_order_id")

            if not broker_order_id:
                raise Exception(f"Dhan response missing broker_order_id → {response}")

            # --------------------------------------------------
            # SUCCESS
            # --------------------------------------------------
            logger.info(
                f"✅ DHAN Order Placed | BrokerOrderID={broker_order_id}"
            )

            return TradeFriendExecutionResult.success(
                broker_order_id=broker_order_id,
                raw_response=response
            )

        except Exception as e:
            logger.exception(
                f"❌ DHAN ORDER FAILED | Symbol={order.symbol}"
            )

            return TradeFriendExecutionResult.failure(
                error=str(e)
            )