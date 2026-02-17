# broker/base_client.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseBrokerClient(ABC):
    """Abstract base for all broker clients."""

    @abstractmethod
    def get_holdings(self) -> List[Dict[str, Any]]:
        """Fetch holdings from broker."""
        pass

    @abstractmethod
    def place_order(self, security_id: str, qty: int, **kwargs) -> Dict[str, Any]:
        """Place order via broker."""
        pass
