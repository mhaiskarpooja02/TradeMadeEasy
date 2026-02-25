# Servieces/TradeFriendExitOrderService.py

from datetime import datetime
from const.TradeFriendPlanStatus import TradeStatus

from utils.logger import get_order_logger

from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendTradeHistoryRepo import TradeFriendTradeHistoryRepo
from db.TradeFriendBrokerTradeRepo import TradeFriendBrokerTradeRepo
from db.TradeFriendOrderAuditRepo import TradeFriendOrderAuditRepo
from db.TradeFriendOrderConfigRepo import TradeFriendOrderConfigRepo
from db.TradeFriendRealizedPnLRepo import TradeFriendRealizedPnLRepo

from models.tradefriend_order_models import TradeFriendOrderRequest
from models.tradefriend_execution_result import TradeFriendExecutionResult

from core.tradefriend_broker_resolver import TradeFriendBrokerResolver

from brokers.tradefriend_dhan_order_adapter import TradeFriendDhanOrderAdapter
from brokers.tradefriend_angel_order_adapter import TradeFriendAngelOrderAdapter


logger = get_order_logger()


class TradeFriendExitOrderService:
    """
    ENTERPRISE EXIT OMS (Production Hardened)

    - Symmetric with Entry OMS
    - State guarded
    - Idempotent safe
    - Broker table aware
    - Partial fill safe
    - Full audit logging
    - Rollback safe
    """

    # =====================================================
    # INIT
    # =====================================================
    def __init__(self):

        logger.debug("🔧 EXIT OMS INITIALIZING")

        self.trade_repo = TradeFriendTradeRepo()
        self.history_repo = TradeFriendTradeHistoryRepo()
        self.broker_trade_repo = TradeFriendBrokerTradeRepo()
        self.audit_repo = TradeFriendOrderAuditRepo()
        self.config_repo = TradeFriendOrderConfigRepo()
        self.realized_repo = TradeFriendRealizedPnLRepo()

        self.brokers = {
            "ANGEL": TradeFriendAngelOrderAdapter(),
            "DHAN": TradeFriendDhanOrderAdapter()
        }

        self.resolver = TradeFriendBrokerResolver(self.config_repo)

        logger.debug(f"Exit brokers available → {list(self.brokers.keys())}")

    # ==================================================
    # FINALIZER
    # ==================================================
    def _finalize_exit(
        self,
        trade: dict,
        exit_qty: int,
        exit_reason: str,
        exit_price: float,
        order_mode: str,
        broker_order_id: str | None
    ):
    
        trade_id = trade["id"]
        symbol = trade["symbol"]
        entry_price = float(trade["entry"])
        remaining_qty = int(trade["remaining_qty"])
    
        logger.debug(
            f"Finalizing exit | trade_id={trade_id} | "
            f"exit_qty={exit_qty} | remaining_before={remaining_qty}"
        )
    
        # ===============================
        # 🟡 PARTIAL EXIT
        # ===============================
        if exit_qty < remaining_qty:
        
            new_remaining = self.trade_repo.mark_partial_exit(
                trade_id,
                exit_qty,
                exit_price
            )
    
            self.realized_repo.insert_realized_pnl(
                trade_id=trade_id,
                symbol=symbol,
                side=trade["side"],
                mode=order_mode,
                qty=exit_qty,
                entry_price=entry_price,
                exit_price=exit_price,
                exit_reason=exit_reason,
                broker_trade_id=broker_order_id
            )
    
            self.trade_repo.update_status(
                trade_id,
                TradeStatus.PARTIAL.value
            )
    
            logger.info(
                f"🟡 PARTIAL EXIT FINALIZED | "
                f"symbol={symbol} | exited={exit_qty} | "
                f"remaining={new_remaining}"
            )
    
            return
    
        # ===============================
        # 🔴 FINAL EXIT
        # ===============================
    
        logger.info(
            f"🔴 FINAL EXIT | symbol={symbol} | qty={remaining_qty}"
        )
    
        # Archive trade (moves to history internally)
        self.trade_repo.close_and_archive(
            trade_id,
            exit_price,
            exit_reason
        )
    
        # Insert realized pnl for full remaining
        self.realized_repo.insert_realized_pnl(
            trade_id=trade_id,
            symbol=symbol,
            side=trade["side"],
            mode=order_mode,
            qty=remaining_qty,
            entry_price=entry_price,
            exit_price=exit_price,
            exit_reason=exit_reason,
            broker_trade_id=broker_order_id
        )
    
        # Optional: deactivate active broker positions
        self.broker_trade_repo.deactivate_active_positions(trade_id)
    
        logger.info(
            f"✅ FINAL EXIT ARCHIVED | "
            f"symbol={symbol} | reason={exit_reason}"
        )
    

    # =====================================================
    # PUBLIC METHOD
    # =====================================================
    def place_exit_order(
        self,
        trade_id: int,
        symbol: str,
        exit_qty: int,
        exit_reason,
        exit_price: float | None = None
    ) -> bool:

        logger.info(
            f"🚪 EXIT START | trade_id={trade_id} | symbol={symbol} | qty={exit_qty}"
        )

        trade = self.trade_repo.fetch_by_id(trade_id)

        # ===============================
        # 1️⃣ STATE GUARD
        # ===============================
        if not trade:
            logger.error(f"❌ Trade not found | trade_id={trade_id}")
            return False

        status = trade["status"]
        remaining_qty = int(trade["remaining_qty"])

        if status in ("CLOSED", "INVALID", "EXIT_IN_PROGRESS"):
            logger.warning(
                f"⏭ EXIT BLOCKED | trade_id={trade_id} | status={status}"
            )
            return False

        if exit_qty <= 0 or exit_qty > remaining_qty:
            logger.error(
                f"❌ INVALID EXIT QTY | trade_id={trade_id} | remaining={remaining_qty}"
            )
            return False

        # ===============================
        # 2️⃣ IDEMPOTENCY GUARD
        # ===============================
        active_entry_positions = \
            self.broker_trade_repo.fetch_active_positions(trade_id)

        if not active_entry_positions:
            logger.error(
                f"❌ EXIT BLOCKED | No active broker position | trade_id={trade_id}"
            )
            return False

        # Restrict brokers to entry broker first
        entry_brokers = {
            bt["broker"] for bt in active_entry_positions
        }

        # ===============================
        # 3️⃣ MODE RESOLUTION
        # ===============================
        cfg = self.config_repo.get()
        order_mode = cfg["order_mode"]

        side = "SELL" if trade["side"] == "BUY" else "BUY"

        logger.info(
            f"Exit mode resolved → {order_mode} | side={side}"
        )

        # ===============================
        # 4️⃣ MARK EXIT IN PROGRESS
        # ===============================
        previous_status = status
        self.trade_repo.update_status(trade_id, "EXIT_IN_PROGRESS")

        # ===============================
        # 5️⃣ AUDIT ATTEMPT
        # ===============================
        audit_id = self.audit_repo.log_attempt(
            trade_id=trade_id,
            symbol=symbol,
            broker="EXIT_OMS",
            order_mode=order_mode,
            side=side,
            qty=exit_qty,
            order_type="MARKET",
            request_payload={
                "symbol": symbol,
                "qty": exit_qty,
                "side": side,
                "reason": exit_reason,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        try:

            # =====================================================
            # PAPER MODE
            # =====================================================
            if order_mode == "PAPER":

                synthetic_id = \
                    f"PAPER-EXIT-{trade_id}-{int(datetime.utcnow().timestamp())}"

                self._finalize_exit(
                    trade=trade,
                    exit_qty=exit_qty,
                    exit_reason=exit_reason,
                    exit_price=exit_price or trade["entry"],
                    order_mode="PAPER",
                    broker_order_id=synthetic_id
                )

                self.audit_repo.log_result(
                    audit_id=audit_id,
                    status="SUCCESS",
                    response_payload={"mode": "PAPER"}
                )

                return True

            # =====================================================
            # LIVE MODE
            # =====================================================
            order_request = TradeFriendOrderRequest(
                trade_id=trade_id,
                symbol=symbol,
                qty=exit_qty,
                side=side,
                order_mode="LIVE"
            )

            resolved_brokers = \
                self.resolver.resolve_live_brokers(self.brokers)

            # Prioritize entry broker
            resolved_brokers = \
                sorted(
                    resolved_brokers,
                    key=lambda b: 0 if b in entry_brokers else 1
                )

            success = False
            execution_payload = None

            for broker_name in resolved_brokers:

                adapter = self.brokers.get(broker_name)

                broker_trade_id = \
                    self.broker_trade_repo.insert_broker_trade(
                        trade_id=trade_id,
                        broker=broker_name,
                        order_mode="LIVE",
                        symbol=symbol,
                        leg_type="EXIT",
                        side=side,
                        qty=exit_qty,
                        order_type="MARKET"
                    )

                try:

                    result: TradeFriendExecutionResult = \
                        adapter.place_order(order_request)

                    if not result.success:

                        self.broker_trade_repo.mark_order_failed(
                            broker_trade_id=broker_trade_id,
                            error_message=result.error
                        )
                        continue

                    # Partial fill safe
                    filled_qty = result.filled_qty or exit_qty

                    exit_exec_price = \
                        result.avg_price or exit_price or trade["entry"]

                    self.broker_trade_repo.mark_order_success(
                        broker_trade_id=broker_trade_id,
                        broker_order_id=result.broker_order_id,
                        response_payload=result.raw_response
                    )

                    self._finalize_exit(
                        trade=trade,
                        exit_qty=filled_qty,
                        exit_reason=exit_reason,
                        exit_price=exit_exec_price,
                        order_mode="LIVE",
                        broker_order_id=result.broker_order_id
                    )

                    execution_payload = {
                        "broker": broker_name,
                        "broker_order_id": result.broker_order_id,
                        "filled_qty": filled_qty,
                        "avg_price": exit_exec_price
                    }

                    success = True
                    break

                except Exception as e:

                    logger.exception(
                        f"💥 EXIT execution crashed | broker={broker_name}"
                    )

                    self.broker_trade_repo.mark_order_failed(
                        broker_trade_id=broker_trade_id,
                        error_message=str(e)
                    )

            # =====================================================
            # AUDIT FINALIZATION
            # =====================================================
            if success:

                self.audit_repo.log_result(
                    audit_id=audit_id,
                    status="SUCCESS",
                    response_payload=execution_payload
                )

                return True

            # FAILURE
            self.trade_repo.update_status(trade_id, previous_status)

            self.audit_repo.log_result(
                audit_id=audit_id,
                status="FAILED",
                error_message="All brokers failed"
            )

            return False

        except Exception as e:

            logger.exception(
                f"💥 EXIT OMS CRASH | trade_id={trade_id}"
            )

            self.trade_repo.update_status(trade_id, previous_status)

            self.audit_repo.log_result(
                audit_id=audit_id,
                status="FAILED",
                error_message=str(e)
            )

            return False