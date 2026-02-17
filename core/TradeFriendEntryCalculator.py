from typing import Dict


class TradeFriendEntryCalculator:
    """
    PURPOSE
    -------
    Centralized entry / SL / target calculation
    Strategy-aware (BB, EMA, etc.)
    """

    @staticmethod
    def calculate(plan: Dict, indicators: Dict) -> Dict:
        """
        Returns:
        {
            entry,
            sl,
            target,
            confidence (optional)
        }
        """

        strategy = plan.get("strategy")
        direction = plan.get("direction", "BUY")

        last_close = indicators["close"]
        last_low = indicators["low"]
        bb_middle = indicators.get("bb_middle")

        # ==================================================
        # UPPER BOLLINGER BAND EXPANSION
        # ==================================================
        if strategy == "Upper Band Expansion":

            entry = last_close

            sl = min(last_low, bb_middle)

            risk = entry - sl
            target = entry + (risk * 1.2)

            return {
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "target": round(target, 2),
                "confidence": 2.0
            }

        # ==================================================
        # DEFAULT / FALLBACK (EMA / MID-BAND / OTHERS)
        # ==================================================
        entry = plan["entry"]
        sl = plan["sl"]

        risk = abs(entry - sl)
        target = entry + (risk * 2)

        return {
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "target": round(target, 2),
            "confidence": plan.get("confidence", 1.0)
        }
