from utils.logger import get_logger
from core.TradeFriendPositionSizer import TradeFriendPositionSizer
from core.TradeFriendRiskManager import TradeFriendRiskManager
from const.PlanStatus import PlanStatus

logger = get_logger(__name__)

class PlanManager:
    """
    Single authoritative plan decision engine
    """

    def __init__(self, trade_repo):
        self.trade_repo = trade_repo
        self.sizer = TradeFriendPositionSizer()
        self.risk_manager = TradeFriendRiskManager()

    def evaluate_plan(self, plan: dict) -> dict:
        symbol = plan.get("symbol")
        plan_id = plan.get("id")

        logger.info(f"🧠 PlanManager | START | {symbol} | plan_id={plan_id}")

        # -------------------------------
        # Parse
        # -------------------------------
        try:
            entry = float(plan["entry"])
            sl = float(plan["sl"])
            target = float(plan.get("target1") or plan.get("target"))
        except Exception as e:
            return self._reject(plan, f"Parsing failed: {e}")

        if entry <= 0 or sl <= 0 or entry <= sl:
            return self._reject(plan, "Invalid price structure")

        # -------------------------------
        # Duplicate trade
        # -------------------------------
        if self.trade_repo.has_open_trade(symbol):
            return self._hold(plan, "Duplicate open trade")

        # -------------------------------
        # Confidence
        # -------------------------------
        confidence = self._derive_confidence(plan)
        if confidence < 6:
            return self._reject(plan, f"Low confidence ({confidence})")

        # -------------------------------
        # Position sizing
        # -------------------------------
        try:
            sizing = self.sizer.calculate(entry_price=entry)
            qty = int(sizing["qty"])
            position_value = float(sizing["position_value"])
        except Exception as e:
            return self._reject(plan, f"Sizing error: {e}")

        if qty <= 0:
            return self._reject(plan, "Qty resolved to zero")

        # -------------------------------
        # Risk check
        # -------------------------------
        allowed, reason, _ = self.risk_manager.can_take_trade(
            trade_repo=self.trade_repo,
            position_value=position_value,
            entry_price=entry
        )

        if not allowed:
            return self._hold(plan, f"Risk blocked: {reason}")

        # -------------------------------
        # APPROVE
        # -------------------------------
        return {
            "decision": PlanStatus.APPROVED,
            "trade": {
                "symbol": symbol,
                "entry": entry,
                "sl": sl,
                "target": target,
                "qty": qty,
                "position_value": position_value,
                "confidence": confidence,
                "source_plan_id": plan_id
            },
            "reason": "OK"
        }

    # =========================
    # Helpers
    # =========================
    def _derive_confidence(self, plan: dict) -> int:
        score = 0

        if plan.get("strategy") in ("BREAKOUT", "TREND_PULLBACK"):
            score += 3
        elif plan.get("strategy"):
            score += 2

        rr = float(plan.get("rr", 0))
        if rr >= 2:
            score += 2
        elif rr >= 1.5:
            score += 1

        if plan.get("order_type") == "LIMIT":
            score += 1
        if plan.get("trade_type") == "SWING":
            score += 1

        return score

    def _reject(self, plan, reason):
        logger.warning(f"❌ REJECTED | {reason} | plan_id={plan.get('id')}")
        return {"decision": PlanStatus.REJECTED, "trade": None, "reason": reason}

    def _hold(self, plan, reason):
        logger.info(f"⏳ HOLD | {reason} | plan_id={plan.get('id')}")
        return {"decision": PlanStatus.HOLD, "trade": None, "reason": reason}
