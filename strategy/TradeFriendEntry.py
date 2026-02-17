import talib


class TradeFriendEntry:
    """
    PURPOSE:
    - Confirm entry (WHEN to trade)
    - Uses lower timeframe confirmation
    """

    def __init__(self, df, symbol):
        self.df = df.copy()
        self.symbol = symbol

    def confirm_entry(self):
        df = self.df

        if df.empty or len(df) < 30:
            return None

        close = df["close"].astype(float)
        low = df["low"].astype(float)

        # Indicators
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = talib.BBANDS(
            close, timeperiod=20
        )
        df["ema_20"] = talib.EMA(close, timeperiod=20)
        df["rsi"] = talib.RSI(close, timeperiod=14)

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # -------- ENTRY LOGIC --------
        crossed_mid = (
            prev["close"] <= prev["bb_middle"]
            and last["close"] > last["bb_middle"]
        )

        bullish_engulf = (
            last["close"] > last["open"]
            and prev["close"] < prev["open"]
            and last["close"] > prev["open"]
        )

        momentum_ok = last["rsi"] > 55
        ema_support = last["close"] > last["ema_20"]

        if not (crossed_mid and bullish_engulf and momentum_ok and ema_support):
            return None

        entry = round(last["close"], 2)
        sl = round(min(last["bb_middle"], low[-5:].min()) * 0.99, 2)
        target = round(entry + (entry - sl) * 2, 2)

        return {
            "symbol": self.symbol,
            "entry": entry,
            "sl": sl,
            "target1": target,
            "reason": "Mid-band recovery confirmation"
        }
