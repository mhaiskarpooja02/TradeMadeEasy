# db/TradeFriendSettingsRepo.py

import sqlite3
from datetime import datetime
import os

from utils.logger import get_logger

logger = get_logger(__name__)

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_settings.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendSettingsRepo:
    """
    PURPOSE:
    - Persist ALL trade settings in ONE table
    - Single row only (id = 1)
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()
        self._create_table()
        self._ensure_single_row()

    def _create_table(self):
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS tradefriend_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),

                -- TRADE MODE
                trade_mode TEXT DEFAULT 'PAPER',
                -- CAPITAL & RISK
                total_capital REAL,
                max_swing_capital REAL,
                available_swing_capital REAL,
                max_per_trade_capital REAL,
                max_open_trades INTEGER,

                -- PRICE RANGE → FIXED QTY
                qty_gt_100 INTEGER,
                qty_gt_200 INTEGER,
                qty_gt_500 INTEGER,
                qty_gt_700 INTEGER,
                qty_gt_1000 INTEGER,
                qty_gt_1500 INTEGER,
                qty_gt_2000 INTEGER,

                -- TARGET / SL MODE
                target_sl_mode TEXT,      -- TRADITIONAL / FIXED

                -- FIXED MODE ONLY
                fixed_target_percent REAL,
                fixed_sl_percent REAL,

                updated_on TEXT
            )
        """)
        self.conn.commit()

    def _ensure_single_row(self):
        self.cur.execute("SELECT COUNT(*) FROM tradefriend_settings")
        if self.cur.fetchone()[0] == 0:
            self.cur.execute("""
                INSERT INTO tradefriend_settings (id, target_sl_mode)
                VALUES (1, 'TRADITIONAL')
            """)
            self.conn.commit()

    def fetch(self):
        return self.cur.execute(
            "SELECT * FROM tradefriend_settings WHERE id = 1"
        ).fetchone()

    def update(self, data: dict):
        fields, values = [], []
        for k, v in data.items():
            fields.append(f"{k} = ?")
            values.append(v)

        fields.append("updated_on = ?")
        values.append(datetime.now().isoformat())

        sql = f"""
            UPDATE tradefriend_settings
            SET {', '.join(fields)}
            WHERE id = 1
        """
        self.cur.execute(sql, values)
        self.conn.commit()

    def get_trade_mode(self) -> str:
        row = self.fetch()
        return row["trade_mode"] if row and row["trade_mode"] else "PAPER"
    
    def adjust_available_swing_capital(self, delta: float):
        """
        Safely adjust available swing capital.

        Args:
            delta: Positive to release capital (exit), negative to allocate (new entry)
        """
        # Thread-safe lock
        if not hasattr(self, "_lock"):
            import threading
            self._lock = threading.Lock()

        with self._lock:
            row = self.fetch()
            current = row["available_swing_capital"] or 0
            # Prevent negative swing capital
            new_value = max(round(current + delta, 2), 0)

            # Persist update
            self.update({"available_swing_capital": new_value})

            # Logging
            action = "Released" if delta > 0 else "Allocated"
            logger.info(
                f"💰 {action} capital: {abs(delta)} | "
                f"Previous: {current} | New available: {new_value}"
            )

    def set_trade_mode(self, mode: str):
        self.update({"trade_mode": mode})


    def get_total_capital(self) -> float:
        row = self.fetch()
        return float(row["total_capital"]) if row and row["total_capital"] is not None else 0.0

    def get_max_swing_capital(self) -> float:
        row = self.fetch()
        return float(row["max_swing_capital"]) if row and row["max_swing_capital"] is not None else 0.0

    def get_available_swing_capital(self) -> float:
        row = self.fetch()
        return float(row["available_swing_capital"]) if row and row["available_swing_capital"] is not None else 0.0

    def get_max_per_trade_capital(self) -> float:
        row = self.fetch()
        return float(row["max_per_trade_capital"]) if row and row["max_per_trade_capital"] is not None else 0.0

    def get_max_open_trades(self) -> int:
        row = self.fetch()
        return int(row["max_open_trades"]) if row and row["max_open_trades"] is not None else 0
