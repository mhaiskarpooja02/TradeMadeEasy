# db/TradeFriendOrderRepo.py

import sqlite3
import os
from datetime import datetime

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_orders.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendOrderRepo:

    # ======================================================
    # INIT
    # ======================================================
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()

        self._apply_pragmas()
        self._create_table()
        self._create_indexes()

    # ======================================================
    def _apply_pragmas(self):
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")

    # ======================================================
    # TABLE (CLEAN DESIGN)
    # ======================================================
    def _create_table(self):

        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS tradefriend_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                trade_id INTEGER NOT NULL,
                broker TEXT NOT NULL,

                broker_order_id TEXT NOT NULL,
                broker_unique_id TEXT,

                leg_type TEXT NOT NULL,
                order_mode TEXT NOT NULL,
                side TEXT NOT NULL,
                qty INTEGER NOT NULL,

                filled_qty INTEGER DEFAULT 0,
                avg_price REAL DEFAULT 0,
                status TEXT NOT NULL,

                rejection_reason TEXT,

                recon_retry_count INTEGER DEFAULT 0,
                recon_error TEXT,
                last_reconciled_at TEXT,

                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)

        self.conn.commit()
    # ======================================================
    # INDEXES
    # ======================================================
    def _create_indexes(self):

        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_trade
            ON tradefriend_orders (trade_id)
        """)

        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_status
            ON tradefriend_orders (status)
        """)

        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_broker
            ON tradefriend_orders (broker)
        """)

        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_broker_unique
            ON tradefriend_orders (broker_unique_id)
        """)

        self.conn.commit()

    # ======================================================
    # INSERT ORDER (SAFE VERSION)
    # ======================================================
    def insert_order(
        self,
        trade_id: int,
        broker: str,
        broker_order_id: str,
        broker_unique_id: str | None,
        leg_type: str,
        order_mode: str,
        side: str,
        qty: int
    ) -> int:
    
        now = datetime.utcnow().isoformat()
    
        with self.conn:  # transaction-safe
        
            # 1️⃣ Check if already exists
            existing_id = self.fetch_by_broker_order_id(broker_order_id)
    
            if existing_id:
                return existing_id
    
            # 2️⃣ Insert new record
            self.cur.execute("""
                INSERT INTO tradefriend_orders (
                    trade_id,
                    broker,
                    broker_order_id,
                    broker_unique_id,
                    leg_type,
                    order_mode,
                    side,
                    qty,
                    status,
                    created_on,
                    updated_on
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                broker,
                broker_order_id,
                broker_unique_id,
                leg_type,
                order_mode,
                side,
                qty,
                "PLACED",
                now,
                now
            ))
    
            return self.cur.lastrowid
    # ======================================================
    # FETCH OPEN ORDERS
    # ======================================================
    def fetch_open_orders(self):

        rows = self.cur.execute("""
            SELECT *
            FROM tradefriend_orders
            WHERE status IN ('PLACED', 'PARTIAL')
              AND recon_retry_count < 5
        """).fetchall()

        return [dict(r) for r in rows]

    # ======================================================
    # UPDATE FILL DETAILS
    # ======================================================
    def update_fill_details(
        self,
        order_id: int,
        filled_qty: int,
        avg_price: float,
        status: str
    ):

        now = datetime.utcnow().isoformat()

        self.cur.execute("""
            UPDATE tradefriend_orders
            SET filled_qty = ?,
                avg_price = ?,
                status = ?,
                recon_retry_count = 0,
                recon_error = NULL,
                last_reconciled_at = ?,
                updated_on = ?
            WHERE id = ?
        """, (
            filled_qty,
            avg_price,
            status,
            now,
            now,
            order_id
        ))

        self.conn.commit()

    # ======================================================
    # MARK REJECTED
    # ======================================================
    def mark_rejected(self, order_id: int, reason: str):

        now = datetime.utcnow().isoformat()

        self.cur.execute("""
            UPDATE tradefriend_orders
            SET status = 'REJECTED',
                rejection_reason = ?,
                last_reconciled_at = ?,
                updated_on = ?
            WHERE id = ?
        """, (
            reason,
            now,
            now,
            order_id
        ))

        self.conn.commit()

    # ======================================================
    # MARK RECON ERROR
    # ======================================================
    def mark_recon_error(self, order_id: int, error: str):

        now = datetime.utcnow().isoformat()

        self.cur.execute("""
            UPDATE tradefriend_orders
            SET recon_retry_count = recon_retry_count + 1,
                recon_error = ?,
                last_reconciled_at = ?,
                updated_on = ?
            WHERE id = ?
        """, (
            error,
            now,
            now,
            order_id
        ))

        self.conn.commit()

    # ======================================================
    # TOUCH RECONCILED
    # ======================================================
    def touch_reconciled(self, order_id: int):

        now = datetime.utcnow().isoformat()

        self.cur.execute("""
            UPDATE tradefriend_orders
            SET last_reconciled_at = ?,
                updated_on = ?
            WHERE id = ?
        """, (
            now,
            now,
            order_id
        ))

        self.conn.commit()

    # ======================================================
    # UPDATE STATUS ONLY
    # ======================================================
    def update_status(self, order_id: int, status: str):

        now = datetime.utcnow().isoformat()

        self.cur.execute("""
            UPDATE tradefriend_orders
            SET status = ?,
                updated_on = ?
            WHERE id = ?
        """, (
            status,
            now,
            order_id
        ))

        self.conn.commit()

    # ======================================================
    # FETCH BY BROKER ORDER ID
    # ======================================================
    def fetch_by_broker_order_id(self, broker_order_id: str):

        row = self.cur.execute("""
            SELECT id
            FROM tradefriend_orders
            WHERE broker_order_id = ?
            LIMIT 1
        """, (broker_order_id,)).fetchone()

        return row["id"] if row else None

    # ======================================================
    # CLOSE
    # ======================================================
    def close(self):
        self.conn.close()