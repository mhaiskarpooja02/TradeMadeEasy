from dataclasses import dataclass
from typing import Optional

@dataclass
class TradeFriendOrderRequest:
    symbol: str
    security_id: str
    qty: int
    side: str = "BUY"
    order_type: str = "MARKET"
    product_type: str = "INTRADAY"
    price: Optional[float] = None
    tag: Optional[str] = None
