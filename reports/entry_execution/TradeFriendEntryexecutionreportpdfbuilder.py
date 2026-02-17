from reportlab.platypus import Paragraph
from reports.base.TradeFriendPdfBase import TradeFriendPdfBase


class EntryExecutionReportPdfBuilder:
    """
    PURPOSE:
    - Build Entry Status PDF (EOD)
    - DB-driven data (already enriched)
    - NO business logic
    - NO DB / API calls
    """

    def build(
        self,
        *,
        report_date: str,
        trades: list,
        output_path: str
    ) -> str:
        """
        :param report_date: YYYY-MM-DD
        :param trades: Enriched trade dicts
        :param output_path: Full PDF path
        """

        if not trades:
            return ""

        pdf = TradeFriendPdfBase(output_path)

        # -------------------------
        # HEADER
        # -------------------------
        pdf.add_title(
            f"TradeFriend Entry Status Report — {report_date}"
        )

        pdf.add_meta(
            f"<b>Total Planned Entries:</b> {len(trades)}"
        )

        pdf.add_timestamp()

        # -------------------------
        # TABLE
        # -------------------------
        headers = [
            "Symbol",
            "Entry Price",
            "Qty",
            "Position Value",
            "Entry Day",
            "State"
        ]

        rows = []

        for t in trades:
            rows.append([
                t.get("symbol", "-"),
                round(t.get("entry", 0), 2),
                t.get("qty", "-"),
                round(t.get("position_value", 0), 2),
                t.get("entry_day", "-"),
                t.get("derived_state", "-"),
            ])

        pdf.add_table(
            headers=headers,
            rows=rows,
            col_widths=[
                80,   # Symbol
                70,   # Entry
                50,   # Qty
                90,   # Position Value
                70,   # Entry Day
                60    # State
            ]
        )

        return pdf.build()
