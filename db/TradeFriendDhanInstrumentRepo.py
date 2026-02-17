import sqlite3
import os
from datetime import datetime

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_dhan_instrument.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendDhanInstrumentRepo:
    """
    PURPOSE:
    - Persist Dhan NSE EQ instruments
    - Source of truth for security_id resolution
    - Used by OMS + Adapters
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
            CREATE TABLE IF NOT EXISTS tradefriend_dhan_instrument (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                symbol TEXT UNIQUE NOT NULL,        -- SBIN-EQ
                trading_symbol TEXT NOT NULL,       -- SBIN
                security_id TEXT UNIQUE NOT NULL,   -- Dhan security id

                exchange TEXT DEFAULT 'NSE',
                segment TEXT DEFAULT 'EQ',

                is_active INTEGER DEFAULT 1,

                source_hash TEXT UNIQUE,
                added_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_on TIMESTAMP
            )
        """)
        self.conn.commit()

    # --------------------------------------------------
    # INDEXES
    # --------------------------------------------------
    def _create_indexes(self):
        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_dhan_symbol
            ON tradefriend_dhan_instrument(symbol)
        """)
        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_dhan_security
            ON tradefriend_dhan_instrument(security_id)
        """)
        self.cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_dhan_active
            ON tradefriend_dhan_instrument(is_active)
        """)
        self.conn.commit()

    # --------------------------------------------------
    # UPSERT (CSV SYNC)
    # --------------------------------------------------
    def upsert(self, symbol, trading_symbol, security_id, source_hash):
        self.cur.execute("""
            INSERT INTO tradefriend_dhan_instrument (
                symbol, trading_symbol, security_id, source_hash
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol)
            DO UPDATE SET
                trading_symbol = excluded.trading_symbol,
                security_id = excluded.security_id,
                source_hash = excluded.source_hash,
                is_active = 1,
                updated_on = ?
        """, (
            symbol,
            trading_symbol,
            security_id,
            source_hash,
            datetime.now().isoformat()
        ))
        self.conn.commit()

    # --------------------------------------------------
    # READ: RESOLVE SYMBOL → SECURITY ID
    # --------------------------------------------------
    def resolve_security_id(self, symbol: str) -> str | None:
        row = self.cur.execute("""
            SELECT security_id
            FROM tradefriend_dhan_instrument
            WHERE symbol = ?
              AND is_active = 1
            LIMIT 1
        """, (symbol,)).fetchone()

        return row["security_id"] if row else None

    # --------------------------------------------------
    # READ: FULL ACTIVE RECORD
    # --------------------------------------------------
    def get_active(self, symbol: str) -> dict | None:
        row = self.cur.execute("""
            SELECT *
            FROM tradefriend_dhan_instrument
            WHERE symbol = ?
              AND is_active = 1
            LIMIT 1
        """, (symbol,)).fetchone()

        return dict(row) if row else None

    # --------------------------------------------------
    # READ: ALL ACTIVE (MONITORING / UI)
    # --------------------------------------------------
    def get_all_active(self):
        return self.cur.execute("""
            SELECT symbol, trading_symbol, security_id
            FROM tradefriend_dhan_instrument
            WHERE is_active = 1
            ORDER BY symbol
        """).fetchall()

    # --------------------------------------------------
    # SOFT DELETE (CSV CLEANUP)
    # --------------------------------------------------
    def deactivate(self, symbol: str):
        self.cur.execute("""
            UPDATE tradefriend_dhan_instrument
            SET is_active = 0,
                updated_on = ?
            WHERE symbol = ?
        """, (datetime.now().isoformat(), symbol))
        self.conn.commit()

    # --------------------------------------------------
    # HASH CHECK (CHANGE DETECTION)
    # --------------------------------------------------
    def exists_by_hash(self, source_hash: str) -> bool:
        row = self.cur.execute(
            "SELECT 1 FROM tradefriend_dhan_instrument WHERE source_hash = ?",
            (source_hash,)
        ).fetchone()
        return row is not None

    # --------------------------------------------------
    # STATS / HEALTH
    # --------------------------------------------------
    def count_active(self) -> int:
        row = self.cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM tradefriend_dhan_instrument
            WHERE is_active = 1
        """).fetchone()
        return row["cnt"]
