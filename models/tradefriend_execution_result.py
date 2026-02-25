# models/tradefriend_execution_result.py

class TradeFriendExecutionResult:
    """
    Standard broker execution response object
    Used by all adapters (Angel / Dhan / Future brokers)
    """

    def __init__(
        self,
        success: bool,
        broker_order_id: str | None = None,
        unique_order_id: str | None = None,   # Angel specific support
        filled_qty: int = 0,
        avg_price: float = 0.0,
        raw_response: dict | None = None,
        error: str | None = None,
    ):
        self.success = success
        self.broker_order_id = broker_order_id
        self.unique_order_id = unique_order_id
        self.filled_qty = filled_qty
        self.avg_price = avg_price
        self.raw_response = raw_response
        self.error = error

    # ----------------------------------------
    # SUCCESS FACTORY
    # ----------------------------------------
    @staticmethod
    def success(
        broker_order_id: str,
        unique_order_id: str | None = None,
        filled_qty: int = 0,
        avg_price: float = 0.0,
        raw_response: dict | None = None,
    ):
        return TradeFriendExecutionResult(
            success=True,
            broker_order_id=broker_order_id,
            unique_order_id=unique_order_id,
            filled_qty=filled_qty,
            avg_price=avg_price,
            raw_response=raw_response,
            error=None,
        )

    # ----------------------------------------
    # FAILURE FACTORY
    # ----------------------------------------
    @staticmethod
    def failure(error: str, raw_response: dict | None = None):
        return TradeFriendExecutionResult(
            success=False,
            broker_order_id=None,
            unique_order_id=None,
            filled_qty=0,
            avg_price=0.0,
            raw_response=raw_response,
            error=error,
        )

    # ----------------------------------------
    # BOOL SUPPORT
    # ----------------------------------------
    def __bool__(self):
        return self.success