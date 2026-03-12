import sqlite3
import os
import csv
from datetime import datetime

# --------------------------------------------------
# DB CONFIG
# --------------------------------------------------
DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_trades.db")
DBSwinggPlan_FILE = os.path.join(DB_FOLDER, "tradefriend_algo.db")

# --------------------------------------------------
# OUTPUT CONFIG
# --------------------------------------------------
REPORT_FOLDER = "reports/swing_plans"
os.makedirs(REPORT_FOLDER, exist_ok=True)

# --------------------------------------------------
# EXPORT LOGIC
# --------------------------------------------------
def export_tradefriend_trades_plans():
    if not os.path.exists(DB_FILE):
        raise FileNotFoundError(f"Database not found: {DB_FILE}")

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
              SELECT * 
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("⚠️ No records found")
        return

    # CSV PATH
    today = datetime.now().strftime("%Y-%m-%d")
    csv_path = os.path.join(
        REPORT_FOLDER,
        f"swing_trade_triendfriends_actual_46{today}_1.csv"
    )

    # Write CSV
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(rows[0].keys())

        # Data
        for row in rows:
            writer.writerow(list(row))

    print(f"✅ Exported {len(rows)} records → {csv_path}")

def export_swing_trade_plans():
    if not os.path.exists(DBSwinggPlan_FILE):
        raise FileNotFoundError(f"Database not found: {DBSwinggPlan_FILE}")

    conn = sqlite3.connect(DBSwinggPlan_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM swing_trade_plans
       
        
        ORDER BY created_on DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("⚠️ No records found")
        return

    # CSV PATH
    today = datetime.now().strftime("%Y-%m-%d")
    csv_path = os.path.join(
        REPORT_FOLDER,
        f"swing_TradeFriendtrade_actual_{today}.csv"
    )

    # Write CSV
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(rows[0].keys())

        # Data
        for row in rows:
            writer.writerow(list(row))

    print(f"✅ Exported {len(rows)} records → {csv_path}")

def export_active_trade_symbols_csv():
    """
    Export distinct symbols from tradefriend_trades
    where status is OPEN or PARTIAL into CSV
    """
    if not os.path.exists(DB_FILE):
        raise FileNotFoundError(f"Database not found: {DB_FILE}")

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT  *
        FROM tradefriend_trades
       
        ORDER BY symbol
    """).fetchall()
    #  # WHERE status IN ('OPEN', 'PARTIAL')
    conn.close()

    if not rows:
        print("⚠️ No active symbols found")
        return

    # CSV PATH
    today = datetime.now().strftime("%Y-%m-%d")
    csv_path = os.path.join(
        REPORT_FOLDER,
        f"active_trade_symbolsfulldata_{today}.csv"
    )

    # Write CSV
    # Write CSV
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(rows[0].keys())

        # Data
        for row in rows:
            writer.writerow(list(row))

    print(f"✅ Exported {len(rows)} active symbols → {csv_path}")

def cleanup_today_data():
    if not os.path.exists(DB_FILE):
        print("❌ Database not found:", DB_FILE)
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    print(f"🧹 Cleaning data for date: {today}")

    # -----------------------------
    # Delete today's watchlist
    # -----------------------------
    cursor.execute("""
        DELETE FROM tradefriend_trades
        WHERE date(created_on) = date('now');
    """)
    watchlist_deleted = cursor.rowcount

  

    conn.commit()
    conn.close()

    print("✅ Cleanup completed")
    print(f"   • Todays TradePlan rows deleted : {watchlist_deleted}")
   
# --------------------------------------------------
# MARK ALL NON-EXPIRED PLANS AS HOLD
# --------------------------------------------------
def mark_all_non_expired_swing_plans_hold() -> int:
    """
    Force ALL non-expired swing trade plans to HOLD.

    Rules:
    - Any status → HOLD
    - EXPIRED plans are untouched
    - Expiry respected via expiry_date
    - Returns number of rows updated
    """

    if not os.path.exists(DBSwinggPlan_FILE):
        raise FileNotFoundError(f"Database not found: {DBSwinggPlan_FILE}")

    conn = sqlite3.connect(DBSwinggPlan_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE swing_trade_plans
        SET status = 'HOLD'
        WHERE status != 'EXPIRED'
          AND (
                expiry_date IS NULL
                OR date(expiry_date) >= date('now')
          )
    """)

    updated = cursor.rowcount
    conn.commit()
    conn.close()

    print(f"⏸ {updated} swing plans forced to HOLD (non-expired)")
    return updated

# --------------------------------------------------
# MANUAL RUN
# --------------------------------------------------
if __name__ == "__main__":
#    export_active_trade_symbols_csv()
    # cleanup_today_data()
     # export_tradefriend_trades_plans()
    # export_active_trade_symbols_csv()
    # export_swing_trade_plans()
    # mark_all_non_expired_swing_plans_hold()
    export_active_trade_symbols_csv()
