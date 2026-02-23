import time
import logging

from core.TradeFriendScheduler import TradeFriendScheduler
from utils.TradeFriendManager import TradeFriendManager

logger = logging.getLogger(__name__)


class TradeFriendAppEngine:
    """
    TradeFriend Application Engine
    ===============================

    Responsibilities:
    - Own lifecycle (start/stop)
    - Own system health integration
    - Initialize Manager (business layer)
    - Initialize Scheduler (time orchestration)
    - Act as supervisor loop

    Architecture:

        Engine
            ↓
        Manager (Business Logic)
            ↓
        Scheduler (Time-based execution)
    """

    # ==========================================================
    # INITIALIZATION
    # ==========================================================
    def __init__(self, health_service):
        """
        Initialize engine with system health dependency.
        """

        logger.info("🚀 Initializing TradeFriendAppEngine...")

        self.health_service = health_service
        self._running = False

        # ------------------------------------------------------
        # BUSINESS MANAGER
        # ------------------------------------------------------
        self.manager = TradeFriendManager()

        # Inject health service into manager (if supported)
        if hasattr(self.manager, "health_service"):
            self.manager.health_service = self.health_service
        elif hasattr(self.manager, "set_health_service"):
            self.manager.set_health_service(self.health_service)

        # ------------------------------------------------------
        # SCHEDULER (Time Orchestrator)
        # ------------------------------------------------------
        self.scheduler = TradeFriendScheduler(
            manager=self.manager
        )

        logger.info("✅ TradeFriendAppEngine initialized successfully")

    # ==========================================================
    # START ENGINE
    # ==========================================================
    def start(self):
        """
        Start engine and scheduler.
        """

        if self._running:
            logger.warning("Engine already running.")
            return

        logger.info("▶ Starting TradeFriend Engine...")
        self._running = True

        # ------------------------------------------------------
        # START SCHEDULER THREAD
        # ------------------------------------------------------
        try:
            self.scheduler.start()
            logger.info("🕒 Scheduler started successfully")
        except Exception:
            logger.exception("❌ Failed to start scheduler")
            self._running = False
            return

        # ------------------------------------------------------
        # SUPERVISOR LOOP
        # ------------------------------------------------------
        while self._running:
            try:
                # ----------------------------------------------
                # SYSTEM HEALTH CHECK
                # ----------------------------------------------
                if not self.health_service.is_system_ready():
                    logger.warning("⏸ System not healthy. Trading paused.")
                    time.sleep(5)
                    continue

                # ----------------------------------------------
                # HEARTBEAT
                # ----------------------------------------------
                logger.debug("💓 Engine heartbeat OK")

            except Exception:
                logger.exception("❌ Engine supervisor error")

            time.sleep(10)

    # ==========================================================
    # STOP ENGINE
    # ==========================================================
    def stop(self):
        """
        Stop engine and scheduler safely.
        """

        if not self._running:
            logger.warning("Engine already stopped.")
            return

        logger.info("⏹ Stopping TradeFriend Engine...")
        self._running = False

        # Stop scheduler safely
        try:
            self.scheduler.stop()
            logger.info("🛑 Scheduler stopped successfully")
        except Exception:
            logger.exception("❌ Error while stopping scheduler")

        logger.info("✅ TradeFriend Engine stopped cleanly")

    # ==========================================================
    # OPTIONAL ACCESSORS
    # ==========================================================
    def is_running(self):
        return self._running

    def get_manager(self):
        return self.manager

    def get_scheduler(self):
        return self.scheduler