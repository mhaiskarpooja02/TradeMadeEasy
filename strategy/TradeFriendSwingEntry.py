import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class TradeFriendSwingEntry:
    """
    PURPOSE:
    - Identify DAILY swing trade entries
    - Ignore intraday noise
    - Return signal dict or None
    """

    def __init__(self, df: pd.DataFrame, symbol: str):
        self.df = df.copy()
        self.symbol = symbol

        if not isinstance(self.df.index, pd.DatetimeIndex):
            logger.error(
            f"{symbol} received non-datetime index: {type(self.df.index)}"
            )


        self._prepare_indicators()

    # -------------------------------------------------
    # PREPARE INDICATORS
    # -------------------------------------------------
    def _prepare_indicators(self):
        self.df["ema20"] = self.df["close"].ewm(span=20).mean()
        self.df["high_20"] = self.df["high"].rolling(20).max()
        self.df["low_20"] = self.df["low"].rolling(20).min()

    # -------------------------------------------------
    # PUBLIC ENTRY METHOD
    # -------------------------------------------------
    def confirm_entry(self):
        """
        Returns signal dict or None
        """

        if len(self.df) < 30:
            return None

        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]

        # -----------------------------
        # LONG SWING CONDITION
        # -----------------------------
        if self._is_long_breakout(last, prev):
            return self._build_long_signal(last)

        # SHORT logic can be added later
        return None

    # -------------------------------------------------
    # LONG BREAKOUT LOGIC
    # -------------------------------------------------
    def _is_long_breakout(self, last, prev):
        return (
            last["close"] > prev["high_20"] and     # breakout
            last["close"] > last["ema20"]           # trend filter
        )

    # -------------------------------------------------
    # BUILD LONG SIGNAL
    # -------------------------------------------------
    def _build_long_signal(self, last):
        entry = last["close"]

        # SL = recent swing low (last 10 candles)
        recent_lows = self.df["low"].iloc[-10:]
        sl = recent_lows.min()

        if sl >= entry:
            return None

        risk = entry - sl
        target1 = entry + (2 * risk)

        signal = {
            "symbol": self.symbol,
            "strategy": "DAILY_BREAKOUT",
            "bias": "LONG",
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "target1": round(target1, 2)
        }

        logger.info(
            f"Swing setup found | {self.symbol} | Entry={entry} SL={sl} Target={target1}"
        )

        return signal
