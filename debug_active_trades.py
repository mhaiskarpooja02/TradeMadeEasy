# debug_active_trades.py

import os
import sqlite3
from db.TradeFriendSwingPlanRepo import TradeFriendSwingPlanRepo
from utils.logger import get_logger

logger = get_logger(__name__)


def print_tradefriend_trades():
    trade_repo = TradeFriendSwingPlanRepo()

    rows = trade_repo.cursor.execute("""SELECT DISTINCT symbol
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
                                      """).fetchall()

# ,'EGSHP-EQ')
    print("\n================ ACTIVE TRADES DEBUG ================\n")
    print(f"Total active trades found: {len(rows)}\n")

    if not rows:
        print("❌ No trades with status OPEN / PARTIAL found")
        return

    for i, trade in enumerate(rows, start=1):
        trade_dict = dict(trade)

        print(f"--- Trade #{i} ---")
        for k, v in trade_dict.items():
            print(f"{k:20}: {v}")
        print("-" * 50)

    print("\n================ END =================\n")

def print_active_trades():
    trade_repo = TradeFriendSwingPlanRepo()


    rows = trade_repo.cursor.execute("""
      SELECT symbol,  COUNT(*) AS cnt
FROM swing_trade_plans
GROUP BY symbol, d;

    """).fetchall()

# ,'EGSHP-EQ')
    print("\n================ ACTIVE TRADES DEBUG ================\n")
    print(f"Total active trades found: {len(rows)}\n")

    if not rows:
        print("❌ No trades with status OPEN / PARTIAL found")
        return

    for i, trade in enumerate(rows, start=1):
        trade_dict = dict(trade)

        print(f"--- Trade #{i} ---")
        for k, v in trade_dict.items():
            print(f"{k:20}: {v}")
        print("-" * 50)

    print("\n================ END =================\n")

def print_tradefindinstrument_count():
        DB_FOLDER = "db"
        DB_FILE = os.path.join(DB_FOLDER, "tradefindinstrument.db")
    
        if not os.path.exists(DB_FILE):
            print(f"❌ DB not found: {DB_FILE}")
            return
    
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
    
        # Total records
        total = cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM tradefindinstrument
        """).fetchone()["cnt"]
    
        print("\n================ TRADEFINDINSTRUMENT DEBUG ================\n")
        print(f"📦 Total records in tradefindinstrument: {total}\n")
    
        # OPTIONAL: status-wise count (safe even if column missing)
        try:
            rows = cursor.execute("""
                SELECT status, COUNT(*) AS cnt
                FROM tradefindinstrument
                GROUP BY status
            """).fetchall()
    
            print("Status-wise breakup:\n")
            for r in rows:
                print(f"{r['status']:15}: {r['cnt']}")
        except Exception:
            print("ℹ️ No status column found — skipped status breakdown")
    
        conn.close()
        print("\n================ END =================\n")


if __name__ == "__main__":
    # print_active_trades()
    # print_tradefriend_trades()

    print_tradefindinstrument_count()
