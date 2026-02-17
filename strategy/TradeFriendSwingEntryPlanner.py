# core/TradeFriendSwingEntryPlanner.py

import pandas as pd
from datetime import datetime, timedelta
import logging
import talib

from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo

logger = logging.getLogger(__name__)


class TradeFriendSwingEntryPlanner:
    """
    PURPOSE:
    - Convert a valid swing signal into a concrete trade plan
    - Strategy-aware (Upper BB vs others)
    - Fully settings-driven for FIXED mode
    - TRADITIONAL mode uses implicit RR
    - Pure logic class (NO DB writes, NO API calls)
    """

    def __init__(self, df: pd.DataFrame, symbol: str, strategy: str):
        self.df = df.copy()
        self.symbol = symbol
        self.strategy = strategy
        self.settings_repo = TradeFriendSettingsRepo()

        # Pre-calc indicators only once
        close = self.df["close"].astype(float)
        self.df["bb_upper"], self.df["bb_middle"], self.df["bb_lower"] = talib.BBANDS(
            close, timeperiod=20
        )

    # --------------------------------------------------
    # PUBLIC
    # --------------------------------------------------
    def build_plan(self) -> dict | None:
        try:
            entry = self._calculate_entry()
            sl = self._calculate_sl(entry)
            target = self._calculate_target(entry, sl)

            if entry <= sl:
                logger.warning(
                    f"{self.symbol} → Invalid SL structure | entry={entry} sl={sl}"
                )
                return None

            rr = round((target - entry) / (entry - sl), 2)

            plan = {
                "symbol": self.symbol,
                "strategy": self.strategy,
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "target": round(target, 2),
                "rr": rr,
                "expiry_date": self._expiry_date()
            }

            logger.info(
                f"✅ Swing plan built | {self.symbol} | "
                f"strategy={self.strategy} | "
                f"Entry={plan['entry']} SL={plan['sl']} "
                f"Target={plan['target']} RR={rr}"
            )

            return plan

        except Exception as e:
            logger.exception(f"Swing plan build failed for {self.symbol}: {e}")
            return None

    # --------------------------------------------------
    # ENTRY
    # --------------------------------------------------
    def _calculate_entry(self) -> float:
        last = self.df.iloc[-1]

        # ✅ UPPER BOLLINGER BAND → CLOSE-BASED ENTRY
        if self.strategy == "Upper Band Expansion":
            entry = float(last["close"])
            logger.debug(
                f"{self.symbol} → BB Entry (close-based): {entry}"
            )
            return entry

        # DEFAULT (breakout above high)
        entry = float(last["high"])
        logger.debug(f"{self.symbol} → Default Entry (high-based): {entry}")
        return entry

    # --------------------------------------------------
    # SL
    # --------------------------------------------------
    def _calculate_sl(self, entry: float) -> float:
        last = self.df.iloc[-1]
        settings = dict(self.settings_repo.fetch())
        mode = (settings.get("target_sl_mode") or "TRADITIONAL").upper()

        # ✅ UPPER BOLLINGER BAND → STRUCTURAL SL
        if self.strategy == "Upper Band Expansion":
            bb_middle = float(last["bb_middle"])
            recent_low = float(self.df["low"].tail(3).min())

            sl = min(bb_middle, recent_low)

            logger.debug(
                f"{self.symbol} → BB SL calculated | "
                f"bb_middle={bb_middle} recent_low={recent_low} sl={sl}"
            )
            return sl

        # -----------------------------
        # DEFAULT LOGIC
        # -----------------------------
        logger.debug(f"{self.symbol} → SL mode: {mode}")

        if mode == "TRADITIONAL":
            recent_lows = self.df["low"].tail(5)
            return float(recent_lows.min())

        if mode == "FIXED":
            sl_pct = float(settings.get("fixed_sl_percent", 2.0))
            return entry * (1 - sl_pct / 100)

        raise ValueError(f"Invalid target_sl_mode: {mode}")

    # --------------------------------------------------
    # TARGET
    # --------------------------------------------------
    def _calculate_target(self, entry: float, sl: float) -> float:
        settings = dict(self.settings_repo.fetch())
        mode = (settings.get("target_sl_mode") or "TRADITIONAL").upper()

        # ✅ UPPER BOLLINGER BAND → CONSERVATIVE RR
        if self.strategy == "Upper Band Expansion":
            risk = entry - sl
            target = entry + (risk * 1.2)

            logger.debug(
                f"{self.symbol} → BB Target calculated | risk={risk} target={target}"
            )
            return target

        # -----------------------------
        # DEFAULT LOGIC
        # -----------------------------
        logger.debug(f"{self.symbol} → Target mode: {mode}")

        if mode == "TRADITIONAL":
            risk = entry - sl
            return entry + (2 * risk)

        if mode == "FIXED":
            tgt_pct = float(settings.get("fixed_target_percent", 4.0))
            return entry * (1 + tgt_pct / 100)

        raise ValueError(f"Invalid target_sl_mode: {mode}")

    # --------------------------------------------------
    # EXPIRY
    # --------------------------------------------------
    def _expiry_date(self, days: int = 7) -> str:
        return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
