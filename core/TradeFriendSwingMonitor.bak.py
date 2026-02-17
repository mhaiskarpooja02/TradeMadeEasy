# core/TradeFriendSwingTradeMonitor.py

from const.PlanStatus import ExitReason, HoldMode
from utils.logger import get_logger,get_monitor_logger
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from Servieces.TradeFriendExitOrderService import TradeFriendExitOrderService
from db.TradeFriendRealizedPnLRepo import TradeFriendRealizedPnLRepo
from db.TradeFriendOrderConfigRepo import TradeFriendOrderConfigRepo
from config.TradeFriendConfig import (
    ALLOW_TRAILING_SL,
    ENABLE_PARTIAL_BOOKING,
)

logger = get_monitor_logger()


class TradeFriendSwingTradeMonitor:
    """
    PURPOSE:
    - Monitor OPEN / PARTIAL swing trades
    - Decide EXACTLY ONE exit per trade per cycle (LOCKED)
    - Execute via PAPER or LIVE safely
    """

    def __init__(self):
        self.provider = TradeFriendDataProvider()
        self.trade_repo = TradeFriendTradeRepo()
        self.exit_oms = TradeFriendExitOrderService()
        self.order_config = TradeFriendOrderConfigRepo()
        self.realized_repo = TradeFriendRealizedPnLRepo()

    # ==================================================
    # PUBLIC ENTRY
    # ==================================================
    def run(self):
        """📌 Iterate all OPEN / PARTIAL trades"""
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
        """📌 Decide ONE exit (or none) for this trade"""

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

        # -------------------------------
        # Fetch LTP (always latest)
        # -------------------------------
        ltp = self.provider.get_ltp_byLtp(symbol)
        if ltp is None:
            return

        logger.info(
            f"🔍 MONITOR | {symbol} | LTP={ltp} | ENTRY={entry} | "
            f"SL={sl} | TARGET={target} | HOLD={hold_mode} | REM_QTY={remaining_qty}"
        )

        # ==================================================
        # 1️⃣ HARD SL — FINAL EXIT (TOP PRIORITY)
        # ==================================================
        if ltp <= sl:
            exit_reason = self._classify_sl_hit(trade)
            self._final_exit(trade, exit_reason, remaining_qty, ltp)
            return  # 🔒 lock cycle

        # ==================================================
        # 2️⃣ PARTIAL PROFIT — DECIDE ONE EXIT ONLY
        # ==================================================
        if ENABLE_PARTIAL_BOOKING and remaining_qty > 0:
            exited = self._process_partial_tiers(
                trade, ltp, entry, target, initial_qty, remaining_qty
            )
            if exited:
                return  # 🔒 one exit per trade per cycle

        # ==================================================
        # 3️⃣ TARGET → CONVERT TO RUNNER (NO EXIT)
        # ==================================================
        if ltp >= target and hold_mode == HoldMode.PARTIAL:
            self.trade_repo.update_sl(trade_id, target)
            self.trade_repo.update_hold_mode(trade_id,HoldMode.RUNNER.value)
            logger.info(f"🏁 TARGET → RUNNER | {symbol}")
            return

        # ==================================================
        # 4️⃣ RUNNER TRAILING SL
        # ==================================================
        if ALLOW_TRAILING_SL and hold_mode == 2:
            new_sl = max(sl, ltp * 0.98)
            if new_sl > sl:
                self.trade_repo.update_sl(trade_id, new_sl)
                logger.info(f"🔒 RUNNER SL TRAILED | {symbol} → {new_sl}")

    # ==================================================
    # PARTIAL TIERS — DECISION FIRST, ONE EXIT
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

        # -----------------------------
        # Safety Check
        # -----------------------------
        if base_qty <= 0:
            logger.debug(f"Partial skipped | {symbol} | BaseQty=0")
            return False

        remainder = initial_qty - (base_qty * 4)

        logger.debug(
            f"Tier Check | {symbol} | "
            f"LTP={ltp} | Exited={exited_qty} | Remaining={remaining_qty}"
        )

        # -----------------------------
        # Tier Definitions
        # -----------------------------
        tiers = [
            (ExitReason.PARTIAL_EXIT_25, 0.25, base_qty),
            (ExitReason.PARTIAL_EXIT_50, 0.50, base_qty * 2),
            (ExitReason.PARTIAL_EXIT_75, 0.75, base_qty * 3),
        ]

        eligible_tier = None

        for tier_name, tier_ratio, required_exited_qty in tiers:

            # Skip completed tiers
            if exited_qty >= required_exited_qty:
                continue

            tier_price = entry + ((target - entry) * tier_ratio)

            logger.debug(
                f"{symbol} | {tier_name} | "
                f"TierPrice={round(tier_price,2)} | LTP={ltp}"
            )

            if ltp >= tier_price:
                eligible_tier = (tier_name, base_qty)
            else:
                break  # Higher tiers impossible if this one not reached

        if not eligible_tier:
            return False

        # -----------------------------
        # Execute Partial
        # -----------------------------
        tier_name, exit_qty = eligible_tier
        exit_qty = min(exit_qty, remaining_qty)

        # Add remainder only on final exit
        if remaining_qty == exit_qty:
            exit_qty += remainder

        logger.info(
            f"""
    📉 PARTIAL EXIT EXECUTED
    Symbol        : {symbol}
    Trade ID      : {trade_id}
    Tier          : {tier_name}
    Exit Qty      : {exit_qty}
    Exit Price    : {ltp}
    Remaining Qty : {remaining_qty - exit_qty}
    """
        )

        # Execute exit
        self._execute_exit(trade, tier_name, exit_qty, ltp)
        updated_trade = self.trade_repo.fetch_by_id(trade_id)
        current_hold_mode = HoldMode(int(updated_trade.get("hold_mode", 0)))
        

        if current_hold_mode == HoldMode.OPEN:
            self.trade_repo.update_hold_mode(
                trade_id,
                HoldMode.PARTIAL.value
            )

        # Restructure SL
        self._restructure_sl_after_partial(trade_id)

        return True

    # ==================================================
    # EXECUTE EXIT — PAPER / LIVE SAFE
    # ==================================================
    def _execute_exit(self, trade: dict, reason: str, qty: int, price: float):
        """
        📌 Execute exit safely using existing repo / OMS contracts
        """

        trade_id = trade["id"]
        symbol = trade["symbol"]
        side = trade["side"]
        entry_price = float(trade["entry"])

        if qty <= 0:
            return

        # =====================
        # PAPER MODE
        # =====================
        if not self.order_config.is_live():
            # Repo owns qty, capital & hold_mode updates
            self.trade_repo.mark_partial_exit(
                trade_id=trade_id,
                exit_qty=qty,
                exit_price=price
            )

            self.realized_repo.insert_realized_pnl(
    trade_id=trade_id,
    symbol=symbol,
    side=side,
    mode="PAPER",
    qty=qty,
    entry_price=entry_price,
    exit_price=price,
    exit_reason=reason
)
            return

        # =====================
        # LIVE MODE
        # =====================
        resp = self.exit_oms.place_exit_order(
            trade_id=trade_id,
            symbol=symbol,
            exit_qty=qty,
            exit_reason=reason,
            exit_price=price
        )

        if not resp or resp.get("status") != "SUCCESS":
            logger.warning(f"❌ LIVE EXIT FAILED | {symbol} | {reason}")
            return

        # ✅ IMPORTANT:
        # Repo update is handled by OMS success flow
        # Monitor MUST NOT update trade table here

    # ==================================================
    # FINAL EXIT — SL / FULL CLOSE
    # ==================================================
    def _final_exit(self, trade: dict, reason: ExitReason, qty: int, price: float):
        """
        📌 Final exit — close and archive trade
        """

        trade_id = trade["id"]
        symbol = trade["symbol"]

        if not self.order_config.is_live():
            self.trade_repo.close_and_archive(
                trade_id=trade_id,
                exit_price=price,
                exit_reason=reason.value
            )
            return

        self.exit_oms.place_exit_order(
            trade_id=trade_id,
            symbol=symbol,
            exit_qty=qty,
            exit_reason=reason,
            exit_price=price
        )
    
    # ==================================================
    # Restructure sl after partial
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
                f"""
    🔒 SL RESTRUCTURED AFTER PARTIAL
    Trade ID     : {trade_id}
    Progress     : {round(progress*100,2)}%
    Old SL       : {current_sl}
    New SL       : {round(new_sl,2)}
    """
            )

        # ==================================================
    # SL CLASSIFICATION — EXIT REASON DECIDER
    # ==================================================
    def _classify_sl_hit(self, trade: dict) -> ExitReason:
        """
        📌 Determine which SL type was hit.

        Long-only logic:
        - INITIAL_SL_HIT      → SL below entry (loss zone)
        - BREAKEVEN_SL_HIT    → SL at entry
        - PROFIT_LOCK_SL_HIT  → SL above entry
        - TRAILING_SL_HIT     → Runner trailing stop (hold_mode=2)
        """

        entry = float(trade["entry"])
        sl = float(trade["sl"])
        hold_mode = int(trade.get("hold_mode", 0))

        # Runner trailing SL
        if hold_mode == 2:
            return ExitReason.TRAILING_SL_HIT

        # Initial hard SL (loss)
        if sl < entry:
            return ExitReason.INITIAL_SL_HIT

        # Breakeven SL
        if abs(sl - entry) < 0.05:
            return ExitReason.BREAKEVEN_SL_HIT

        # Profit lock SL
        if sl > entry:
            return ExitReason.PROFIT_LOCK_SL_HIT

        return ExitReason.INITIAL_SL_HIT
