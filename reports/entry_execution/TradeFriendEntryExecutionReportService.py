import logging

from Servieces.TradeFriendInitialScanReportService import (
    TradeFriendDailyScanReportService
)
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from reports.entry_execution.TradeFriendEntryexecutionreportpdfbuilder import (
    EntryExecutionReportPdfBuilder
)

from utils.logger import get_logger
logger = get_logger(__name__)


class TradeFriendEntryExecutionReportService:
    """
    PURPOSE:
    - Generate EOD Entry Status Report
    - Apply business logic
    - Build PDF and send email
    """

    @staticmethod
    def _derive_entry_state(trade: dict) -> str:
        """
        Business rule:
        - PENDING  -> no qty consumed
        - PARTIAL  -> some qty consumed
        - FILLED   -> no remaining qty
        """
        if trade["remaining_qty"] == trade["initial_qty"]:
            return "PENDING"
        elif trade["remaining_qty"] > 0:
            return "PARTIAL"
        return "FILLED"

    @staticmethod
    def generate_and_send(report_date: str):
        try:
            raw_trades = TradeFriendTradeRepo().fetch_entries_by_date(
                report_date
            )

            if not raw_trades:
                logger.info(
                    "📭 Entry Report skipped — no entries today"
                )
                return

            # -------------------------
            # BUSINESS LOGIC
            # -------------------------
            trades = []

            for row in raw_trades:
                t = dict(row)

                t["derived_state"] = (
                    TradeFriendEntryExecutionReportService
                    ._derive_entry_state(t)
                )

                trades.append(t)

            # -------------------------
            # PDF
            # -------------------------
            pdf_path = (
                f"reports/entry_execution/"
                f"entry_execution_{report_date}.pdf"
            )

            EntryExecutionReportPdfBuilder().build(
                report_date=report_date,
                trades=trades,
                output_path=pdf_path
            )

            # -------------------------
            # EMAIL
            # -------------------------
            TradeFriendDailyScanReportService.send_email(
                scan_date=report_date,
                scan_results=trades,
                attachments=[pdf_path]
            )

            logger.info(
                "📨 Entry Status Report sent | Trades=%d",
                len(trades)
            )

        except Exception as e:
            logger.exception(
                f"❌ Entry execution report failed: {e}"
            )
