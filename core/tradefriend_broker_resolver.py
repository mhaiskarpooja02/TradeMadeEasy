# core/tradefriend_broker_resolver.py

class TradeFriendBrokerResolver:
    """
    Decides which broker(s) should be used for ENTRY execution.
    Policy layer only.
    """

    def __init__(self, settings_repo):
        self.settings_repo = settings_repo

    def resolve_live_brokers(self, available_brokers: dict) -> list[str]:
        """
        Returns ordered list of brokers to attempt.
        """

        # Example: priority order can come from settings later
        priority_order = ["ANGEL", "DHAN"]

        enabled_brokers = []

        for broker in priority_order:
            adapter = available_brokers.get(broker)

            if not adapter:
                continue

            if hasattr(adapter, "is_enabled") and not adapter.is_enabled():
                continue

            enabled_brokers.append(broker)

        return enabled_brokers