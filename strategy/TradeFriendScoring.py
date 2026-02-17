class TradeFriendScoring:
    """
    PURPOSE:
    - Assign confidence score to a swing setup
    - Used for analytics, ranking, dashboards
    """

    def score(self, signal: dict) -> float:
        """
        signal keys expected:
        - rr
        - trend_strength
        - volume_confirmed
        """

        score = 0.0

        rr = signal.get("rr", 0)
        if rr >= 3:
            score += 0.4
        elif rr >= 2:
            score += 0.3
        elif rr >= 1.5:
            score += 0.2

        if signal.get("trend_strength") == "STRONG":
            score += 0.3
        elif signal.get("trend_strength") == "MODERATE":
            score += 0.2

        if signal.get("volume_confirmed"):
            score += 0.3

        return round(min(score, 1.0), 2)
