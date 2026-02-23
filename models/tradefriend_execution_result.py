class TradeFriendExecutionResult:
    """
    Standard broker execution response object
    Used by all adapters (Angel / Dhan / Future brokers)
    """

    def __init__(
        self,
        success: bool,
        broker_order_id: str | None = None,
        raw_response: dict | None = None,
        error: str | None = None,
    ):
        self.success = success
        self.broker_order_id = broker_order_id
        self.raw_response = raw_response
        self.error = error

    # ----------------------------------------
    # SUCCESS FACTORY
    # ----------------------------------------
    @staticmethod
    def success(broker_order_id: str, raw_response: dict | None = None):
        return TradeFriendExecutionResult(
            success=True,
            broker_order_id=broker_order_id,
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
            raw_response=raw_response,
            error=error,
        )

    # ----------------------------------------
    # BOOL SUPPORT
    # ----------------------------------------
    def __bool__(self):
        return self.success