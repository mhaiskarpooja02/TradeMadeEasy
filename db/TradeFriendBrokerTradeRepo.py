# db/TradeFriendBrokerTradeRepo.py

import sqlite3
import os
import json
from datetime import datetime

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_broker_trades.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendBrokerTradeRepo:
    """
    PURPOSE:
    - Persist broker-wise ENTRY & EXIT executions
    - Maintain broker position lifecycle
    - Source of truth for Exit OMS & Reporting
    """

    # =====================================================
    # INIT
    # =====================================================
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()

        self._create_table()
        self._run_migrations()
        self._create_indexes()

    # =====================================================
    # TABLE
    # =====================================================
    def _create_table(self):
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS tradefriend_broker_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                trade_id INTEGER NOT NULL,

                broker TEXT NOT NULL,
                order_mode TEXT NOT NULL,

                symbol TEXT NOT NULL,
                leg_type TEXT NOT NULL,           -- ENTRY / EXIT
                side TEXT NOT NULL,               -- BUY / SELL
                qty INTEGER NOT NULL,

                exchange TEXT,
                product TEXT,
                order_type TEXT,

                resolved_id TEXT,
                broker_order_id TEXT,

                parent_trade_id INTEGER,          -- EXIT → ENTRY broker_trade_id

                status TEXT NOT NULL,              -- CREATED / SUCCESS / FAILED
                position_status TEXT NOT NULL,     -- OPEN / PARTIAL_EXIT / CLOSED

                error_message TEXT,
                request_payload TEXT,
                response_payload TEXT,

                created_on TEXT,
                updated_on TEXT
            )
        """)
        self.conn.commit()

    # =====================================================
    # MIGRATIONS (SAFE FOR OLD DBS)
    # =====================================================
    def _run_migrations(self):
        existing_cols = {
            col["name"]
            for col in self.cur.execute(
                "PRAGMA table_info(tradefriend_broker_trades)"
            ).fetchall()
        }

        migrations = {
            "leg_type": "TEXT NOT NULL DEFAULT 'ENTRY'",
            "position_status": "TEXT NOT NULL DEFAULT 'OPEN'",
            "parent_trade_id": "INTEGER",
            "exchange": "TEXT",
            "product": "TEXT",
            "order_type": "TEXT",
            "resolved_id": "TEXT",
            "error_message": "TEXT",
            "request_payload": "TEXT",
            "response_payload": "TEXT",
        }

        for col, definition in migrations.items():
            if col not in existing_cols:
                self.cur.execute(
                    f"ALTER TABLE tradefriend_broker_trades "
                    f"ADD COLUMN {col} {definition}"
                )

        self.conn.commit()

    # =====================================================
    # INDEXES
    # =====================================================
    def _create_indexes(self):
        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_bt_trade_leg_status
            ON tradefriend_broker_trades(trade_id, leg_type, position_status)
        """)

        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_bt_symbol_leg_status
            ON tradefriend_broker_trades(symbol, leg_type, position_status)
        """)

        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_bt_broker_order
            ON tradefriend_broker_trades(broker, broker_order_id)
        """)

        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_bt_created_on
            ON tradefriend_broker_trades(created_on)
        """)

        self.conn.commit()

    # =====================================================
    # INSERT (ENTRY / EXIT)
    # =====================================================
    def insert_broker_trade(
        self,
        trade_id: int,
        broker: str,
        order_mode: str,
        symbol: str,
        leg_type: str,             # ENTRY / EXIT
        side: str,
        qty: int,
        exchange: str = None,
        product: str = None,
        order_type: str = None,
        resolved_id: str = None,
        parent_trade_id: int = None,
        request_payload: dict = None
    ) -> int:

        position_status = "OPEN" if leg_type == "ENTRY" else "CLOSED"

        self.cur.execute("""
            INSERT INTO tradefriend_broker_trades (
                trade_id, broker, order_mode, symbol,
                leg_type, side, qty,
                exchange, product, order_type,
                resolved_id, parent_trade_id,
                status, position_status,
                request_payload, created_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CREATED', ?, ?, ?)
        """, (
            trade_id, broker, order_mode, symbol,
            leg_type, side, qty,
            exchange, product, order_type,
            resolved_id, parent_trade_id,
            position_status,
            json.dumps(request_payload) if request_payload else None,
            datetime.now().isoformat()
        ))

        self.conn.commit()
        return self.cur.lastrowid

    # =====================================================
    # STATUS UPDATES
    # =====================================================
    def mark_order_success(
        self,
        broker_trade_id: int,
        broker_order_id: str,
        response_payload: dict = None
    ):
        self.cur.execute("""
            UPDATE tradefriend_broker_trades
            SET status='SUCCESS',
                broker_order_id=?,
                response_payload=?,
                updated_on=?
            WHERE id=?
        """, (
            broker_order_id,
            json.dumps(response_payload) if response_payload else None,
            datetime.now().isoformat(),
            broker_trade_id
        ))
        self.conn.commit()

    def mark_order_failed(self, broker_trade_id: int, error_message: str):
        self.cur.execute("""
            UPDATE tradefriend_broker_trades
            SET status='FAILED',
                error_message=?,
                updated_on=?
            WHERE id=?
        """, (
            error_message,
            datetime.now().isoformat(),
            broker_trade_id
        ))
        self.conn.commit()

    # =====================================================
    # POSITION LIFECYCLE (ENTRY ONLY)
    # =====================================================
    def mark_position_partial_exit(self, broker_trade_id: int):
        self.cur.execute("""
            UPDATE tradefriend_broker_trades
            SET position_status='PARTIAL_EXIT',
                updated_on=?
            WHERE id=?
        """, (datetime.now().isoformat(), broker_trade_id))
        self.conn.commit()

    def mark_position_closed(self, broker_trade_id: int):
        self.cur.execute("""
            UPDATE tradefriend_broker_trades
            SET position_status='CLOSED',
                updated_on=?
            WHERE id=?
        """, (datetime.now().isoformat(), broker_trade_id))
        self.conn.commit()

    # =====================================================
    # FETCHES (EXIT OMS / REPORTING)
    # =====================================================
    def fetch_active_positions(self, trade_id: int):
        rows = self.cur.execute("""
            SELECT *
            FROM tradefriend_broker_trades
            WHERE trade_id=?
              AND leg_type='ENTRY'
              AND status='SUCCESS'
              AND position_status IN ('OPEN', 'PARTIAL_EXIT')
            ORDER BY id
        """, (trade_id,)).fetchall()

        return [dict(r) for r in rows]

    def fetch_by_symbol(self, symbol: str):
        rows = self.cur.execute("""
            SELECT *
            FROM tradefriend_broker_trades
            WHERE symbol=?
            ORDER BY created_on DESC
        """, (symbol,)).fetchall()

        return [dict(r) for r in rows]

    def has_active_position(self, trade_id: int, symbol: str) -> bool:
        row = self.cur.execute("""
            SELECT 1
            FROM tradefriend_broker_trades
            WHERE trade_id = ?
              AND symbol = ?
              AND leg_type = 'ENTRY'
              AND status = 'SUCCESS'
              AND position_status IN ('OPEN', 'PARTIAL_EXIT')
            LIMIT 1
        """, (trade_id, symbol)).fetchone()

        return row is not None
    
    def fetch_active_entry_by_symbol(self, symbol: str):
        rows = self.cur.execute("""
            SELECT *
            FROM tradefriend_broker_trades
            WHERE symbol = ?
              AND leg_type = 'ENTRY'
              AND status = 'SUCCESS'
              AND position_status IN ('OPEN', 'PARTIAL_EXIT')
            ORDER BY id
        """, (symbol,)).fetchall()
    
        return [dict(r) for r in rows]