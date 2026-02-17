from typing import List, Dict, Any
from utils.logger import get_logger
from brokers.dhan_clientold import DhanClient
from brokers.angel_client import AngelClient

logger = get_logger(__name__)

# Registry for all brokers
BROKER_REGISTRY = {}

def register_broker(name):
    def decorator(cls):
        BROKER_REGISTRY[name] = cls
        return cls
    return decorator

# ---------------- Base Broker ----------------
class BaseBroker:
    def get_holdings(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_ltp(self, *args, **kwargs):
        raise NotImplementedError


# ---------------- Wrap Dhan ----------------
@register_broker("Dhan")
class DhanBroker(BaseBroker):
    def __init__(self):
        self.client = DhanClient()

    def get_holdings(self):
        return self.client.get_holdings()

    def get_ltp(self, exchange, security_id):
        return self.client.get_ltp(exchange, security_id)


# ---------------- Wrap AngelOne ----------------
@register_broker("AngelOne")
class AngelOneBroker(BaseBroker):
    def __init__(self):
        self.client = AngelClient()

    def get_holdings(self):
        logger.info("AngelOne: get_holdings not implemented yet")
        return []

    def get_ltp(self, resolved_symbol: dict):
        return self.client.get_ltp(resolved_symbol)


# ---------------- Motilal Oswal ----------------
@register_broker("MotilalOswal")
class MotilalOswalBroker(BaseBroker):
    def __init__(self):
        logger.info("MotilalOswal client not implemented yet")

    def get_holdings(self):
        logger.info("MotilalOswal: get_holdings not implemented yet")
        return []

    def get_ltp(self, *args, **kwargs):
        logger.info("MotilalOswal: get_ltp not implemented yet")
        return None
