class MorningConfirmReport:
    """
    PURPOSE:
    - Collect morning confirmation decisions
    - Store rows in decision-specific buckets
    - Provide clean accessors for PDF / Email / Dashboard
    """

    DECISION_APPROVED = "APPROVED"
    DECISION_REJECTED = "REJECTED"
    DECISION_SKIPPED = "SKIPPED"

    def __init__(self, mode: str, capital: float):
        self.mode = mode
        self.capital = capital

        self._approved = []
        self._rejected = []
        self._skipped = []

    # -------------------------------------------------
    # ADD ENTRY
    # -------------------------------------------------
    def add(
        self,
        symbol: str,
        ltp,
        entry,
        sl,
        target,
        decision: str,
        reason: str,
        qty: int = 0,
        position_value: float = 0.0,
        confidence: int | None = None
    ):
        row = {
            "symbol": symbol or "",
            "ltp": ltp if ltp is not None else "-",
            "entry": entry if entry is not None else "-",
            "sl": sl if sl is not None else "-",
            "target": target if target is not None else "-",
            "decision": decision,
            "reason": reason or "",
            "qty": qty or "-",
            "position_value": position_value or "-",
            "confidence": confidence
        }

        if decision == self.DECISION_APPROVED:
            self._approved.append(row)
        elif decision == self.DECISION_REJECTED:
            self._rejected.append(row)
        else:
            self._skipped.append(row)

    # -------------------------------------------------
    # ACCESSORS (NO FILTERING NEEDED ANYWHERE ELSE)
    # -------------------------------------------------
    def approved(self) -> list:
        return self._approved

    def rejected(self) -> list:
        return self._rejected

    def skipped(self) -> list:
        return self._skipped

    # -------------------------------------------------
    # SUMMARY HELPERS
    # -------------------------------------------------
    def has_approved(self) -> bool:
        return len(self._approved) > 0

    def has_rejected(self) -> bool:
        return len(self._rejected) > 0

    def has_skipped(self) -> bool:
        return len(self._skipped) > 0

    def is_empty(self) -> bool:
        return not (self._approved or self._rejected or self._skipped)

    def summary(self) -> dict:
        return {
            "approved": len(self._approved),
            "rejected": len(self._rejected),
            "skipped": len(self._skipped),
            "total": (
                len(self._approved)
                + len(self._rejected)
                + len(self._skipped)
            )
        }
