"""
===============================================================================
TradeFriendAngelOrderAdapter
===============================================================================
"""

from core.TradeFriendDataProvider import TradeFriendDataProvider
from models.tradefriend_execution_result import TradeFriendExecutionResult
from utils.logger import get_brokerorder_logger
from db.TradeFriendStocMasterRepo import TradeFriendStocMasterRepo
from brokers.angel_orderclient import init_client


class TradeFriendAngelOrderAdapter:

    # ==========================================================================
    def __init__(self):
        self.logger = get_brokerorder_logger()
        self.stockmaster_repo = TradeFriendStocMasterRepo()
        self.client = init_client()
        self.data_provider = TradeFriendDataProvider()

        self.logger.info("Angel Order Adapter initialized")

    # ==========================================================================
    # SYMBOL RESOLUTION
    # ==========================================================================
    def _resolve_symbol(self, symbol: str):

        try:
            rows = self.stockmaster_repo.get_active_symbols()

            for row in rows:
                if row["symbol"] == symbol:
                    self.logger.info(
                        f"✅ Symbol resolved | {symbol} | Token: {row['token']}"
                    )
                    return {
                        "symbol": row["symbol"],
                        "trading_symbol": row["trading_symbol"],
                        "token": row["token"],
                        "exchange": "NSE"
                    }

            self.logger.error(f"❌ Symbol not found in StockMaster: {symbol}")
            return None

        except Exception as e:
            self.logger.exception(
                f"❌ Symbol resolution failed for {symbol} | Error: {e}"
            )
            return None

    # ==========================================================================
    # PLACE ORDER
    # ==========================================================================
    def place_order(self, order_request) -> TradeFriendExecutionResult:

        try:
            self.logger.info(
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
            product_type = getattr(order_request, "product_type", "INTRADAY")
            tag = getattr(order_request, "tag", None)

            # ----------------------------------------------------------
            # PAPER MODE
            # ----------------------------------------------------------
            if order_mode == "PAPER":
                self.logger.info(f"📝 PAPER ORDER simulated | {symbol}")

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
            angel_payload = {
                "variety": "NORMAL",
                "tradingsymbol": trading_symbol,
                "symboltoken": token,
                "transactiontype": side,
                "exchange": exchange,
                "ordertype": order_type,
                "producttype": product_type,
                "duration": "DAY",
                "quantity": quantity
            }

            if order_type == "LIMIT":
                angel_payload["price"] = order_request.price

            if tag:
                angel_payload["tag"] = tag

            self.logger.info(f"📦 Angel Payload → {angel_payload}")

            # ----------------------------------------------------------
            # Broker Call
            # ----------------------------------------------------------
            order_id = self.client.place_order(angel_payload)

            self.logger.info(f"✅ Angel Order Placed | OrderID={order_id}")

            return TradeFriendExecutionResult(
                success=True,
                broker_order_id=order_id,
                error=None
            )

        except Exception as e:

            self.logger.error(
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