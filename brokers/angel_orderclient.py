# =============================================================================
# Singleton initializer for AngelOrderClient
# =============================================================================

from brokers.angel_order_client import AngelOrderClient

_client_instance = None


def init_client():
    global _client_instance

    if _client_instance is None:
        _client_instance = AngelOrderClient()

    return _client_instance