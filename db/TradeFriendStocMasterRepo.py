# db/TradeFriendStocMasterRepo.py

import os
import sqlite3
from datetime import datetime


# --------------------------------------------------
# DB CONFIG
# --------------------------------------------------
DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_stocmaster.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendStocMasterRepo:

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._ensure_table()
        self._ensure_indexes()

    # --------------------------------------------------
    # CONTEXT MANAGER
    # --------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    # --------------------------------------------------
    # TABLE
    # --------------------------------------------------
    def _ensure_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tradefriend_stocmaster (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                symbol_name TEXT NOT NULL,
                token TEXT NOT NULL,
                symbolnameltp TEXT,
                is_active INTEGER DEFAULT 1,
                last_ltp_check TIMESTAMP,
                created_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_on TIMESTAMP,
                deactivated_on TIMESTAMP
            )
        """)
        self.conn.commit()

    # --------------------------------------------------
    # INDEXES
    # --------------------------------------------------
    def _ensure_indexes(self):
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tfsm_symbol
            ON tradefriend_stocmaster(symbol)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tfsm_active
            ON tradefriend_stocmaster(is_active)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tfsm_symbolnameltp
            ON tradefriend_stocmaster(symbolnameltp)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tfsm_last_ltp
            ON tradefriend_stocmaster(last_ltp_check)
        """)
        self.conn.commit()

    # --------------------------------------------------
    # UPSERT FROM CSV
    # --------------------------------------------------
    def upsert_from_csv(self, row: dict):
        now = datetime.now().isoformat()

        self.cursor.execute("""
            INSERT INTO tradefriend_stocmaster (
                symbol,
                symbol_name,
                token,
                symbolnameltp,
                is_active,
                last_ltp_check,
                updated_on,
                deactivated_on
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(symbol)
            DO UPDATE SET
                symbol_name = excluded.symbol_name,
                token = excluded.token,
                symbolnameltp = excluded.symbolnameltp,
                is_active = excluded.is_active,
                last_ltp_check = excluded.last_ltp_check,
                updated_on = excluded.updated_on,
                deactivated_on = CASE
                    WHEN excluded.is_active = 0 THEN CURRENT_TIMESTAMP
                    ELSE NULL
                END
        """, (
            row["symbol"],
            row["symbolName"],
            row["token"],
            row.get("symbolnameltp"),
            int(row.get("active", 0)),
            row.get("last_ltp_check"),
            now
        ))

        self.conn.commit()

    # --------------------------------------------------
    # READERS (SCANNER USE)
    # --------------------------------------------------
    def get_active_symbols(self):
        self.cursor.execute("""
            SELECT
                symbol,
                symbolnameltp AS trading_symbol,
                token
            FROM tradefriend_stocmaster
            WHERE is_active = 1
        """)
        return self.cursor.fetchall()

    def get_stats(self):
        self.cursor.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(is_active = 1) AS active,
                SUM(is_active = 0) AS inactive
            FROM tradefriend_stocmaster
        """)
        return dict(self.cursor.fetchone())
    
    def get_active_symbol(self, symbol: str):
        self.cursor.execute("""
            SELECT symbolnameltp, token
            FROM tradefriend_stocmaster
            WHERE symbol = ?
            AND is_active = 1
        """, (symbol,))
        return self.cursor.fetchone()
