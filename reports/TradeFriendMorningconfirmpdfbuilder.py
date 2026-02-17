# reports/MorningConfirmPdfBuilder.py

from reports.base.TradeFriendPdfBase import TradeFriendPdfBase
from reportlab.platypus import Paragraph


class MorningConfirmPdfBuilder:

    def build(self, *, title, rows,   filename_suffix: str, mode="", capital=0):
        if not rows:
            return ""


        output_path = f"reports/morning_confirm/morning_confirm_{filename_suffix}.pdf"
        pdf = TradeFriendPdfBase(output_path)

        pdf.add_title(title)
        pdf.add_meta(
            f"<b>Mode:</b> {mode or '-'} &nbsp;&nbsp; "
            f"<b>Capital:</b> ₹{capital or '-'}"
        )
        pdf.add_timestamp()

        headers = [
            "Symbol", "LTP", "Entry", "SL", "Target",
            "Decision", "Reason", "Qty", "Pos Value", "Conf"
        ]

        table_rows = []
        for r in rows:
            table_rows.append([
                r.get("symbol", ""),
                r.get("ltp", "-"),
                r.get("entry", "-"),
                r.get("sl", "-"),
                r.get("target", "-"),
                r.get("decision", ""),
                Paragraph(str(r.get("reason", "")), pdf.normal),
                r.get("qty", "-"),
                r.get("position_value", "-"),
                r.get("confidence") or "-"
            ])

        pdf.add_table(
            headers=headers,
            rows=table_rows,
            col_widths=[65, 40, 40, 40, 45, 55, 170, 35, 55, 35]
        )

        return pdf.build()
