from datetime import date
from const.TradeFriendPlanStatus import TradeStatus
from db.TradeFriendBrokerTradeRepo import TradeFriendBrokerTradeRepo
from db.TradeFriendOrderAuditRepo import TradeFriendOrderAuditRepo
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from db.TradeFriendOrderConfigRepo import TradeFriendOrderConfigRepo
from core.TradeFriendDataProvider import TradeFriendDataProvider
from Servieces.TradeFriendOrderManagementService import TradeFriendOrderManagementService
from utils.logger import get_logger, get_order_logger
import time
import json

from config.TradeFriendConfig import (
    ENTRY_TOLERANCE,
    PARTIAL_ENTRY_ENABLED,
    PARTIAL_ENTRY_QTY,
)

logger = get_logger(__name__)
order_logger = get_order_logger()


class TradeFriendSwingTriggerEngine:
    """
    HARDENED SWING TRIGGER ENGINE
    - Duplicate safe (atomic lock)
    - Paper / Live unified via OMS
    - Broker repo for real execution
    - Optional Audit repo for reporting
    - Logger for skipped / invalid trades
    """

    def __init__(self, capital: float):
        self.capital = capital
        self.provider = TradeFriendDataProvider()
        self.trade_repo = TradeFriendTradeRepo()
        self.plan_repo = TradeFriendSwingPlanRepo()
        self.broker_repo = TradeFriendBrokerTradeRepo()
        self.audit_repo = TradeFriendOrderAuditRepo()
        self.oms = TradeFriendOrderManagementService()

        self._next_broker_call_ts = 0

        cfg = TradeFriendOrderConfigRepo()
        self.paper_trade = not cfg.is_live()

    # =========================
    # PUBLIC RUN
    # =========================
    def run(self):
        logger.info("📡 Swing Trigger Engine started")

        ready_trades = self.trade_repo.fetch_ready_trades()
        if not ready_trades:
            logger.info("No READY trades found")
            return

        for trade in ready_trades:
            trade = dict(trade)
            try:
                result = self._process_trade(trade)
                if result and result["status"] in (
                    TradeStatus.OPEN,
                    TradeStatus.PARTIAL,
                ):
                    self.plan_repo.mark_triggered_by_Planid(result["plan_id"])
            except Exception as e:
                logger.exception(f"Trigger crashed | {trade.get('symbol')} | {e}")

        logger.info("✅ Swing Trigger Engine completed")

    
    # =========================
    # PROCESS SINGLE TRADE
    # =========================
    def _process_trade(self, trade: dict) -> dict | None:

        trade_id = trade["id"]
        symbol = trade["symbol"]
        plan_id = trade.get("swing_plan_id")

        if trade.get("status") != TradeStatus.READY.value:
            logger.debug(f"{symbol} skipped — not READY")
            return None

        # ----------------------------
        # DUPLICATE ENTRY LOCK
        # ----------------------------
        locked = self.trade_repo.promote_if_ready(
            trade_id=trade_id,
            from_status=TradeStatus.READY.value,
            to_status=TradeStatus.ENTRY_IN_PROGRESS.value
        )
        if not locked:
            logger.info(f"{symbol} skipped — already picked by another engine")
            return None

        logger.info(f"🔐 LOCK ACQUIRED | {symbol}")

        planned_entry = float(trade["planned_entry"])
        initial_qty = int(trade["initial_qty"])
        remaining_qty = int(trade["remaining_qty"])
        filled_qty = initial_qty - remaining_qty

        if not plan_id:
            logger.error(f"{symbol} missing swing_plan_id")
            self._rollback_to_ready(trade_id)
            return None

        # ----------------------------
        # BROKER COOLDOWN
        # ----------------------------
        self._wait_for_broker()

        # ----------------------------
        # FETCH LTP
        # ----------------------------
        ltp = self.provider.get_ltp_byLtp(symbol)
        if not ltp or ltp <= 0:
            logger.warning(f"{symbol} invalid LTP")
            self._rollback_to_ready(trade_id)
            return None

        tolerance = planned_entry * ENTRY_TOLERANCE

        # ----------------------------
        # ENTRY WINDOW VALIDATION
        # ----------------------------
        if ltp < planned_entry:
            logger.info(f"{symbol} below planned entry ({ltp} < {planned_entry})")
            self._rollback_to_ready(trade_id)
            return None

        if ltp > planned_entry + tolerance:
            reason = f"Missed entry | LTP={ltp}"
            logger.warning(f"{symbol} {reason}")
            self.trade_repo.invalidate_trade(
                trade_id,
                reason=reason,
                status=TradeStatus.INVALID.value
            )
            return None

        logger.info(f"🚀 ENTRY WINDOW HIT | {symbol} | LTP={ltp}")

        # ----------------------------
        # DECIDE QTY
        # ----------------------------
        if remaining_qty <= 0:
            self._rollback_to_ready(trade_id)
            return None

        qty_to_place = (
            min(PARTIAL_ENTRY_QTY, remaining_qty)
            if PARTIAL_ENTRY_ENABLED and filled_qty == 0
            else remaining_qty
        )

        # ----------------------------
        # CAPITAL VALIDATION ONLY
        # ----------------------------
        capital_snapshot = self.trade_repo.settings_repo.fetch()
        available_capital = capital_snapshot["available_swing_capital"]
        required_capital = planned_entry * qty_to_place

        logger.info(
            f"💰 CAPITAL CHECK | {symbol} | "
            f"Available={available_capital} | Required={required_capital}"
        )

        if required_capital > available_capital:
            logger.warning(
                f"❌ Insufficient capital | {symbol} | "
                f"Required={required_capital} | Available={available_capital}"
            )
            self._rollback_to_ready(trade_id)
            return None

        # ----------------------------
        # PLACE ORDER (Paper / Live)
        # ----------------------------
        executions = self.oms.place_entry_order(
            trade_id=trade_id,
            symbol=symbol,
            qty=qty_to_place,
            side="BUY",
            price=ltp
        )

        if not executions:
            logger.warning(f"{symbol} OMS returned no executions")
            self._rollback_to_ready(trade_id)
            return None

        # ----------------------------
        # PROCESS EXECUTIONS
        # ----------------------------
        total_filled = 0
        weighted_price = 0.0

        for ex in executions:
            qty = ex["filled_qty"]
            price = ex["avg_price"]

            total_filled += qty
            weighted_price += qty * price

            broker_trade_id = self.broker_repo.insert_broker_trade(
                trade_id=trade_id,
                broker=ex["broker"],
                order_mode="PAPER" if self.paper_trade else "LIVE",
                symbol=symbol,
                leg_type="ENTRY",
                side="BUY",
                qty=qty,
                exchange=ex.get("exchange"),
                product=ex.get("product"),
                order_type=ex.get("order_type"),
                request_payload=ex.get("request_payload"),
            )

            self.broker_repo.mark_order_success(
                broker_trade_id=broker_trade_id,
                broker_order_id=ex["broker_order_id"],
                response_payload=ex.get("response_payload"),
            )

            order_logger.info(
                f"[ENTRY] {symbol} | {ex['broker']} | qty={qty} | price={price}"
            )

        if total_filled <= 0:
            logger.warning(f"{symbol} no fills received")
            self._rollback_to_ready(trade_id)
            return None

        avg_entry_price = round(weighted_price / total_filled, 2)

        # ----------------------------
        # DEDUCT ACTUAL USED CAPITAL
        # ----------------------------
        actual_used_capital = avg_entry_price * total_filled

        before_capital = self.trade_repo.settings_repo.fetch()["available_swing_capital"]

        self.trade_repo.settings_repo.adjust_available_swing_capital(-actual_used_capital)

        after_capital = self.trade_repo.settings_repo.fetch()["available_swing_capital"]

        logger.info(
            f"💸 CAPITAL ALLOCATED | {symbol} | "
            f"Used={actual_used_capital} | "
            f"Before={before_capital} | After={after_capital}"
        )

        # ----------------------------
        # UPDATE TRADE FILL
        # ----------------------------
        self.trade_repo.update_entry_fill(
            trade_id=trade_id,
            fill_qty=total_filled,
            fill_price=avg_entry_price
        )

        new_filled_qty = filled_qty + total_filled

        # ----------------------------
        # FULL ENTRY
        # ----------------------------
        if new_filled_qty >= initial_qty:
            self.trade_repo.mark_open(
                trade_id=trade_id,
                avg_entry=avg_entry_price,
                entry_day=date.today().isoformat(),
                status=TradeStatus.OPEN.value
            )

            logger.info(f"✅ ENTRY COMPLETE | {symbol}")

            return {
                "trade_id": trade_id,
                "plan_id": plan_id,
                "symbol": symbol,
                "status": TradeStatus.OPEN,
                "filled_qty": new_filled_qty
            }

        # ----------------------------
        # PARTIAL ENTRY
        # ----------------------------
        self.trade_repo.update_status(trade_id, TradeStatus.PARTIAL.value)

        logger.info(f"➗ PARTIAL ENTRY | {symbol}")

        return {
            "trade_id": trade_id,
            "plan_id": plan_id,
            "symbol": symbol,
            "status": TradeStatus.PARTIAL,
            "filled_qty": new_filled_qty
        }

  
    
    # =========================
    # ROLLBACK TO READY
    # =========================
    def _rollback_to_ready(self, trade_id: int):
        self.trade_repo.update_status(trade_id, TradeStatus.READY.value)
        logger.info(
            f"↩ Rolled back trade_id={trade_id} to READY (No capital movement)"
        )

    # =========================
    # BROKER COOLDOWN
    # =========================
    def _wait_for_broker(self):
        now = time.time()
        if now < self._next_broker_call_ts:
            wait = round(self._next_broker_call_ts - now, 2)
            logger.info(f"⏸ Broker cooldown {wait}s")
            time.sleep(wait)
        self._next_broker_call_ts = time.time() + 2  # 2 sec cooldown
