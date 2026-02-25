# utils/TradeFriendManager.py

import logging
from Servieces.TradeFriendBrokerReconciliationService import TradeFriendBrokerReconciliationService
from core.TradeFriendDecisionRunner import TradeFriendDecisionRunner
from core.TradeFriendSwingTradeMonitor import TradeFriendSwingTradeMonitor
from core.TradeFriendWatchlistEngine import WatchlistEngine


from core.TradeFriendSwingTriggerEngine import TradeFriendSwingTriggerEngine
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo
from reports.entry_execution.TradeFriendEntryExecutionReportService import TradeFriendEntryExecutionReportService

from utils.logger import get_logger
logger = get_logger(__name__)


class TradeFriendManager:
    """
    Orchestrator for TradeFriend flow.
    Triggered via Dashboard buttons.
    """

    # ---------------- Daily Scan ----------------
    def tf_daily_scan(self, mode: str):
        logger.info(f"📊 TradeFriend Daily scan started | Mode={mode}")
        engine = WatchlistEngine()
        engine.run()
        logger.info("✅ TradeFriend Daily scan completed")

    # ---------------- Morning Confirmation ----------------
    def tf_morning_confirm(self, capital: float, mode: str):
        logger.info(f"🚀 TradeFriend Morning confirmation started | Mode={mode}")

        # # 👉 scorer can be simple for now
        # scorer = None  # or DummyScorer()

        # runner = TradeFriendDecisionRunner()
        # runner.run()

        # logger.info("✅ TradeFriend Morning confirmation completed")

    # ---------------- Trade Monitoring ----------------
    def tf_monitor(self):
        logger.info("🔁 TradeFriend swing monitoring started")
        monitor = TradeFriendSwingTradeMonitor()
        monitor.run()
        logger.info("✅ TradeFriend swing monitoring completed")

    # ---------------- Trade Execution ----------------
    def tf_trigger_engine(self):
        """
        Phase-2 Trigger Engine
        - READY → OPEN
        - No decision logic
        - No plans
        """
        logger.info("🚀 Trigger Engine invoked")

        settings = TradeFriendSettingsRepo().fetch()

        engine = TradeFriendSwingTriggerEngine(
            capital=settings["available_swing_capital"]
        )
        engine.run()
    # ------------------------
    # New: Decision Runner
    # ------------------------
    def tf_decision_runner(self):
        """
        Wrapper to run DecisionRunner phase manually or via scheduler.
        """
        logger.info("🧠 TradeFriend DecisionRunner started")
        runner = TradeFriendDecisionRunner()
        runner.run()
        logger.info("✅ TradeFriend DecisionRunner completed")

    # ----------------------------------------------
    # 📊 END-OF-DAY REPORT ORCHESTRATION
    #
    # - Generates all EOD trade reports
    # - Entry execution summary (PDF)
    # - Sends reports via static mail service
    # - Invoked ONLY by Scheduler (time-guarded)
    # ----------------------------------------------
    def tf_generate_eod_reports(self, report_date: str):
        logger.info("🧠 TradeFriend EOD Report generation started")
        TradeFriendEntryExecutionReportService.generate_and_send(
            report_date
        )
        logger.info("✅ TradeFriend EOD Report generation completed")

    # ----------------------------------------------
    # 🔁 RECONCILIATION SERVICE
    # ----------------------------------------------
    def tf_reconciliation_service(self):
        """
        Sync local order/trade state with broker reality.
        - No trigger logic
        - No new order placement
        - Only status correction
        """
        logger.info("🔁 TradeFriend Reconciliation started")
    
        
    
        service = TradeFriendBrokerReconciliationService()
        service.run()
    
        logger.info("✅ TradeFriend Reconciliation completed")