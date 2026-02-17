# core/PlanStatus.py
from enum import Enum

class PlanStatus(str, Enum):
    PLANNED = "PLANNED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TRIGGERED = "TRIGGERED"
    EXPIRED = "EXPIRED"
    HOLD = "HOLD"  # New status for 7-day hold

class TradeStatus(str, Enum):
    READY   = "READY"     # waiting for entry trigger
    PARTIAL = "PARTIAL"   # entry in progress
    OPEN    = "OPEN"      # fully entered
    EXITED  = "EXITED"
    INVALID = "INVALID"
    SKIPPED = "SKIPPED"
    ENTRY_IN_PROGRESS = "ENTRY_IN_PROGRESS"

class HoldMode(int, Enum):
    OPEN    = 0   # no partial booking yet
    PARTIAL = 1   # partial profit booked
    RUNNER  = 2   # runner mode

class ExitReason(str, Enum):
    INITIAL_SL_HIT      = "INITIAL_SL_HIT"
    PARTIAL_EXIT_25     = "PARTIAL_EXIT_25"
    BREAKEVEN_SL_HIT    = "BREAKEVEN_SL_HIT"
    PARTIAL_EXIT_50     = "PARTIAL_EXIT_50"
    PROFIT_LOCK_SL_HIT  = "PROFIT_LOCK_SL_HIT"
    PARTIAL_EXIT_75     = "PARTIAL_EXIT_75"
    TRAILING_SL_HIT     = "TRAILING_SL_HIT"
    TARGET_HIT_FULL     = "TARGET_HIT_FULL"
    MANUAL_EXIT         = "MANUAL_EXIT"