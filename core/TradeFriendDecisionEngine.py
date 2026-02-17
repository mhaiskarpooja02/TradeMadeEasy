# core/TradeFriendDecisionEngine.py

from config.TradeFriendConfig import MIN_SCAN_CONFIDENCE
from utils.logger import get_logger
from core.TradeFriendPositionSizer import TradeFriendPositionSizer
from core.TradeFriendRiskManager import TradeFriendRiskManager
from const.TradeFriendPlanStatus import PlanStatus

logger = get_logger(__name__)


class TradeFriendDecisionEngine:
    """
    PURE DECISION ENGINE
    --------------------
    - Validate PLANNED swing plans
    - Derive confidence
    - Apply sizing & risk rules
    - RETURN decision only
    - ❌ No DB writes
    - ❌ No lifecycle mutation
    """

    def __init__(self, trade_repo):
        self.trade_repo = trade_repo
        self.sizer = TradeFriendPositionSizer()
        self.risk_manager = TradeFriendRiskManager()

    # ==================================================
    # PUBLIC ENTRY
    # ==================================================
    def evaluate(self, plan: dict) -> dict:
        symbol = plan.get("symbol", "UNKNOWN")
        plan_id = plan.get("id")

        logger.info(f"🧠 DecisionEngine | START | symbol={symbol} | plan_id={plan_id}")

        # -------------------------------
        # Parse prices
        # -------------------------------
        try:
            entry = float(plan["entry"])
            sl = float(plan["sl"])
            target = float(plan.get("target1") or plan.get("target") or 0)
        except Exception as e:
            return self._reject(symbol, plan, f"Plan parsing failed: {e}")

        if entry <= 0 or sl <= 0 or entry <= sl:
            return self._reject(symbol, plan, "Invalid price structure")

        # -------------------------------
        # Duplicate open trade
        # -------------------------------
        if self.trade_repo.has_open_trade(symbol):
            return self._hold(plan, "Duplicate open trade")

        # -------------------------------
        # Derive confidence
        # -------------------------------
        confidence = self._derive_confidence(plan)
        logger.info(f"📊 Confidence derived | plan_id={plan_id} | confidence={confidence}")

        if confidence < MIN_SCAN_CONFIDENCE:
            return self._reject(symbol, plan, f"Low confidence ({confidence})")

        # -------------------------------
        # Position sizing
        # -------------------------------
        try:
            sizing = self.sizer.calculate(entry_price=entry)
            qty = int(sizing["qty"])
            position_value = float(sizing["position_value"])
        except Exception as e:
            logger.exception("❌ DecisionEngine | Sizing failed")
            return self._reject(symbol, plan, f"Sizing error: {e}")

        if qty <= 0:
            return self._reject(symbol, plan, "Qty resolved to zero")

        logger.info(f"📐 Position sizing OK | plan_id={plan_id} | qty={qty} | position_value={position_value}")

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
        logger.info(f"✅ Plan APPROVED | plan_id={plan_id} | symbol={symbol} | qty={qty} | entry={entry}")

        return {
            "decision": PlanStatus.APPROVED,
            "reason": "OK",
            "trade": {
                "symbol": symbol,
                "entry": entry,
                "sl": sl,
                "target": target,
                "qty": qty,
                "position_value": position_value,
                "confidence": confidence,
                "source_plan_id": plan_id
            }
        }

    # ==================================================
    # CONFIDENCE CALCULATION
    # ==================================================
    def _derive_confidence(self, plan: dict) -> int:
        """
        Derive deterministic confidence from plan attributes.
        Logs each step and running score.
        """
        score = 0
        plan_id = plan.get("id")
        strategy = plan.get("strategy")
        rr = float(plan.get("rr", 0))
        order_type = plan.get("order_type")
        trade_type = plan.get("trade_type")

        logger.info(f"🧠 _derive_confidence START | plan_id={plan_id} | "
                    f"strategy={strategy}, rr={rr}, order_type={order_type}, trade_type={trade_type} | initial_score={score}")

        # Strategy contribution
        if strategy in ("BREAKOUT", "TREND_PULLBACK", "Mid-Band Support", "Upper Band Expansion"):
            score += 3
            logger.info(f"  ✅ Strategy bonus +3 | running_score={score} | strategy={strategy}")
        elif strategy:
            score += 2
            logger.info(f"  ✅ Strategy minor bonus +2 | running_score={score} | strategy={strategy}")
        else:
            logger.info(f"  ⚠️ Strategy missing or unknown | running_score={score}")

        # RR contribution
        if rr >= 2:
            score += 2
            logger.info(f"  ✅ RR bonus +2 | running_score={score} | rr={rr}")
        elif rr >= 1.5:
            score += 1
            logger.info(f"  ✅ RR bonus +1 | running_score={score} | rr={rr}")
        else:
            logger.info(f"  ⚠️ RR too low | running_score={score} | rr={rr}")

        # Order type contribution
        if order_type in ("LIMIT", "PULLBACK", "BREAKOUT"):
            score += 1
            logger.info(f"  ✅ Order type bonus +1 | running_score={score} | order_type={order_type}")
        else:
            logger.info(f"  ⚠️ Order type no bonus | running_score={score} | order_type={order_type}")

        # Trade type contribution
        if trade_type == "SWING":
            score += 1
            logger.info(f"  ✅ Trade type bonus +1 | running_score={score} | trade_type={trade_type}")
        else:
            logger.info(f"  ⚠️ Trade type no bonus | running_score={score} | trade_type={trade_type}")

        logger.info(f"🧠 _derive_confidence END | plan_id={plan_id} | final_score={score}")
        return score

    # ==================================================
    # REJECTION / HOLD
    # ==================================================
    def _reject(self, symbol: str, plan: dict, reason: str) -> dict:
        logger.warning(f"❌ REJECTED | reason={reason} | plan_id={plan.get('id')} | symbol={symbol}")
        return {"decision": PlanStatus.REJECTED, "trade": None, "reason": reason}

    def _hold(self, plan: dict, reason: str) -> dict:
        logger.info(f"⏳ HOLD | reason={reason} | plan_id={plan.get('id')} | symbol={plan.get('symbol')}")
        return {"decision": PlanStatus.HOLD, "trade": None, "reason": reason}
