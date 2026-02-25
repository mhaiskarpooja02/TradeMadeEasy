import talib
import logging
from utils.logger import get_logger

logger = get_logger(__name__)

class TradeFriendScanner:
    """
    PURPOSE:
    - Find swing candidates (WHAT to trade)
    - Uses higher-timeframe bias
    - Saves only SYMBOL + STRATEGY
    """

    def __init__(self, df, symbol):
        self.df = df.copy()
        self.symbol = symbol

    def scan(self):
        df = self.df

        logger.info(f"{self.symbol} → started scanner")
        # Safety checks
        if df.empty or len(df) < 60:
            logger.info(f"{self.symbol} → Skipped (insufficient data)")
            return None

        close = df["close"].astype(float)
        volume = df["volume"].astype(float)

        # Indicators
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = talib.BBANDS(
            close, timeperiod=20
        )
        df["ema_50"] = talib.EMA(close, timeperiod=50)
        df["rsi"] = talib.RSI(close, timeperiod=14)

        last = df.iloc[-1]

        # --------- GLOBAL TREND FILTER ----------
        ema_slope = df["ema_50"].iloc[-1] - df["ema_50"].iloc[-5]
        if ema_slope <= 0:
            logger.debug(
                f"{self.symbol} → Rejected (EMA slope down: {ema_slope:.2f})"
            )
            return None

        # --------- SETUP 1: MID-BAND SUPPORT ----------
        near_mid = (
            last["low"] <= last["bb_middle"] * 1.01
            and last["close"] > last["bb_middle"]
        )

        bullish_candle = last["close"] > last["open"]

        if near_mid and bullish_candle and last["rsi"] < 65:
            logger.info(
                f"{self.symbol} → Mid-Band Support detected | RSI {last['rsi']:.1f}"
            )
            return {
                "symbol": self.symbol,
                "strategy": "Mid-Band Support",
                "bias": "BULLISH",
                "direction": "BUY",
                "order_type": "PULLBACK"
            }

        # --------- SETUP 2: UPPER BAND EXPANSION ----------
        vol_avg = volume.rolling(20).mean().iloc[-1]
        breakout = last["close"] > last["bb_upper"]
        vol_spike = last["volume"] > vol_avg * 1.3

        if breakout and vol_spike and 60 < last["rsi"] < 80:
            logger.info(
                f"{self.symbol} → Upper Band Expansion | "
                f"Vol {last['volume']:.0f} > Avg {vol_avg:.0f}"
            )
            return {
                "symbol": self.symbol,
                "strategy": "Upper Band Expansion",
                "bias": "BULLISH",
                "direction": "BUY",
                "order_type": "BREAKOUT"
            }

        # --------- NO SETUP ----------
        logger.debug(f"{self.symbol} → No valid setup found")
        return None