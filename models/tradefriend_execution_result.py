from dataclasses import dataclass
from typing import Optional


@dataclass
class TradeFriendExecutionResult:
    success: bool
    broker_order_id: Optional[str]
    raw_response: Optional[dict]
    error: Optional[str]