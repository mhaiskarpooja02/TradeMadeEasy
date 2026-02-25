# core/TradeFriendSwingTradeMonitor.py

from const.TradeFriendPlanStatus import ExitReason, HoldMode
from utils.logger import get_monitor_logger
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from Servieces.TradeFriendExitOrderService import TradeFriendExitOrderService
from Servieces.TradeFriendOrderManagementService import TradeFriendOrderManagementService
from config.TradeFriendConfig import (
    ALLOW_TRAILING_SL,
    ENABLE_PARTIAL_BOOKING,
)

logger = get_monitor_logger()


class TradeFriendSwingTradeMonitor:
    """
    PURPOSE:
    - Monitor OPEN / PARTIAL swing trades
    - Decide EXACTLY ONE exit per trade per cycle
    - Delegate execution to OMS (PAPER + LIVE handled inside OMS)
    """

    def __init__(self):
        self.provider = TradeFriendDataProvider()
        self.trade_repo = TradeFriendTradeRepo()
        self.exit_oms = TradeFriendExitOrderService()
        self.entry_oms = TradeFriendOrderManagementService()

    # ==================================================
    # PUBLIC ENTRY
    # ==================================================
    def run(self):

        open_trades = self.trade_repo.fetch_open_trades()
        if not open_trades:
            return

        for trade in open_trades:
            try:
                self._process_trade(dict(trade))
            except Exception as e:
                logger.exception(
                    f"SwingTradeMonitor failed for {trade['symbol']}: {e}"
                )

    # ==================================================
    # PROCESS SINGLE TRADE
    # ==================================================
    def _process_trade(self, trade: dict):

        symbol = trade["symbol"]
        trade_id = trade["id"]

        entry = float(trade["entry"])
        sl = float(trade["sl"])
        target = float(trade["target"])

        initial_qty = int(trade["initial_qty"])
        remaining_qty = int(trade["remaining_qty"])
        hold_mode = int(trade.get("hold_mode", 0))

        if remaining_qty <= 0:
            return

        ltp = self.provider.get_ltp_byLtp(symbol)
        if ltp is None:
            return

        logger.info(
            f"🔍 MONITOR | {symbol} | LTP={ltp} | "
            f"SL={sl} | TARGET={target} | HOLD={hold_mode} | REM={remaining_qty}"
        )

        # ==================================================
        # 1️⃣ HARD SL — FINAL EXIT
        # ==================================================
        if ltp <= sl:
            exit_reason = self._classify_sl_hit(trade)
            self._delegate_exit(trade, exit_reason, remaining_qty, ltp)
            return

        # ==================================================
        # 2️⃣ SCALE-IN
        # ==================================================
        logger.info(f"2️⃣ SCALE-IN CHECK | Symbol={trade['symbol']} | LTP={ltp}")
        scaled = self._process_scale_in(trade, ltp)
        if scaled:
            logger.info(f"2️⃣ SCALE-IN COMPLETED | Symbol={trade['symbol']}")
            return
        else:
            logger.info(f"2️⃣ SCALE-IN SKIPPED / NOT TRIGGERED | Symbol={trade['symbol']}")

        # ==================================================
        # 3️⃣ PARTIAL PROFIT TIERS
        # ==================================================
        if ENABLE_PARTIAL_BOOKING:
            logger.info(f"3️⃣ PARTIAL PROFIT CHECK | Symbol={trade['symbol']} | LTP={ltp}")
            exited = self._process_partial_tiers(
                trade, ltp, entry, target, initial_qty, remaining_qty
            )
            if exited:
                logger.info(f"3️⃣ PARTIAL PROFIT EXITED | Symbol={trade['symbol']}")
                return
            else:
                logger.info(f"3️⃣ PARTIAL PROFIT NOT TRIGGERED | Symbol={trade['symbol']}")

        # ==================================================
        # 4️⃣   TARGET → RUNNER MODE
        # ==================================================
        if ltp >= target and hold_mode == HoldMode.PARTIAL:
            self.trade_repo.update_sl(trade_id, target)
            self.trade_repo.update_hold_mode(
                trade_id, HoldMode.RUNNER.value
            )
            logger.info(f"🏁 TARGET HIT → RUNNER | {symbol}")
            return

        # ==================================================
        # 5️⃣   RUNNER TRAILING SL
        # ==================================================
        if ALLOW_TRAILING_SL and hold_mode == HoldMode.RUNNER:
            new_sl = max(sl, ltp * 0.98)
            if new_sl > sl:
                self.trade_repo.update_sl(trade_id, round(new_sl, 2))
                logger.info(
                    f"🔒 RUNNER SL TRAILED | {symbol} → {round(new_sl,2)}"
                )

    # ==================================================
    # PARTIAL TIERS
    # ==================================================
    def _process_partial_tiers(
        self,
        trade: dict,
        ltp: float,
        entry: float,
        target: float,
        initial_qty: int,
        remaining_qty: int
    ) -> bool:

        symbol = trade["symbol"]
        trade_id = trade["id"]

        exited_qty = initial_qty - remaining_qty
        base_qty = initial_qty // 4

        if base_qty <= 0:
            return False

        remainder = initial_qty - (base_qty * 4)

        tiers = [
            (ExitReason.PARTIAL_EXIT_25, 0.25, base_qty),
            (ExitReason.PARTIAL_EXIT_50, 0.50, base_qty * 2),
            (ExitReason.PARTIAL_EXIT_75, 0.75, base_qty * 3),
        ]

        eligible_tier = None

        for tier_reason, tier_ratio, required_exited in tiers:

            if exited_qty >= required_exited:
                continue

            tier_price = entry + ((target - entry) * tier_ratio)

            if ltp >= tier_price:
                eligible_tier = (tier_reason, base_qty)
            else:
                break

        if not eligible_tier:
            return False

        tier_reason, exit_qty = eligible_tier
        exit_qty = min(exit_qty, remaining_qty)

        if remaining_qty == exit_qty:
            exit_qty += remainder

        logger.info(
            f"📉 PARTIAL EXIT | {symbol} | "
            f"Reason={tier_reason.name} | Qty={exit_qty} | Price={ltp}"
        )

        # Execute via OMS
        success = self._delegate_exit(trade, tier_reason, exit_qty, ltp)

        if not success:
            return False

        # Upgrade hold mode if needed
        updated_trade = self.trade_repo.fetch_by_id(trade_id)
        if updated_trade:
            current_hold_mode = HoldMode(
                int(updated_trade.get("hold_mode", 0))
            )

            if current_hold_mode == HoldMode.OPEN:
                self.trade_repo.update_hold_mode(
                    trade_id, HoldMode.PARTIAL.value
                )

        # Restructure SL
        self._restructure_sl_after_partial(trade_id)

        return True

    # ==================================================
    # DELEGATE EXIT TO OMS
    # ==================================================
    def _delegate_exit(
        self,
        trade: dict,
        reason: ExitReason,
        qty: int,
        price: float
    ) -> bool:

        if qty <= 0:
            return False

        resp = self.exit_oms.place_exit_order(
            trade_id=trade["id"],
            symbol=trade["symbol"],
            exit_qty=qty,
            exit_reason=reason,
            exit_price=price
        )

        if not resp:
            logger.warning(
                f"❌ EXIT FAILED | {trade['symbol']} | {reason}"
            )
            return False

        return True

    # ==================================================
    # SL RESTRUCTURE AFTER PARTIAL
    # ==================================================
    def _restructure_sl_after_partial(self, trade_id: int):

        trade = self.trade_repo.fetch_by_id(trade_id)
        if not trade:
            return

        entry = float(trade["entry"])
        target = float(trade["target"])
        initial_qty = int(trade["initial_qty"])
        remaining_qty = int(trade["remaining_qty"])
        current_sl = float(trade["sl"])

        booked_qty = initial_qty - remaining_qty
        progress = booked_qty / initial_qty

        level_25 = entry
        level_50 = entry + (target - entry) * 0.25
        level_75 = entry + (target - entry) * 0.50

        new_sl = current_sl

        if progress >= 0.75:
            new_sl = max(current_sl, level_75)
        elif progress >= 0.50:
            new_sl = max(current_sl, level_50)
        elif progress >= 0.25:
            new_sl = max(current_sl, level_25)

        if new_sl > current_sl:
            self.trade_repo.update_sl(trade_id, round(new_sl, 2))
            logger.info(
                f"🔒 SL UPDATED AFTER PARTIAL | Trade={trade_id} | "
                f"Old={current_sl} | New={round(new_sl,2)}"
            )

    # ==================================================
    # SL CLASSIFICATION
    # ==================================================
    def _classify_sl_hit(self, trade: dict) -> ExitReason:

        entry = float(trade["entry"])
        sl = float(trade["sl"])
        hold_mode = int(trade.get("hold_mode", 0))
        partial_exit_pct = float(trade.get("partial_exit_pct", 0))  # 25, 50, 75

        if hold_mode == HoldMode.RUNNER:
            return ExitReason.TRAILING_SL_HIT

        # Partial exits
        if partial_exit_pct == 25:
            return ExitReason.PARTIAL_EXIT_25
        if partial_exit_pct == 50:
            return ExitReason.PARTIAL_EXIT_50
        if partial_exit_pct == 75:
            return ExitReason.PARTIAL_EXIT_75

        # Full SL stages
        if sl < entry:
            return ExitReason.INITIAL_SL_HIT
        if abs(sl - entry) < 0.05:
            return ExitReason.BREAKEVEN_SL_HIT
        if sl > entry:
            return ExitReason.PROFIT_LOCK_SL_HIT

        return ExitReason.INITIAL_SL_HIT

    # ==================================================
    # process scale in
    # ==================================================
    def _process_scale_in(self, trade: dict, ltp: float) -> bool:
        symbol = trade["symbol"]
        trade_id = trade["id"]

        entry = float(trade["entry"])
        initial_qty = int(trade["initial_qty"])
        remaining_qty = int(trade["remaining_qty"])

        logger.debug(f"🔹 SCALE-IN CHECK | {symbol} | Trade ID={trade_id} | LTP={ltp} | Entry={entry} | Remaining Qty={remaining_qty}")

        # Nothing left to scale
        if remaining_qty <= 0:
            logger.info(f"⏹ SCALE-IN SKIPPED | {symbol} | No remaining quantity to scale-in")
            return False

        # Example trigger: 1% above entry
        trigger_price = entry * 1.01
        logger.debug(f"💡 SCALE-IN TRIGGER PRICE CALCULATED | {symbol} | Trigger={trigger_price}")

        if ltp < trigger_price:
            logger.info(f"⏳ SCALE-IN NOT TRIGGERED | {symbol} | LTP={ltp} below trigger={trigger_price}")
            return False

        scale_qty = remaining_qty
        logger.info(f"📈 SCALE-IN TRIGGERED | {symbol} | LTP={ltp} | Scaling Qty={scale_qty}")

        try:
            # Call ENTRY OMS
            executions = self.entry_oms.place_entry_order(
                trade_id=trade_id,
                symbol=symbol,
                qty=scale_qty,
                side="BUY",
                price=ltp
            )
            logger.debug(f"📝 SCALE-IN ORDER SENT | {symbol} | Order Response={executions}")
        except Exception as e:
            logger.error(f"❌ SCALE-IN OMS ERROR | {symbol} | Error: {e}")
            return False

        if not executions:
            logger.warning(f"❌ SCALE-IN FAILED | {symbol} | No executions returned")
            return False

        total_filled = 0
        weighted_price = 0.0

        for ex in executions:
            qty = ex.get("filled_qty", 0)
            price = ex.get("avg_price", 0.0)
            logger.debug(f"🔄 SCALE-IN EXECUTION | {symbol} | Filled={qty} | Price={price}")

            total_filled += qty
            weighted_price += qty * price

        if total_filled <= 0:
            logger.info(f"⏳ SCALE-IN PLACED — WAITING FILL | {symbol}")
            return False

        avg_price = round(weighted_price / total_filled, 2)
        logger.info(f"✅ SCALE-IN FILLED | {symbol} | Total Qty={total_filled} | Avg Price={avg_price}")

        try:
            # Update trade table same way initial entry does
            self.trade_repo.update_entry_fill(
                trade_id=trade_id,
                fill_qty=total_filled,
                fill_price=avg_price
            )
            logger.debug(f"💾 TRADE REPO UPDATED | {symbol} | Trade ID={trade_id}")
        except Exception as e:
            logger.error(f"❌ TRADE REPO UPDATE FAILED | {symbol} | Error: {e}")
            return False

        logger.info(f"✅ SCALE-IN COMPLETE | {symbol}")
        return True