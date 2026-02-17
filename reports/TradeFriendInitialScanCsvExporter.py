# reports/TradeFriendInitialScanCsvExporter.py

import csv
import os

class TradeFriendInitialScanCsvExporter:

    def export(self, rows: list, output_path: str):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if not rows:
            headers = [
                "symbol", "strategy", "bias", "score",
                "entry", "sl", "target", "scan_date"
            ]
            with open(output_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
            return

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
