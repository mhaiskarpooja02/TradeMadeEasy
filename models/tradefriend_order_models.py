from dataclasses import dataclass
from typing import Optional


@dataclass
class TradeFriendOrderRequest:
    """
    Standardized order request used by OMS.
    Broker-specific fields must NOT exist here.
    """

    trade_id: int
    symbol: str
    qty: int
    side: str
    order_mode: str = "LIVE"
    tag: Optional[str] = None