# core/TradeFriendConfidenceScorer.py

class TradeFriendConfidenceScorer:
    """
    PURPOSE:
    - Calculate confidence score at SCAN time only
    - Stateless & deterministic
    - Output range: 1–10
    """

    def score(self, context: dict) -> int:
        score = 0

        # -------------------------------------------------
        # Trend alignment
        # -------------------------------------------------
        if context.get("htf_trend") == "BULLISH":
            score += 2

        # -------------------------------------------------
        # Location quality
        # -------------------------------------------------
        if context.get("location") in (
            "Mid-Band Support",
            "Upper Band Expansion",
            "EMA20",
            "VWAP"
        ):
            score += 2

        # -------------------------------------------------
        # Momentum (RSI sweet zone)
        # -------------------------------------------------
        rsi = context.get("rsi", 0)
        if 45 <= rsi <= 65:
            score += 1

        # -------------------------------------------------
        # Volume confirmation
        # -------------------------------------------------
        if context.get("volume_ratio", 0) >= 1.3:
            score += 2

        # -------------------------------------------------
        # Risk–Reward sanity
        # -------------------------------------------------
        if context.get("rr", 0) >= 1.5:
            score += 1

        # -------------------------------------------------
        # Clamp (1–10)
        # -------------------------------------------------
        return max(1, min(score, 10))
