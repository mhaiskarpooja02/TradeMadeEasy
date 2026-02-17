# signal_service.py

import pandas as pd
from datetime import datetime, timedelta
from utils.logger import get_logger

logger = get_logger(__name__)

class RangeboundService:

    # ------------------------------------------------------------
    # ➤ Identify yearly range (LL–HH) and % width
    # ------------------------------------------------------------
    def identify_range(self, df: pd.DataFrame, symbol: str):
        try:
            # 1) Clean numeric columns
            for col in ["close", "open", "high", "low", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
    
            if df.empty or "close" not in df.columns:
                return None
    
            # 2) Normalize date column
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
            elif "timestamp" in df.columns:
                df["date"] = pd.to_datetime(df["timestamp"], errors="coerce")
            elif "time" in df.columns:
                df["date"] = pd.to_datetime(df["time"], errors="coerce")
            else:
                # fallback to index if no date column exists
                df["date"] = pd.to_datetime(df.index, errors="coerce")
    
            df = df.dropna(subset=["date"])
    
            # 3) Filter last 1 year
            one_year_ago = datetime.now() - timedelta(days=365)
            df = df[df["date"] >= one_year_ago]
    
            if df.empty:
                return None
    
            # 4) Compute range metrics
            ll = df["low"].min()
            hh = df["high"].max()
    
            if ll == 0 or hh == 0:
                return None
    
            range_pct = round(((hh - ll) / ll) * 100, 2)
    
            return {
                "symbol": symbol,
                "year_low": float(ll),
                "year_high": float(hh),
                "range_percent": range_pct
            }
    
        except Exception as e:
            logger.error(f"Range identification failed for {symbol}: {e}")
            return None


    # ------------------------------------------------------------
    # ➤ Count how many times price touched low/high within tolerance
    # ------------------------------------------------------------
    def count_range_touches(self, df: pd.DataFrame, ll: float, hh: float, tolerance_pct: float = 1.5):
        try:
            tol_low = ll * (1 + tolerance_pct / 100)
            tol_high = hh * (1 - tolerance_pct / 100)

            low_touches = df[df["low"] <= tol_low].shape[0]
            high_touches = df[df["high"] >= tol_high].shape[0]

            return {
                "low_touches": low_touches,
                "high_touches": high_touches
            }
        except Exception as e:
            logger.error(f"Counting range touches failed: {e}")
            return {"low_touches": 0, "high_touches": 0}

    # ------------------------------------------------------------
    # ➤ Trend using EMA 20/50
    # ------------------------------------------------------------
    def get_trend(self, df: pd.DataFrame):
        try:
            df["ema20"] = df["close"].ewm(span=20).mean()
            df["ema50"] = df["close"].ewm(span=50).mean()

            if df["ema20"].iloc[-1] > df["ema50"].iloc[-1]:
                return "UP TREND"
            elif df["ema20"].iloc[-1] < df["ema50"].iloc[-1]:
                return "DOWN TREND"
            else:
                return "SIDEWAYS"
        except:
            return "SIDEWAYS"

    # ------------------------------------------------------------
    # ➤ Momentum: RSI14
    # ------------------------------------------------------------
    def get_momentum(self, df: pd.DataFrame):
        try:
            delta = df["close"].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return round(float(rsi.iloc[-1]), 2)
        except:
            return None

    # ------------------------------------------------------------
    # ➤ Reversal detection using last 3 candles
    # ------------------------------------------------------------
    def get_reversal(self, df: pd.DataFrame):
        try:
            c1, c2, c3 = df.tail(3).itertuples()

            # bullish reversal – higher low + green candle
            if c3.close > c3.open and c3.low > c2.low:
                return "BULLISH REVERSAL"

            # bearish reversal – lower high + red candle
            if c3.close < c3.open and c3.high < c2.high:
                return "BEARISH REVERSAL"

            return "NO REVERSAL"
        except:
            return "NO REVERSAL"

    # ------------------------------------------------------------
    # ➤ Breakout/Breakdown from yearly range
    # ------------------------------------------------------------
    def get_breakout(self, ltp, ll, hh):
        try:
            if ltp > hh * 1.01:
                return "BREAKOUT"
            if ltp < ll * 0.99:
                return "BREAKDOWN"
            return "NONE"
        except:
            return "NONE"

    # ------------------------------------------------------------
    # ➤ Prepare DB-ready record (pure range metrics)
    # ------------------------------------------------------------
    def evaluate_for_db(self, df: pd.DataFrame, symbol: str):
        base = self.identify_range(df, symbol)
        if not base:
            return None

        ll = base["year_low"]
        hh = base["year_high"]

        touches = self.count_range_touches(df, ll, hh)

        record = {
            "symbol": symbol,
            "date": df["date"].iloc[-1],
            "year_low": ll,
            "year_high": hh,
            "low_touches": touches["low_touches"],
            "high_touches": touches["high_touches"],
            "range_percent": base["range_percent"],
            "last_close": df["close"].iloc[-1],
            "updated_at": datetime.now()
        }

        return record

    # ------------------------------------------------------------
    # ➤ Calculate dynamic signal (BUY/STRONG BUY/EXIT/WAIT)
    # ------------------------------------------------------------
    def calculate_signal(self, ltp, record, df: pd.DataFrame):
        try:
            ll = record["year_low"]
            hh = record["year_high"]

            # Bottom of range
            if ltp <= ll * 1.03:
                trend = self.get_trend(df)
                rsi = self.get_momentum(df)
                reversal = self.get_reversal(df)
                breakout = self.get_breakout(ltp, ll, hh)

                # STRONG BUY conditions
                if trend == "UP TREND" and rsi and rsi < 40:
                    return "STRONG BUY"
                if reversal == "BULLISH REVERSAL":
                    return "BUY"
                if breakout == "BREAKDOWN":
                    return "WAIT"
                return "BUY"

            # Top of range
            elif ltp >= hh * 0.97:
                return "EXIT"

            # Middle of range
            else:
                return "WAIT"

        except Exception as e:
            logger.error(f"Signal calculation failed: {e}")
            return "WAIT"
