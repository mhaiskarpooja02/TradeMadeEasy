# db/TradeFriendRealizedPnLRepo.py

import sqlite3
import os
from datetime import datetime
from typing import Optional

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_realized_pnl.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendRealizedPnLRepo:
    """
    PURPOSE:
    - Append-only ledger for realized PnL
    - One record per EXIT execution (partial / final)
    - Reporting, audit & tax friendly
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()

        self._apply_pragmas()
        self._create_table()
        self._create_indexes()

    # --------------------------------------------------
    # SQLITE PRAGMAS (PERFORMANCE)
    # --------------------------------------------------
    def _apply_pragmas(self):
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA temp_store=MEMORY;")
        self.conn.execute("PRAGMA foreign_keys=ON;")

    # --------------------------------------------------
    # TABLE
    # --------------------------------------------------
    def _create_table(self):
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS tradefriend_realized_pnl (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                trade_id INTEGER NOT NULL,
                broker_trade_id INTEGER,

                symbol TEXT NOT NULL,
                side TEXT NOT NULL,                -- BUY / SELL (original side)
                mode TEXT NOT NULL,        
                exit_reason TEXT NOT NULL,

                qty INTEGER NOT NULL,

                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,

                pnl_amount REAL NOT NULL,

                exit_time TEXT NOT NULL,
                exit_date TEXT NOT NULL,           -- YYYY-MM-DD
                exit_week TEXT NOT NULL,           -- YYYY-WW
                exit_month TEXT NOT NULL           -- YYYY-MM
            )
        """)
        self.conn.commit()

    # --------------------------------------------------
    # INDEXES (REPORT PERFORMANCE)
    # --------------------------------------------------
    def _create_indexes(self):
        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pnl_exit_month
            ON tradefriend_realized_pnl (exit_month)
        """)
        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pnl_exit_week
            ON tradefriend_realized_pnl (exit_week)
        """)
        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pnl_symbol_time
            ON tradefriend_realized_pnl (symbol, exit_time DESC)
        """)
        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pnl_symbol_month
            ON tradefriend_realized_pnl (symbol, exit_month)
        """)
        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pnl_trade_id
            ON tradefriend_realized_pnl (trade_id)
        """)
        self.conn.commit()

    # --------------------------------------------------
    # INSERT REALIZED PNL (CORE METHOD)
    # --------------------------------------------------
    def insert_realized_pnl(
        self,
        trade_id: int,
        symbol: str,
        side: str,
         mode: str,  
        qty: int,
        entry_price: float,
        exit_price: float,
        exit_reason: str,
        broker_trade_id: Optional[int] = None,
        exit_time: Optional[datetime] = None
    ):
        """
        NOTE:
        - This is called ONLY by Exit OMS
        - Entry OMS NEVER touches this
        """

        exit_time = exit_time or datetime.now()

        # BUY → profit if exit > entry
        # SELL → profit if exit < entry
        if side == "BUY":
            pnl_amount = round((exit_price - entry_price) * qty, 2)
        else:
            pnl_amount = round((entry_price - exit_price) * qty, 2)

        self.cur.execute("""
            INSERT INTO tradefriend_realized_pnl (
                trade_id,
                broker_trade_id,
                symbol,
                side,
                exit_reason,
                mode,       
                qty,
                entry_price,
                exit_price,
                pnl_amount,
                exit_time,
                exit_date,
                exit_week,
                exit_month
            ) VALUES (?, ?, ?, ?,   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_id,
            broker_trade_id,
            symbol,
            side,
            mode,
            exit_reason,
            qty,
            entry_price,
            exit_price,
            pnl_amount,
            exit_time.isoformat(),
            exit_time.strftime("%Y-%m-%d"),
            exit_time.strftime("%Y-%W"),
            exit_time.strftime("%Y-%m")
        ))

        self.conn.commit()

    # --------------------------------------------------
    # REPORT QUERIES (READ ONLY)
    # --------------------------------------------------
    def fetch_symbol_history(self, symbol: str):
        rows = self.cur.execute("""
            SELECT *
            FROM tradefriend_realized_pnl
            WHERE symbol = ?
            ORDER BY exit_time DESC
        """, (symbol,)).fetchall()

        return [dict(r) for r in rows]

    def fetch_month_summary(self, month: str):
        rows = self.cur.execute("""
            SELECT
                symbol,
                COUNT(*) AS exit_count,
                SUM(qty) AS total_qty,
                ROUND(SUM(pnl_amount), 2) AS total_pnl
            FROM tradefriend_realized_pnl
            WHERE exit_month = ?
            GROUP BY symbol
            ORDER BY total_pnl DESC
        """, (month,)).fetchall()

        return [dict(r) for r in rows]

    def fetch_week_summary(self, week: str):
        rows = self.cur.execute("""
            SELECT
                symbol,
                COUNT(*) AS exit_count,
                ROUND(SUM(pnl_amount), 2) AS total_pnl
            FROM tradefriend_realized_pnl
            WHERE exit_week = ?
            GROUP BY symbol
        """, (week,)).fetchall()

        return [dict(r) for r in rows]
