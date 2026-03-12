# export_tradefriend_orders_csv.py

import os
import csv
from datetime import datetime
from db.TradeFriendOrderRepo import TradeFriendOrderRepo


REPORT_FOLDER = "reports"
os.makedirs(REPORT_FOLDER, exist_ok=True)


def export_open_orders_csv():
    repo = TradeFriendOrderRepo()

    # Using existing repo method
    orders = repo.fetch_open_orders()

    if not orders:
        print("❌ No open orders found to export")
        return

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(
        REPORT_FOLDER,
        f"open_orders_{timestamp}.csv"
    )

    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=orders[0].keys())
        writer.writeheader()
        writer.writerows(orders)

    repo.close()

    print(f"\n✅ Open Orders CSV exported successfully:")
    print(f"📁 {file_path}\n")


def export_all_orders_csv():
    repo = TradeFriendOrderRepo()

    # Using repo's internal cursor (still respecting repo connection)
    rows = repo.cur.execute("""
        SELECT *
        FROM tradefriend_orders
        ORDER BY created_on DESC
    """).fetchall()

    if not rows:
        print("❌ No orders found")
        return

    orders = [dict(r) for r in rows]

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(
        REPORT_FOLDER,
        f"all_orders_{timestamp}.csv"
    )

    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=orders[0].keys())
        writer.writeheader()
        writer.writerows(orders)

    repo.close()

    print(f"\n✅ All Orders CSV exported successfully:")
    print(f"📁 {file_path}\n")


if __name__ == "__main__":
    export_open_orders_csv()
    # export_all_orders_csv()