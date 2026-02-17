from utils.logger import get_logger
from db.TradeFriendOrderConfigRepo import TradeFriendOrderConfigRepo

logger = get_logger(__name__)


class TradeFriendActiveBrokerService:
    """
    PURPOSE:
    - Decide active broker for ENTRY orders
    - Reads OMS config only
    - NO DB writes, NO broker calls
    """

    BROKER_PAPER = "PAPER"
    BROKER_DHAN = "DHAN"
    BROKER_ANGEL = "ANGEL"

    def __init__(self):
        self.config_repo = TradeFriendOrderConfigRepo()

    def get_active_broker(self) -> str | None:
        """
        RETURNS:
        - 'PAPER'
        - 'DHAN'
        - 'ANGEL'
        - None (no broker allowed)
        """

        cfg = self.config_repo.get()

        # ---------------------------
        # PAPER MODE (GLOBAL OVERRIDE)
        # ---------------------------
        if cfg.get("order_mode") == "PAPER":
            logger.debug("OMS in PAPER mode → using PAPER broker")
            return self.BROKER_PAPER

        # ---------------------------
        # LIVE MODE – PRIORITY BASED
        # ---------------------------
        if cfg.get("dhan_enabled") and cfg.get("dhan_auto_order"):
            logger.debug("Active broker resolved → DHAN")
            return self.BROKER_DHAN

        if cfg.get("angel_enabled") and cfg.get("angel_auto_order"):
            logger.debug("Active broker resolved → ANGEL")
            return self.BROKER_ANGEL

        logger.warning("No active broker found in OMS config")
        return None
