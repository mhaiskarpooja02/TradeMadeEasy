from abc import ABC, abstractmethod
from models.tradefriend_order_models import TradeFriendOrderRequest
from models.tradefriend_execution_result import TradeFriendExecutionResult


class TradeFriendBrokerAdapter(ABC):
    """
    Base contract for all broker adapters.
    Adapters MUST NOT touch DB or audit.
    """

    @abstractmethod
    def place_order(
        self,
        order: TradeFriendOrderRequest
    ) -> TradeFriendExecutionResult:
        """
        Execute broker order and return structured result.
        """
        raise NotImplementedError