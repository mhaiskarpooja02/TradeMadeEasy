"""
===============================================================================
TradeFriendAngelOrderAdapter
===============================================================================
"""

from core.TradeFriendDataProvider import TradeFriendDataProvider
from models.tradefriend_execution_result import TradeFriendExecutionResult
from utils.logger import get_angel_rest_logger, get_brokerorder_logger
from db.TradeFriendStocMasterRepo import TradeFriendStocMasterRepo
from brokers.angel_orderclient import init_client
logger = get_angel_rest_logger()

class TradeFriendAngelOrderAdapter:

    # ==========================================================================
    def __init__(self):
        
        self.stockmaster_repo = TradeFriendStocMasterRepo()
        self.client = init_client()
        self.data_provider = TradeFriendDataProvider()

        logger.info("Angel Order Adapter initialized")

    # ==========================================================================
    # SYMBOL RESOLUTION
    # ==========================================================================
    def _resolve_symbol(self, symbol: str):

        try:
            rows = self.stockmaster_repo.get_active_symbols()

            for row in rows:
                if row["symbol"] == symbol:
                    logger.info("=" * 60)
                    logger.info("🔎 ANGEL SYMBOL RESOLUTION")
                    logger.info(f"Symbol          : {row['symbol']}")
                    logger.info(f"Trading Symbol  : {row['trading_symbol']}")
                    logger.info(f"Token           : {row['token']}")
                    logger.info(f"Exchange        : NSE")
                    logger.info("=" * 60)
                    return {
                        "symbol": row["symbol"],
                        "trading_symbol": row["trading_symbol"],
                        "token": row["token"],
                        "exchange": "NSE"
                    }

            logger.error(f"❌ Symbol not found in StockMaster: {symbol}")
            return None

        except Exception as e:
            logger.exception(
                f"❌ Symbol resolution failed for {symbol} | Error: {e}"
            )
            return None

    # ==========================================================================
    # PLACE ORDER
    # ==========================================================================
    def place_order(self, order_request) -> TradeFriendExecutionResult:

        try:
            logger.info(
                f"📤 Angel place_order | "
                f"trade_id={order_request.trade_id} | "
                f"symbol={order_request.symbol} | "
                f"qty={order_request.qty} | "
                f"side={order_request.side} | "
                f"mode={order_request.order_mode}"
            )

            symbol = order_request.symbol
            side = order_request.side
            quantity = order_request.qty
            order_mode = order_request.order_mode

            order_type = getattr(order_request, "order_type", "MARKET")
            product_type = getattr(order_request, "product_type", "DELIVERY")
            tag = getattr(order_request, "tag", None)

            # ----------------------------------------------------------
            # PAPER MODE
            # ----------------------------------------------------------
            if order_mode == "PAPER":
                logger.info(f"📝 PAPER ORDER simulated | {symbol}")

                return TradeFriendExecutionResult(
                    success=True,
                    broker_order_id="PAPER_ANGEL_ORDER",
                    error=None
                )

            # ----------------------------------------------------------
            # Resolve Symbol
            # ----------------------------------------------------------
            resolved = self._resolve_symbol(symbol)

            if not resolved:
                return TradeFriendExecutionResult(
                    success=False,
                    broker_order_id=None,
                    error=f"Symbol resolution failed for {symbol}"
                )

            token = resolved["token"]
            trading_symbol = resolved["trading_symbol"]
            exchange = resolved["exchange"]

            # ----------------------------------------------------------
            # Build Payload
            # ----------------------------------------------------------

            if "_" in trading_symbol:
                trading_symbol = trading_symbol.replace("_EQ", "-EQ")

            angel_payload = {
                "variety": "NORMAL",
                "tradingsymbol": trading_symbol,
                "symboltoken": token,
                "transactiontype": side,
                "exchange": exchange,
                "ordertype": order_type,
                "producttype": product_type,
                "duration": "DAY",
                "quantity": quantity,
                "disclosedquantity": 0,
                "scripconsent": "yes"
            }

            if order_type == "LIMIT":
                angel_payload["price"] = order_request.price

            if tag:
                angel_payload["tag"] = tag

            logger.info(f"📦 Angel Payload → {angel_payload}")

            # ----------------------------------------------------------
            # Broker Call
            # ----------------------------------------------------------
            # Place order
            response = self.client.place_order(angel_payload)
            
            order_id = response["order_id"]
            unique_id = response["unique_order_id"]

            logger.info(f"✅ Angel Order Placed | OrderID={order_id}")

            return TradeFriendExecutionResult(
                success=True,
                broker_order_id=order_id,
                unique_order_id=unique_id,
                error=None
            )

        except Exception as e:

            logger.error(
                f"❌ Angel Order FAILED | "
                f"trade_id={getattr(order_request, 'trade_id', None)} | "
                f"error={str(e)}",
                exc_info=True
            )

            return TradeFriendExecutionResult(
                success=False,
                broker_order_id=None,
                error=str(e)
            )

    # ==========================================================================
    def close(self):
        try:
            self.stockmaster_repo.close()
        except Exception:
            pass

    # ==========================================================================
    # ORDER STATUS FETCH (ABSTRACTION LAYER)
    # ==========================================================================
    def get_order_status(self, broker_order_id: str, broker_unique_id: str = None) -> dict:
        """
        Fetch order status from Angel
        Returns normalized structure
        Does NOT touch DB
        """

        try:
            if not broker_unique_id:
                raise Exception("Angel requires unique_order_id")

            logger.info(
                f"🔎 [ANGEL] Fetching order status | unique_id={broker_unique_id}"
            )

            response = self.client.get_order_status(broker_unique_id)

            if not response:
                raise Exception("Empty response from broker")

            raw_status = str(response.get("orderstatus", "")).lower()
            filled_qty = int(response.get("filledshares", 0) or 0)
            avg_price = float(response.get("averageprice", 0) or 0)
            rejection_reason = response.get("text", "")

            # ------------------------------
            # Normalize lifecycle
            # ------------------------------
            if raw_status == "complete":
                status = "COMPLETE"
            elif raw_status == "cancelled":
                status = "CANCELLED"
            elif raw_status == "rejected":
                status = "REJECTED"
            elif filled_qty > 0:
                status = "PARTIAL"
            else:
                status = "PLACED"

            logger.info(
                f"📊 [ANGEL] Status={status} | Filled={filled_qty} | Avg={avg_price}"
            )

            return {
                "status": status,
                "filled_qty": filled_qty,
                "avg_price": avg_price,
                "raw_status": raw_status,
                "rejection_reason": rejection_reason
            }

        except Exception as e:
            logger.error(
                f"❌ [ANGEL] Status fetch failed | "
                f"{broker_order_id} | {str(e)}"
            )
            raise