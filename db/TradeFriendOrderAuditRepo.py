# db/TradeFriendOrderAuditRepo.py

import sqlite3
import os
import json
from datetime import datetime

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_order_audit.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendOrderAuditRepo:
    """
    PURPOSE:
    - Persist OMS order attempts & results
    - Full traceability for PAPER / LIVE
    - Broker-agnostic audit layer
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()
        self._create_table()
        self._create_indexes()

    # --------------------------------------------------
    # TABLE
    # --------------------------------------------------
    def _create_table(self):
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS tradefriend_order_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                trade_id INTEGER,
                symbol TEXT NOT NULL,

                broker TEXT NOT NULL,          -- OMS / DHAN / ANGEL
                order_mode TEXT NOT NULL,      -- PAPER / LIVE

                side TEXT NOT NULL,            -- BUY / SELL
                qty INTEGER NOT NULL,

                resolved_id TEXT,              -- token / security_id
                exchange TEXT,
                product TEXT,
                order_type TEXT,

                request_payload TEXT,
                response_payload TEXT,

                status TEXT NOT NULL,          -- ATTEMPTED / SUCCESS / FAILED / SKIPPED
                error_message TEXT,

                created_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    # --------------------------------------------------
    # INDEXES (IMPORTANT FOR DEBUGGING)
    # --------------------------------------------------
    def _create_indexes(self):
        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_trade
            ON tradefriend_order_audit(trade_id)
        """)

        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_symbol
            ON tradefriend_order_audit(symbol)
        """)

        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_status
            ON tradefriend_order_audit(status)
        """)

        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_created
            ON tradefriend_order_audit(created_on)
        """)
        self.conn.commit()

    # --------------------------------------------------
    # INSERT: ATTEMPT
    # --------------------------------------------------
    def log_attempt(
        self,
        trade_id: int,
        symbol: str,
        broker: str,
        order_mode: str,
        side: str,
        qty: int,
        exchange: str = None,
        product: str = None,
        order_type: str = None,
        resolved_id: str = None,
        request_payload: dict = None
    ) -> int:
        """
        Insert initial audit record.
        Returns audit_id.
        """

        self.cur.execute("""
            INSERT INTO tradefriend_order_audit (
                trade_id,
                symbol,
                broker,
                order_mode,
                side,
                qty,
                resolved_id,
                exchange,
                product,
                order_type,
                request_payload,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_id,
            symbol,
            broker,
            order_mode,
            side,
            qty,
            resolved_id,
            exchange,
            product,
            order_type,
            json.dumps(request_payload) if request_payload else None,
            "ATTEMPTED"
        ))

        self.conn.commit()
        return self.cur.lastrowid

    # --------------------------------------------------
    # UPDATE: RESULT
    # --------------------------------------------------
    def log_result(
        self,
        audit_id: int,
        status: str,
        response_payload: dict = None,
        error_message: str = None
    ):
        """
        Update audit with final result.
        """

        self.cur.execute("""
            UPDATE tradefriend_order_audit
            SET
                status = ?,
                response_payload = ?,
                error_message = ?
            WHERE id = ?
        """, (
            status,
            json.dumps(response_payload) if response_payload else None,
            error_message,
            audit_id
        ))

        self.conn.commit()

    # --------------------------------------------------
    # READERS (DEBUG / UI)
    # --------------------------------------------------
    def get_by_trade(self, trade_id: int):
        self.cur.execute("""
            SELECT *
            FROM tradefriend_order_audit
            WHERE trade_id = ?
            ORDER BY created_on
        """, (trade_id,))
        return self.cur.fetchall()

    def get_recent(self, limit: int = 50):
        self.cur.execute("""
            SELECT *
            FROM tradefriend_order_audit
            ORDER BY created_on DESC
            LIMIT ?
        """, (limit,))
        return self.cur.fetchall()
