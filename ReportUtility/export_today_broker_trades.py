# utils/export_today_broker_trades.py

import os
import csv
from datetime import datetime

from db.TradeFriendBrokerTradeRepo import TradeFriendBrokerTradeRepo
from db.TradeFriendOrderAuditRepo import TradeFriendOrderAuditRepo
from db.TradeFriendRealizedPnLRepo import TradeFriendRealizedPnLRepo




# -------------------------------------------------------
# CONFIG
# -------------------------------------------------------
EXPORT_FOLDER = "reports/broker_trades"
os.makedirs(EXPORT_FOLDER, exist_ok=True)


# -------------------------------------------------------
# EXPORT BROKER TRADES
# -------------------------------------------------------
def export_today_broker_trades():
    """
    Fetch today's broker trades and export to CSV.
    """

    repo = TradeFriendBrokerTradeRepo()

    today_str = datetime.now().date().isoformat()
    start_time = f"{today_str}T00:00:00"
    end_time = f"{today_str}T23:59:59"

    rows = repo.fetch_trades(
        from_date=start_time,
        to_date=end_time,
        limit=None
    )

    if not rows:
        print("No broker trades found for today.")
        return

    filename = f"broker_trades_{today_str}.csv"
    filepath = os.path.join(EXPORT_FOLDER, filename)

    with open(filepath, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} broker rows to: {filepath}")


# -------------------------------------------------------
# EXPORT REALIZED PNL
# -------------------------------------------------------
def export_today_pnl():
    """
    Fetch today's realized PnL and export to CSV.
    """

    pnl_repo = TradeFriendRealizedPnLRepo()

    today_str = datetime.now().strftime("%Y-%m-%d")

    rows = pnl_repo.fetch_pnl(
        from_date=today_str,
        to_date=today_str,
        limit=None
    )

    if not rows:
        print("No realized PnL found for today.")
        return

    filename = f"pnl_{today_str}.csv"
    filepath = os.path.join(EXPORT_FOLDER, filename)

    with open(filepath, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} pnl rows to: {filepath}")

# -------------------------------------------------------
# EXPORT ORDER AUDIT
# -------------------------------------------------------
def export_today_order_audit():
    """
    Fetch today's order audit records and export to CSV.
    """

    audit_repo = TradeFriendOrderAuditRepo()

    today_str = datetime.now().date().isoformat()
    start_time = f"{today_str}T00:00:00"
    end_time = f"{today_str}T23:59:59"

    # You need to have this method in your repo
    rows = audit_repo.fetch_orders(
        from_date=start_time,
        to_date=end_time,
        limit=None
    )

    if not rows:
        print("No order audit records found for today.")
        return

    filename = f"order_audit_{today_str}.csv"
    filepath = os.path.join(EXPORT_FOLDER, filename)

    with open(filepath, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} order audit rows to: {filepath}")
# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
if __name__ == "__main__":
    export_today_broker_trades()
    export_today_pnl()
    export_today_order_audit()