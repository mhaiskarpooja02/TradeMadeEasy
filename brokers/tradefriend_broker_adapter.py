from abc import ABC, abstractmethod
from core.tradefriend_order_models import TradeFriendOrderRequest

class TradeFriendBrokerAdapter(ABC):

    @abstractmethod
    def place_order(self, order: TradeFriendOrderRequest) -> bool:
        """
        Places order with broker.
        Must return True ONLY if broker confirms acceptance.
        """
        pass