import logging
import shutil
from pathlib import Path
from datetime import datetime

from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendWatchlistRepo import TradeFriendWatchlistRepo
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from utils.logger import get_logger

logger = get_logger(__name__)

class TradeFriendCleanupService:
    """
    Centralized maintenance service.

    Responsible for:
    - Cleaning stale DB records
    - Cleaning logs & reports
    - Future maintenance extensions
    """

    def __init__(self):
        

        # 🔹 Declare repos internally
        self.trade_repo = TradeFriendTradeRepo()
        self.watchlist_repo = TradeFriendWatchlistRepo()
        self.swing_plan_repo = TradeFriendSwingPlanRepo()

    # -------------------------------------------------
    # PUBLIC ENTRY POINT
    # -------------------------------------------------
    def run(self, base_path=".", keep_days=4):
        logger.info("🧹 Cleanup Service Started")

        self._cleanup_database()
        self._cleanup_files(base_path, keep_days)

        logger.info("✅ Cleanup Service Completed")

    # -------------------------------------------------
    # DATABASE CLEANUP
    # -------------------------------------------------
    def _cleanup_database(self):

        # 1️⃣ Remove invalid trades
        try:
            self.trade_repo.delete_old_invalid_trades()
            logger.info("🗑 Old INVALID trades removed")
        except Exception:
            logger.exception("❌ Failed cleaning INVALID trades")

        # 2️⃣ Remove stale READY trades (never triggered)
        try:
            deleted = self.trade_repo.cleanup_active_trades()
            logger.info(f"🗑 Stale READY trades removed | count={deleted}")
        except Exception:
            logger.exception("❌ Failed cleaning stale READY trades")

        # 3️⃣ Clean watchlist
        try:
            self.watchlist_repo.delete_untriggered_older_than(days=7)
            logger.info("🗑 Old untriggered watchlist removed")
        except Exception:
            logger.exception("❌ Failed cleaning watchlist")

        # 4️⃣ Remove orphan swing plans
        try:
            self.swing_plan_repo.delete_orphan_plans()
            logger.info("🗑 Orphan swing plans removed")
        except Exception:
            logger.exception("❌ Failed cleaning swing plans")

        # 5️⃣ Cleanup terminal plans
        try:
            self.swing_plan_repo.cleanup_old_terminal_plans()
            logger.info("🗑 Deleted terminal plans (EXPIRED, TRIGGERED, REJECTED)")
        except Exception:
            logger.exception("❌ Failed cleaning swing plans")

        # 6️⃣ Remove orphan trades (very important)
        try:
            valid_plan_ids = self.swing_plan_repo.get_valid_plan_ids()

            deleted = self.trade_repo.delete_orphan_active_trades(valid_plan_ids)

            logger.info(f"🗑 Orphan trades removed | count={deleted}")
        except Exception:
            logger.exception("❌ Failed cleaning orphan trades")

            
    # -------------------------------------------------
    # FILE CLEANUP
    # -------------------------------------------------
    def _cleanup_files(self, base_path, keep_days):

        base = Path(base_path)
        logs_dir = base / "logs"
        reports_dir = base / "reports"

        # Clean logs (keep last N days)
        if logs_dir.exists():
            folders = []

            for folder in logs_dir.iterdir():
                if folder.is_dir():
                    try:
                        folder_date = datetime.strptime(folder.name, "%Y-%m-%d")
                        folders.append((folder_date, folder))
                    except ValueError:
                        continue

            folders.sort(reverse=True, key=lambda x: x[0])

            for _, folder in folders[keep_days:]:
                shutil.rmtree(folder, ignore_errors=True)
                logger.info(f"🗑 Deleted log folder {folder.name}")

        # Clean CSV reports
        if reports_dir.exists():
            for file in reports_dir.rglob("*"):
                if file.suffix.lower() in [".csv", ".pdf"]:
                    file.unlink(missing_ok=True)
                    logger.info(f"🗑 Deleted {file.suffix.upper()} {file.name}")