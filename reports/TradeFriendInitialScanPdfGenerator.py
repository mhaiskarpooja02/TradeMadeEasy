from reports.base.TradeFriendPdfBase import TradeFriendPdfBase


class TradeFriendInitialScanPdfGenerator:

    def build(
        self,
        *,
        scan_date: str,
        rows: list,
        score_cutoff: int,
        output_path: str
    ) -> str:

        pdf = TradeFriendPdfBase(output_path)

        pdf.add_title(f"TradeFriend Daily Scan Report — {scan_date}")

        pdf.add_meta(
            f"<b>Score Cutoff:</b> {score_cutoff} &nbsp;&nbsp; "
            f"<b>Total Scanned:</b> {len(rows or [])}"
        )

        pdf.add_timestamp()

        headers = [
            "Symbol", "Strategy", "Bias",
            "Entry", "SL", "Target", "Confidence"
        ]

        table_rows = []

        for r in rows or []:
            try:
                confidence = int(float(r.get("confidence", 0)))
            except (TypeError, ValueError):
                confidence = 0

            if confidence < score_cutoff:
                continue

            table_rows.append([
                r.get("symbol", "-"),
                r.get("strategy", "-"),
                r.get("bias", "-"),
                r.get("entry", "-"),
                r.get("sl", "-"),
                r.get("target", "-"),
                confidence
            ])

        if not table_rows:
            pdf.add_meta(
                f"No stocks met the score cutoff ({score_cutoff})."
            )
        else:
            pdf.add_table(
                headers=headers,
                rows=table_rows,
                col_widths = [85, 160, 55, 50, 45, 55, 40]
            )

        return pdf.build()
