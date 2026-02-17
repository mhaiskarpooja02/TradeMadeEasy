# Servieces/TradeFriendExitOrderService.py

import logging
from datetime import datetime
from const.TradeFriendPlanStatus import TradeStatus

from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendTradeHistoryRepo import TradeFriendTradeHistoryRepo
from db.TradeFriendBrokerTradeRepo import TradeFriendBrokerTradeRepo
from db.TradeFriendOrderAuditRepo import TradeFriendOrderAuditRepo
from db.TradeFriendOrderConfigRepo import TradeFriendOrderConfigRepo
from db.TradeFriendRealizedPnLRepo import TradeFriendRealizedPnLRepo

from brokers.tradefriend_dhan_order_adapter import TradeFriendDhanOrderAdapter
from brokers.tradefriend_angel_order_adapter import TradeFriendAngelOrderAdapter

logger = logging.getLogger(__name__)


class TradeFriendExitOrderService:

    def __init__(self):
        self.trade_repo = TradeFriendTradeRepo()
        self.history_repo = TradeFriendTradeHistoryRepo()
        self.broker_trade_repo = TradeFriendBrokerTradeRepo()
        self.audit_repo = TradeFriendOrderAuditRepo()
        self.config_repo = TradeFriendOrderConfigRepo()
        self.realized_repo = TradeFriendRealizedPnLRepo()

        self.brokers = {
            "DHAN": TradeFriendDhanOrderAdapter(),
            "ANGEL": TradeFriendAngelOrderAdapter()
        }

    # ==================================================
    # PUBLIC ENTRY
    # ==================================================
    def place_exit_order(
        self,
        trade_id: int,
        symbol: str,
        exit_qty: int,
        exit_reason,
        exit_price: float | None = None
    ) -> bool:

        logger.info(
            f"🚪 EXIT OMS | trade_id={trade_id} | symbol={symbol} | qty={exit_qty}"
        )

        trade = self.trade_repo.fetch_by_id(trade_id)
        if not trade:
            logger.error(f"EXIT OMS → Trade not found: {trade_id}")
            return False

        status = trade["status"]
        remaining_qty = int(trade["remaining_qty"])

        # ===============================
        # STATE GUARD
        # ===============================
        if status in ("CLOSED", "INVALID", "EXIT_IN_PROGRESS"):
            logger.warning(f"⏭ EXIT BLOCKED | Trade={trade_id} | Status={status}")
            return False

        if exit_qty <= 0 or exit_qty > remaining_qty:
            logger.error(
                f"{symbol} → Invalid exit qty {exit_qty} (remaining {remaining_qty})"
            )
            return False

        # ===============================
        # ENUM NORMALIZATION
        # ===============================
        if hasattr(exit_reason, "value"):
            exit_reason = exit_reason.value

        side = "SELL" if trade["side"] == "BUY" else "BUY"
        ltp = exit_price or trade.get("ltp")

        cfg = self.config_repo.get()
        order_mode = cfg["order_mode"]

        request_payload = {
            "symbol": symbol,
            "qty": exit_qty,
            "side": side,
            "mode": order_mode,
            "exit_reason": exit_reason,
            "timestamp": datetime.utcnow().isoformat()
        }

        # ===============================
        # MARK EXIT IN PROGRESS
        # ===============================
        previous_status = status
        self.trade_repo.update_status(trade_id, "EXIT_IN_PROGRESS")

        audit_id = self.audit_repo.log_attempt(
            trade_id=trade_id,
            symbol=symbol,
            broker="EXIT_OMS",
            order_mode=order_mode,
            side=side,
            qty=exit_qty,
            exchange=trade.get("exchange"),
            product=trade.get("product"),
            order_type="MARKET",
            request_payload=request_payload
        )

        try:

            # ==================================================
            # PAPER MODE
            # ==================================================
            if order_mode == "PAPER":
                synthetic_broker_id = (
                    f"PAPER-EXIT-{trade_id}-{int(datetime.now().timestamp())}"
                )

                self._finalize_exit(
                    trade=trade,
                    exit_qty=exit_qty,
                    exit_reason=exit_reason,
                    exit_price=ltp,
                    order_mode="PAPER",
                    broker_order_id=synthetic_broker_id
                )

                self._finalize_audit(
                    audit_id=audit_id,
                    status="SUCCESS",
                    resolved_id=synthetic_broker_id,
                    response_payload={
                        "mode": "PAPER",
                        "broker_order_id": synthetic_broker_id
                    }
                )

                return True

            # ==================================================
            # LIVE MODE
            # ==================================================
            success, broker_order_id, broker_response = \
                self._execute_live_exit(
                    trade_id, symbol, exit_qty, side, ltp
                )

            if not success:
                self.trade_repo.update_status(trade_id, previous_status)

                self._finalize_audit(
                    audit_id=audit_id,
                    status="FAILED",
                    error_message="Broker execution failed"
                )

                return False

            self._finalize_exit(
                trade=trade,
                exit_qty=exit_qty,
                exit_reason=exit_reason,
                exit_price=ltp,
                order_mode="LIVE",
                broker_order_id=broker_order_id
            )

            self._finalize_audit(
                audit_id=audit_id,
                status="SUCCESS",
                resolved_id=broker_order_id,
                response_payload=broker_response
            )

            return True

        except Exception as e:
            logger.exception(f"EXIT OMS CRASH | Trade={trade_id}")

            self.trade_repo.update_status(trade_id, previous_status)

            self._finalize_audit(
                audit_id=audit_id,
                status="FAILED",
                error_message=str(e)
            )

            return False

    # ==================================================
    # LIVE EXECUTION LAYER
    # ==================================================
    def _execute_live_exit(self, trade_id, symbol, qty, side, price):

        broker_trades = self.broker_trade_repo.fetch_active_positions(trade_id)

        for bt in broker_trades or []:
            adapter = self.brokers.get(bt["broker"])
            if not adapter:
                continue

            result = adapter.place_order(
                symbol=symbol,
                qty=qty,
                side=side
            )

            if result and result.get("status") == "SUCCESS":

                broker_order_id = result.get("broker_order_id")

                self.broker_trade_repo.insert_broker_trade(
                    trade_id=trade_id,
                    broker=bt["broker"],
                    symbol=symbol,
                    side="EXIT",
                    qty=qty,
                    price=price,
                    broker_order_id=broker_order_id,
                    active=False
                )

                return True, broker_order_id, result

        return False, None, None

    # ==================================================
    # FINALIZER (TRADE MUTATION)
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
        remaining = int(trade["remaining_qty"])

        # ===============================
        # PARTIAL EXIT
        # ===============================
        if exit_qty < remaining:

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
                trade_id, TradeStatus.PARTIAL.value
            )

            logger.info(
                f"🟡 PARTIAL EXIT FINALIZED | {symbol} | "
                f"Qty={exit_qty} | Remaining={new_remaining} | Mode={order_mode}"
            )
            return

        # ===============================
        # FINAL EXIT
        # ===============================
        self.trade_repo.close_and_archive(
            trade_id,
            exit_price,
            exit_reason
        )

        self.realized_repo.insert_realized_pnl(
            trade_id=trade_id,
            symbol=symbol,
            side=trade["side"],
            mode=order_mode,
            qty=remaining,
            entry_price=entry_price,
            exit_price=exit_price,
            exit_reason=exit_reason,
            broker_trade_id=broker_order_id
        )

        logger.info(
            f"🔴 FINAL EXIT ARCHIVED | {symbol} | "
            f"Reason={exit_reason} | Mode={order_mode}"
        )

    # ==================================================
    # AUDIT FINALIZER
    # ==================================================
    def _finalize_audit(
        self,
        audit_id: int,
        status: str,
        resolved_id: str | None = None,
        response_payload: dict | None = None,
        error_message: str | None = None
    ):
        self.audit_repo.log_result(
            audit_id=audit_id,
            status=status,
            resolved_id=resolved_id,
            response_payload=response_payload,
            error_message=error_message
        )
