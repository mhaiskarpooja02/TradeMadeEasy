# db/TradeFriendOrderConfigRepo.py

import sqlite3
import os
from datetime import datetime

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_order_config.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendOrderConfigRepo:
    """
    PURPOSE:
    - Persist OMS runtime configuration
    - Single row only (id = 1)
    - Controls LIVE / PAPER routing & broker behavior
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()
        self._create_table()
        self._seed_if_needed()   # ✅ runs once only

    # ---------------------------------------------------
    # TABLE
    # ---------------------------------------------------
    def _create_table(self):
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS tradefriend_order_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),

                -- GLOBAL OMS FLAGS
                order_mode TEXT DEFAULT 'PAPER',   -- PAPER | LIVE
                allow_multi_broker INTEGER DEFAULT 1,

                -- DHAN
                dhan_enabled INTEGER DEFAULT 1,
                dhan_auto_order INTEGER DEFAULT 0,
                dhan_max_qty INTEGER,

                -- ANGEL
                angel_enabled INTEGER DEFAULT 1,
                angel_auto_order INTEGER DEFAULT 0,
                angel_max_qty INTEGER,

                updated_on TEXT
            )
        """)
        self.conn.commit()

    # ---------------------------------------------------
    # SEED (RUNS ONLY ONCE)
    # ---------------------------------------------------
    def _seed_if_needed(self):
        row = self.cur.execute(
            "SELECT 1 FROM tradefriend_order_config WHERE id = 1"
        ).fetchone()

        if row:
            return  # ✅ already seeded

        self.cur.execute("""
            INSERT INTO tradefriend_order_config (
                id,
                order_mode,
                allow_multi_broker,
                dhan_enabled,
                dhan_auto_order,
                angel_enabled,
                angel_auto_order,
                updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            1,
            "PAPER",
            1,
            1, 0,
            1, 0,
            datetime.now().isoformat()
        ))
        self.conn.commit()

    # ---------------------------------------------------
    # FETCH
    # ---------------------------------------------------
    def get(self) -> dict:
        row = self.cur.execute(
            "SELECT * FROM tradefriend_order_config WHERE id = 1"
        ).fetchone()
        return dict(row) if row else {}

    # ---------------------------------------------------
    # UPDATE
    # ---------------------------------------------------
    def update(self, **kwargs):
        if not kwargs:
            return

        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values())
        values.append(datetime.now().isoformat())

        sql = f"""
            UPDATE tradefriend_order_config
            SET {fields}, updated_on = ?
            WHERE id = 1
        """

        self.cur.execute(sql, values)
        self.conn.commit()

    # ---------------------------------------------------
    # CONVENIENCE FLAGS
    # ---------------------------------------------------
    def is_live(self) -> bool:
        return self.get().get("order_mode") == "LIVE"

    def is_dhan_auto(self) -> bool:
        cfg = self.get()
        return bool(cfg.get("dhan_enabled")) and bool(cfg.get("dhan_auto_order"))

    def is_angel_auto(self) -> bool:
        cfg = self.get()
        return bool(cfg.get("angel_enabled")) and bool(cfg.get("angel_auto_order"))

    def allow_multiple_brokers(self) -> bool:
        return bool(self.get().get("allow_multi_broker"))
