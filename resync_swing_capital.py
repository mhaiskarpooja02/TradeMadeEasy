"""
DEV / ADMIN SCRIPT
------------------
Resync available_swing_capital based on active trades.

Formula:
USED = SUM(position_value WHERE status IN ('OPEN','PARTIAL'))
AVAILABLE = max_swing_capital - USED

Run ONCE in development when capital KPI mismatches.
"""

import sqlite3
import os

# -----------------------------
# DB CONFIG
# -----------------------------
DB_FOLDER = "dbdata"
TRADES_DB = os.path.join(DB_FOLDER, "tradefriend_trades.db")
SETTINGS_DB = os.path.join(DB_FOLDER, "tradefriend_settings.db")

# -----------------------------
# CONNECT
# -----------------------------
trade_conn = sqlite3.connect(TRADES_DB)
trade_conn.row_factory = sqlite3.Row
trade_cur = trade_conn.cursor()

settings_conn = sqlite3.connect(SETTINGS_DB)
settings_conn.row_factory = sqlite3.Row
settings_cur = settings_conn.cursor()

# -----------------------------
# FETCH USED CAPITAL
# -----------------------------
trade_cur.execute("""
    SELECT COALESCE(SUM(entry * remaining_qty), 0) AS used_capital
    FROM tradefriend_trades
    WHERE status IN ('OPEN', 'PARTIAL')
""")
used_capital = float(trade_cur.fetchone()["used_capital"])

# -----------------------------
# FETCH SETTINGS
# -----------------------------
settings_cur.execute("""
    SELECT
        max_swing_capital,
        available_swing_capital
    FROM tradefriend_settings
    WHERE id = 1
""")
settings = settings_cur.fetchone()

if not settings or settings["max_swing_capital"] is None:
    raise RuntimeError("❌ max_swing_capital not set in settings")

max_capital = float(settings["max_swing_capital"])
old_available = float(settings["available_swing_capital"] or 0)

# -----------------------------
# CALCULATE NEW AVAILABLE
# -----------------------------
new_available = round(max_capital - used_capital, 2)
if new_available < 0:
    new_available = 0.0

# -----------------------------
# UPDATE SETTINGS
# -----------------------------
settings_cur.execute("""
    UPDATE tradefriend_settings
    SET
        available_swing_capital = ?,
        updated_on = CURRENT_TIMESTAMP
    WHERE id = 1
""", (new_available,))
settings_conn.commit()

# -----------------------------
# OUTPUT
# -----------------------------
print("\n🔄 SWING CAPITAL RESYNC COMPLETE\n")
print(f"Max Swing Capital     : {max_capital}")
print(f"Used Capital (Active) : {used_capital}")
print(f"Old Available Capital : {old_available}")
print(f"New Available Capital : {new_available}")

# -----------------------------
# CONSISTENCY CHECK
# -----------------------------
diff = abs((used_capital + new_available) - max_capital)

print("\n🔍 CONSISTENCY CHECK")
print(f"Used + Available - Max = {diff}")

if diff < 1:
    print("✅ CAPITAL STATE CONSISTENT")
else:
    print("❌ CAPITAL MISMATCH — FULL RESET MAY BE REQUIRED")

# -----------------------------
# CLOSE
# -----------------------------
trade_conn.close()
settings_conn.close()
