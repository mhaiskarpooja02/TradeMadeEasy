# Servieces/TradeFriendOrderManagementService.py

from utils.logger import get_logger
from db.TradeFriendBrokerTradeRepo import TradeFriendBrokerTradeRepo
from db.TradeFriendOrderAuditRepo import TradeFriendOrderAuditRepo
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendOrderConfigRepo import TradeFriendOrderConfigRepo

from brokers.tradefriend_dhan_order_adapter import TradeFriendDhanOrderAdapter
from brokers.tradefriend_angel_order_adapter import TradeFriendAngelOrderAdapter

logger = get_logger(__name__)


class TradeFriendOrderManagementService:
    """
    ENTERPRISE ENTRY OMS

    Responsibilities:
    - Execute ENTRY orders only
    - Maintain broker_trade table
    - Maintain order_audit table
    - Paper + Live symmetry
    - Idempotent safe execution
    - PnL agnostic
    """

    def __init__(self):
        self.broker_repo = TradeFriendBrokerTradeRepo()
        self.audit_repo = TradeFriendOrderAuditRepo()
        self.trade_repo = TradeFriendTradeRepo()
        self.config_repo = TradeFriendOrderConfigRepo()

        self.brokers = {
            "ANGEL": TradeFriendAngelOrderAdapter(),
            "DHAN": TradeFriendDhanOrderAdapter()
        }

    # =====================================================
    # PUBLIC ENTRY METHOD
    # =====================================================
    def place_entry_order(
        self,
        trade_id: int,
        symbol: str,
        qty: int,
        side: str,
        price: float
    ) -> list[dict]:

        logger.info(
            f"🚀 ENTRY OMS | trade_id={trade_id} | symbol={symbol} | qty={qty}"
        )

        executions: list[dict] = []

        # =====================================================
        # 1️⃣ STATE GUARD
        # =====================================================
        trade = self.trade_repo.fetch_by_id(trade_id)
        if not trade:
            logger.error(f"ENTRY OMS → Trade not found: {trade_id}")
            return executions

        if trade.get("status") not in ("PENDING", "ENTRY_IN_PROGRESS"):
            logger.warning(
                f"⏭ ENTRY BLOCKED | trade_id={trade_id} | status={trade.get('status')}"
            )
            return executions

        # =====================================================
        # 2️⃣ IDEMPOTENCY CHECK
        # Prevent duplicate entries
        # =====================================================
        existing_positions = self.broker_repo.fetch_active_positions(trade_id)
        if existing_positions:
            logger.warning(
                f"⚠ ENTRY SKIPPED | trade_id={trade_id} already has active broker position"
            )
            return executions

        # =====================================================
        # 3️⃣ MODE RESOLUTION
        # =====================================================
        cfg = self.config_repo.get()
        order_mode = cfg["order_mode"]  # PAPER or LIVE

        # =====================================================
        # 4️⃣ AUDIT ATTEMPT (OMS LEVEL)
        # =====================================================
        audit_id = self.audit_repo.log_attempt(
            trade_id=trade_id,
            symbol=symbol,
            broker="ENTRY_OMS",
            order_mode=order_mode,
            side=side,
            qty=qty,
            order_type="MARKET",
            request_payload={
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "price": price
            }
        )

        # =====================================================
        # 5️⃣ PAPER MODE
        # =====================================================
        if order_mode == "PAPER":
            try:
                broker_trade_id = self.broker_repo.insert_broker_trade(
                    trade_id=trade_id,
                    broker="PAPER",
                    order_mode="PAPER",
                    symbol=symbol,
                    leg_type="ENTRY",
                    side=side,
                    qty=qty,
                    order_type="MARKET",
                    request_payload={
                        "symbol": symbol,
                        "qty": qty,
                        "side": side,
                        "price": price
                    }
                )

                broker_order_id = f"PAPER-{broker_trade_id}"

                self.broker_repo.update_broker_trade_success(
                    broker_trade_id=broker_trade_id,
                    broker_order_id=broker_order_id,
                    response_payload={
                        "filled_qty": qty,
                        "avg_price": price
                    }
                )

                executions.append({
                    "broker": "PAPER",
                    "broker_trade_id": broker_trade_id,
                    "filled_qty": qty,
                    "avg_price": price,
                    "broker_order_id": broker_order_id
                })

                self.audit_repo.log_result(
                    audit_id=audit_id,
                    status="SUCCESS",
                    response_payload={
                        "mode": "PAPER",
                        "broker_order_id": broker_order_id
                    }
                )

                return executions

            except Exception as e:
                logger.error(f"PAPER ENTRY FAILED | {symbol} → {e}")
                self.audit_repo.log_result(
                    audit_id=audit_id,
                    status="FAILED",
                    error_message=str(e)
                )
                return executions

        # =====================================================
        # 6️⃣ LIVE MODE
        # =====================================================
        success = False

        for broker_name, adapter in self.brokers.items():

            if not adapter.is_enabled():
                continue

            broker_trade_id = self.broker_repo.insert_broker_trade(
                trade_id=trade_id,
                broker=broker_name,
                order_mode="LIVE",
                symbol=symbol,
                leg_type="ENTRY",
                side=side,
                qty=qty,
                order_type="MARKET"
            )

            try:
                order = adapter.place_order(symbol, qty, side)

                if not order or not order.get("order_id"):
                    raise Exception("Broker rejected order")

                fill = adapter.wait_for_fill(order["order_id"])

                self.broker_repo.update_broker_trade_success(
                    broker_trade_id=broker_trade_id,
                    broker_order_id=order["order_id"],
                    response_payload=fill
                )

                executions.append({
                    "broker": broker_name,
                    "broker_trade_id": broker_trade_id,
                    "filled_qty": fill["filled_qty"],
                    "avg_price": fill["avg_price"],
                    "broker_order_id": order["order_id"]
                })

                success = True
                break

            except Exception as e:
                logger.error(f"[{broker_name} ENTRY FAILED] {symbol} → {e}")
                self.broker_repo.update_broker_trade_failure(
                    broker_trade_id,
                    str(e)
                )

        # =====================================================
        # 7️⃣ AUDIT RESULT
        # =====================================================
        if success:
            self.audit_repo.log_result(
                audit_id=audit_id,
                status="SUCCESS",
                response_payload={"executions": executions}
            )
        else:
            self.audit_repo.log_result(
                audit_id=audit_id,
                status="FAILED",
                error_message="All brokers failed"
            )

        return executions
