import talib
import logging
from utils.logger import get_logger

logger = get_logger(__name__)


class TradeFriendScanner:
    """
    PURPOSE:
    - Find high-quality DAILY swing candidates
    - Strong structural filtering (for 1400 stock universe)
    - Returns only SYMBOL + STRATEGY metadata
    """

    def __init__(self, df, symbol):
        self.df = df.copy()
        self.symbol = symbol

    def scan(self):
        df = self.df

        logger.info(f"{self.symbol} → started scanner")

        # -----------------------------
        # SAFETY CHECK
        # -----------------------------
        if df.empty or len(df) < 220:
            logger.info(f"{self.symbol} → Skipped (insufficient data)")
            return None

        close = df["close"].astype(float)
        volume = df["volume"].astype(float)

        # -----------------------------
        # INDICATORS
        # -----------------------------
        df["ema_20"] = talib.EMA(close, 20)
        df["ema_50"] = talib.EMA(close, 50)
        df["ema_200"] = talib.EMA(close, 200)

        df["adx"] = talib.ADX(df["high"], df["low"], close, 14)
        df["rsi"] = talib.RSI(close, 14)

        last = df.iloc[-1]

        # ==================================================
        # LAYER 1 → STRUCTURAL TREND FILTER
        # ==================================================
        trend_stack = (
            last["close"] > last["ema_20"] >
            last["ema_50"] > last["ema_200"]
        )

        ema_slope = df["ema_50"].iloc[-1] - df["ema_50"].iloc[-20]

        if not trend_stack or ema_slope <= 0:
            logger.debug(f"{self.symbol} → Rejected (Structural trend fail)")
            return None

        # ==================================================
        # LAYER 2 → STRENGTH FILTER
        # ==================================================
        if last["adx"] < 22:
            logger.debug(f"{self.symbol} → Rejected (Weak ADX)")
            return None

        if last["rsi"] < 50:
            logger.debug(f"{self.symbol} → Rejected (Weak RSI)")
            return None

        # Liquidity filter (adjust if needed)
        avg_vol = volume.rolling(20).mean().iloc[-1]
        if avg_vol < 500000:
            logger.debug(f"{self.symbol} → Rejected (Low liquidity)")
            return None

        # Avoid overextended stocks
        distance_from_ema20 = (
            (last["close"] - last["ema_20"]) / last["ema_20"]
        )

        if distance_from_ema20 > 0.10:
            logger.debug(f"{self.symbol} → Rejected (Overextended)")
            return None

        # ==================================================
        # LAYER 3 → SETUP FILTERS
        # ==================================================

        # -----------------------------
        # SETUP 1 → EMA20 PULLBACK
        # -----------------------------
        pullback = (
            last["low"] <= last["ema_20"] * 1.02 and
            last["close"] > last["ema_20"]
        )

        rsi_reset = 45 < last["rsi"] < 60
        bullish_candle = last["close"] > last["open"]

        if pullback and rsi_reset and bullish_candle:
            logger.info(
                f"{self.symbol} → EMA Pullback Setup | RSI {last['rsi']:.1f}"
            )
            return {
                "symbol": self.symbol,
                "strategy": "EMA Pullback",
                "bias": "BULLISH",
                "direction": "BUY",
                "order_type": "PULLBACK"
            }

        # -----------------------------
        # SETUP 2 → 30-DAY BREAKOUT
        # -----------------------------
        recent_high = df["high"].rolling(30).max().iloc[-2]
        vol_spike = last["volume"] > avg_vol * 1.5

        breakout = last["close"] > recent_high

        if breakout and vol_spike:
            logger.info(
                f"{self.symbol} → 30D Breakout | "
                f"Vol {last['volume']:.0f} > Avg {avg_vol:.0f}"
            )
            return {
                "symbol": self.symbol,
                "strategy": "30D Breakout",
                "bias": "BULLISH",
                "direction": "BUY",
                "order_type": "BREAKOUT"
            }

        # -----------------------------
        # NO VALID SETUP
        # -----------------------------
        logger.debug(f"{self.symbol} → No valid setup found")
        return None