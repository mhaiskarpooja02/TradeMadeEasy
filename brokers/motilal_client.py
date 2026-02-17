# broker/motilal_client.py
from brokers.base_client import BaseBrokerClient

class MotilalClient(BaseBrokerClient):
    

    def place_order(self, security_id, qty, **kwargs):
        # Stub
        return {}
    
    # ------------------------------------------------------------------------
    def get_holdings(self):
        """
        Placeholder for holdings API.
        Returns empty list until real implementation is done.
        """
        return []
 