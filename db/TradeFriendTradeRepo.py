import sqlite3
import os
import logging
from datetime import datetime, date

from db.TradeFriendTradeHistoryRepo import TradeFriendTradeHistoryRepo
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo

logger = logging.getLogger(__name__)

DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_trades.db")
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendTradeRepo:
    """
    PURPOSE:
    - Persist ACTIVE trades only
    - Lock / release swing capital safely
    - Handle PARTIAL exits
    - Archive trades on FINAL exit
    """

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self._create_table()

        self.history_repo = TradeFriendTradeHistoryRepo()
        self.settings_repo = TradeFriendSettingsRepo()

    # -------------------------------------------------
    # TABLE (ACTIVE ONLY)
    # -------------------------------------------------
    def _create_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tradefriend_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                swing_plan_id INTEGER,               -- 🔑 future linkage
                symbol TEXT NOT NULL,
                side TEXT NOT NULL DEFAULT 'BUY',

                entry REAL  NULL,
                sl REAL NOT NULL,
                trailing_sl REAL,
                target REAL NOT NULL,

                qty INTEGER NOT NULL,
                initial_qty INTEGER NOT NULL,
                remaining_qty INTEGER NOT NULL,

                position_value REAL NOT NULL,
                risk_amount REAL,
                planned_entry REAL NOT NULL,
                first_entry_time   TEXT,

                confidence REAL DEFAULT 0,
                status TEXT DEFAULT 'OPEN',      -- OPEN / PARTIAL
                hold_mode INTEGER DEFAULT 0,

                entry_day TEXT,
                created_on TEXT,
                updated_at TEXT
            )
        """)
        self.conn.commit()

    # -------------------------------------------------
    # CREATE TRADE (NO CAPITAL LOCKING HERE)
    # -------------------------------------------------
    def save_trade(self, trade: dict) -> int:
        """
        Creates a new trade record.
    
        IMPORTANT:
        - This method does NOT adjust capital.
        - Capital is deducted only after confirmed broker fill.
        """
    
        position_value = trade["entry"] * trade["qty"]
        risk_amount = abs(trade["entry"] - trade["sl"]) * trade["qty"]
    
        try:
            self.cursor.execute("""
                INSERT INTO tradefriend_trades (
                    swing_plan_id,
                    symbol,
                    side,
                    planned_entry,
                    entry,
                    sl,
                    trailing_sl,
                    target,
                    qty,
                    initial_qty,
                    remaining_qty,
                    position_value,
                    risk_amount,
                    confidence,
                    status,
                    hold_mode,
                    entry_day,
                    created_on
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                trade["swing_plan_id"],
                trade["symbol"],
                trade.get("side", "BUY"),
                trade["planned_entry"],
                trade["entry"],
                trade["sl"],
                trade["sl"],  # trailing_sl initially same as SL
                trade["target"],
    
                trade["qty"],
                trade["qty"],  # initial_qty
                trade["qty"],  # remaining_qty
    
                position_value,
                risk_amount,
                trade.get("confidence", 0),
                trade.get("status", "READY"),
                trade.get("hold_mode", 0),
                date.today().isoformat(),
                datetime.now().isoformat()
            ))
    
            self.conn.commit()
            return self.cursor.lastrowid
    
        except Exception as e:
            self.conn.rollback()
            raise e


    # -------------------------------------------------
    # FETCH
    # -------------------------------------------------
    def fetch_open_trades(self):
        return self.cursor.execute("""
            SELECT *
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
        """).fetchall()

    def fetch_by_id(self, trade_id: int):
        row = self.cursor.execute("""
            SELECT *
            FROM tradefriend_trades
            WHERE id = ?
        """, (trade_id,)).fetchone()

        return dict(row) if row else None

    def has_open_trade(self, symbol: str) -> bool:
        row = self.cursor.execute("""
            SELECT 1
            FROM tradefriend_trades
            WHERE symbol = ?
              AND status IN ('OPEN', 'PARTIAL')
            LIMIT 1
        """, (symbol,)).fetchone()
        return row is not None

    def promote_if_ready(self, trade_id: int, from_status: str, to_status: str) -> bool:
       self.cursor.execute("""
           UPDATE tradefriend_trades
           SET status = ?
           WHERE id = ?
           AND status = ?
       """, (to_status, trade_id, from_status))

       self.conn.commit()

       return self.cursor.rowcount == 1
    # -------------------------------------------------
    # SL / TRAILING SL
    # -------------------------------------------------
    def update_sl(self, trade_id: int, new_sl: float):
        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET sl = ?,
                trailing_sl = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_sl, new_sl, trade_id))
        self.conn.commit()

   # ==================================================
    # PARTIAL EXIT
    # ==================================================
    def mark_partial_exit(
        self,
        trade_id: int,
        exit_qty: int,
        exit_price: float,
        reason: str = "Partial Exit"
    ) -> int | None:

        trade = self.fetch_by_id(trade_id)
        if not trade:
            logger.warning(f"Partial exit failed | trade_id={trade_id} not found")
            return None

        remaining_qty = int(trade["remaining_qty"])
        if exit_qty <= 0 or remaining_qty <= 0:
            logger.warning(
                f"Partial exit skipped | trade_id={trade_id} | "
                f"exit_qty={exit_qty} | remaining_qty={remaining_qty}"
            )
            return None

        exit_qty = min(exit_qty, remaining_qty)
        entry_price = float(trade["entry"])
        new_remaining = remaining_qty - exit_qty

        # --------------------------
        # 1️⃣ Release Capital
        # --------------------------
        released_capital = round(entry_price * exit_qty, 2)
        self.settings_repo.adjust_available_swing_capital(released_capital)

        # --------------------------
        # 2️⃣ Realized PnL (optional audit)
        # --------------------------
        realized_pnl = round((exit_price - entry_price) * exit_qty, 2)

        # --------------------------
        # 3️⃣ Update trade table
        # --------------------------
        new_position_value = round(entry_price * new_remaining, 2)
        status = "PARTIAL" if new_remaining > 0 else "CLOSED"

        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET remaining_qty = ?,
                position_value = ?,
                status = ?,
                hold_mode = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            new_remaining,
            new_position_value,
            status,
            trade_id
        ))
        self.conn.commit()

        # --------------------------
        # 4️⃣ Archive partial exit for audit
        # --------------------------
        self.history_repo.archive_trade(
            trade=trade,
            exit_price=exit_price,
            exit_qty=exit_qty,
            exit_reason=reason,
            closed_on=datetime.now().isoformat(),
            partial=True
        )

        logger.info(
            f"➗ PARTIAL EXIT | trade_id={trade_id} | "
            f"qty={exit_qty} | exit_price={exit_price} | "
            f"remaining_qty={new_remaining} | released_capital={released_capital} | "
            f"realized_pnl={realized_pnl}"
        )

        return new_remaining

    # ==================================================
    # FULL EXIT → HISTORY
    # ==================================================
    def close_and_archive(
        self,
        trade_id: int,
        exit_price: float,
        exit_reason: str
    ):
        trade = self.fetch_by_id(trade_id)
        if not trade:
            logger.warning(f"Close and archive failed | trade_id={trade_id} not found")
            return

        filled_qty = trade["initial_qty"] - trade["remaining_qty"]
        if filled_qty <= 0:
            logger.warning(f"No capital to release for trade_id={trade_id}")
            return

        # --------------------------
        # 1️⃣ Release remaining capital
        # --------------------------
        released_capital = round(trade["position_value"], 2)
        self.settings_repo.adjust_available_swing_capital(released_capital)

        # --------------------------
        # 2️⃣ Archive full trade
        # --------------------------
        self.history_repo.archive_trade(
            trade=trade,
            exit_price=exit_price,
            exit_reason=exit_reason,
            closed_on=datetime.now().isoformat(),
            partial=False
        )

        # --------------------------
        # 3️⃣ Remove trade from active table
        # --------------------------
        self.cursor.execute(
            "DELETE FROM tradefriend_trades WHERE id = ?",
            (trade_id,)
        )
        self.conn.commit()

        logger.info(
            f"✅ FULL EXIT | trade_id={trade_id} | "
            f"qty={filled_qty} | exit_price={exit_price} | "
            f"released_capital={released_capital} | reason={exit_reason}"
        )
        
    # -------------------------------------------------
    # SYMBOL HELPERS
    # -------------------------------------------------
    def get_all_symbols(self) -> set:
        rows = self.cursor.execute("""
            SELECT DISTINCT symbol
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
        """).fetchall()
        return {r["symbol"] for r in rows}
    
    # -------------------------------------------------
    # fetch active Trade for Dashboard
    # -------------------------------------------------
    def fetch_active_trades(self, limit: int = 100):
        """
        Fetch active trades (OPEN / PARTIAL) ordered by most recent.
        """

        rows = self.cursor.execute(
            """
            SELECT *
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
            ORDER BY created_on DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

        statuses = list({r["status"] for r in rows}) if rows else []

        logger.info(
            "📦 fetch_active_trades | rows=%d | statuses=%s",
            len(rows),
            statuses
        )

        if rows:
            logger.debug(
                "📦 First active trade → %s",
                dict(rows[0])
            )

        return rows

    def fetch_ready_by_symbol(self, symbol: str):
        return self.cursor.execute("""
            SELECT *
            FROM tradefriend_trades
            WHERE symbol = ?
            AND status = 'READY'
            LIMIT 1
        """, (symbol,)).fetchone()

    def fetch_ready_trades(self, min_entry=120):
        return self.cursor.execute("""
            SELECT *
            FROM tradefriend_trades
            WHERE status = 'READY'
              AND entry > ?
              AND entry < 400
            ORDER BY confidence DESC, entry ASC
            LIMIT 10
        """, (min_entry,)).fetchall()

    # ----------------------------------------------
    # 📊 END-OF-DAY ENTRY EXECUTION REPORT
    # ----------------------------------------------
    def fetch_entries_by_date(self, report_date: str):
        """
        Fetch trades with executed entries for given date.
        """
    
        rows = self.cursor.execute(
            """
            SELECT *
            FROM tradefriend_trades
            WHERE entry_day = ?
             
            ORDER BY created_on ASC
            """,
            (report_date,)
        ).fetchall()
    
        logger.info(
            "📊 fetch_entries_by_date | date=%s | rows=%d",
            report_date,
            len(rows)
        )
    
        if rows:
            logger.debug(
                "📊 First entry execution → %s",
                dict(rows[0])
            )
    
        return rows
    
    # ----------------------------------------------
    # 📊 END-OF-DAY ENTRY EXECUTION REPORT
    # ----------------------------------------------
    
    def count_open_trades(self) -> int:
        """
        Count active trades (OPEN / PARTIAL).
        """
        cur = self.cursor.execute(
            """
            SELECT COUNT(*)
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
            """
        )
        return cur.fetchone()[0]


    def sum_open_position_value(self) -> float:
        """
        Sum position value of active trades (OPEN / PARTIAL).
        """
        cur = self.cursor.execute(
            """
            SELECT COALESCE(SUM(position_value), 0)
            FROM tradefriend_trades
            WHERE status IN ('OPEN', 'PARTIAL')
            """
        )
        return float(cur.fetchone()[0])

    # -------------------------------------------------
    # INVALIDATE TRADE (MISSED ENTRY)
    # -------------------------------------------------
    def invalidate_trade(self, trade_id: int, reason: str, status: str):
        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, trade_id))
        self.conn.commit()

    # -------------------------------------------------
    # UPDATE ENTRY FILL
    # -------------------------------------------------
    def update_entry_fill(
        self,
        trade_id: int,
        fill_qty: int,
        fill_price: float
    ):
        trade = self.fetch_by_id(trade_id)
        if not trade:
            return

        remaining = max(trade["remaining_qty"] - fill_qty, 0)

        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET entry = ?,
                remaining_qty = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (fill_price, remaining, trade_id))
        self.conn.commit()


    def update_ready_trade(self, trade_id: int, trade: dict):
        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET
                entry = ?,
                planned_entry = ?,
                sl = ?,
                target = ?,
                qty = ?,
                initial_qty = ?,
                remaining_qty = ?,
                confidence = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            AND status = 'READY'
        """, (
            trade["entry"],
            trade["planned_entry"],
            trade["sl"],
            trade["target"],
            trade["qty"],
            trade["qty"],
            trade["qty"],
            trade.get("confidence", 0),
            trade_id
        ))
        self.conn.commit()

    # -------------------------------------------------
       # MARK TRADE OPEN
    # -------------------------------------------------
    
    def mark_open(self, trade_id: int, avg_entry: float, entry_day: str, status: str):
        self.cursor.execute("""
            UPDATE tradefriend_trades
            SET entry = ?,
                entry_day = ?,
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (avg_entry, entry_day, status, trade_id))


    def update_hold_mode(self, trade_id: int, hold_mode: int):
        """
        Update trade hold state:
        0 = OPEN
        1 = PARTIAL_BOOKED
        2 = RUNNER
        """
        with self.conn:
            self.conn.execute(
                """
                UPDATE tradefriend_trades
                SET hold_mode = ?
                WHERE id = ?
                """,
                (hold_mode, trade_id)
            )



    def update_status(self, trade_id: int, status: str):
        """
        PURPOSE:
        - Update trade lifecycle state only
        - Used for READY → PARTIAL transitions
        """
        self.cursor.execute(
            """
            UPDATE tradefriend_trades
            SET status = ?
            WHERE id = ?
            """,
            (status, trade_id)
        )
        self.conn.commit()


    def rebuild_trade(self, trade: dict):
        self.cursor.execute("""
            INSERT INTO tradefriend_trades (
                id,
                swing_plan_id,
                symbol, side,
                planned_entry,
                entry, sl, trailing_sl, target,
                qty, initial_qty, remaining_qty,
                position_value, risk_amount,
                confidence, status,
                hold_mode, entry_day,
                created_on, updated_at
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            trade["id"],
            trade["swing_plan_id"],
            trade["symbol"],
            trade["side"],
            trade["planned_entry"],
            trade["entry"],
            trade["sl"],
            trade["trailing_sl"],
            trade["target"],
            trade["qty"],
            trade["initial_qty"],
            trade["remaining_qty"],
            trade["position_value"],
            trade["risk_amount"],
            trade["confidence"],
            trade["status"],
            trade["hold_mode"],
            trade["entry_day"],
            trade["created_on"],
            trade["updated_at"]
        ))

        self.conn.commit()   # 🔥 THIS IS REQUIRED
