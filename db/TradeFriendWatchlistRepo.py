import sqlite3
import os
from typing import Dict, List

# -------------------------------------------------
# DB CONFIG
# -------------------------------------------------
DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_algo.db")

os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendWatchlistRepo:
    """
    PURPOSE:
    - Persist scanner results (IDEA ONLY)
    - No execution data (entry / SL / target)
    - Single source of truth for scan output
    """

    # -------------------------------------------------
    # INIT
    # -------------------------------------------------
    def __init__(self):
        self.conn = sqlite3.connect(
            DB_FILE,
            check_same_thread=False
        )
        self.conn.row_factory = sqlite3.Row

        # 🔒 Concurrency safety
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA busy_timeout = 5000;")

        self._create_table()

    # -------------------------------------------------
    # SCHEMA
    # -------------------------------------------------
    def _create_table(self):
        """
        IMPORTANT:
        - Drop old watchlist table ONCE before using
        """

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS tradefriend_watchlist (
            symbol TEXT PRIMARY KEY,
            strategy TEXT,
            bias TEXT,
            score INTEGER,
            scanned_on TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'WATCH'
        )
        """)

        # Indexes
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_watchlist_status
            ON tradefriend_watchlist(status)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_watchlist_scanned
            ON tradefriend_watchlist(scanned_on)
        """)

        self.conn.commit()

    # -------------------------------------------------
    # UPSERT (MAIN ENTRY POINT)
    # -------------------------------------------------
    def upsert(self, record: Dict):
        """
        record must contain:
        {
            symbol,
            strategy,
            bias,
            score
        }
        """

        if not record or not record.get("symbol"):
            return

        self.conn.execute("""
            INSERT INTO tradefriend_watchlist
                (symbol, strategy, bias, score, scanned_on, status)
            VALUES
                (?, ?, ?, ?, datetime('now'), 'WATCH')
            ON CONFLICT(symbol) DO UPDATE SET
                strategy   = excluded.strategy,
                bias       = excluded.bias,
                score      = excluded.score,
                scanned_on = datetime('now'),
                status     = 'WATCH'
        """, (
            record["symbol"],
            record.get("strategy"),
            record.get("bias"),
            int(record.get("score") or 0)
        ))

        self.conn.commit()

    # -------------------------------------------------
    # READ — FULL WATCHLIST
    # -------------------------------------------------
    def fetch_all(self) -> List[sqlite3.Row]:
        cursor = self.conn.execute("""
            SELECT *
            FROM tradefriend_watchlist
            WHERE status = 'WATCH'
            ORDER BY scanned_on DESC
        """)
        return cursor.fetchall()

    # -------------------------------------------------
    # READ — SYMBOL MAP (FAST LOOKUP)
    # -------------------------------------------------
    def get_symbol_map(self) -> Dict[str, dict]:
        cursor = self.conn.execute("""
            SELECT *
            FROM tradefriend_watchlist
            WHERE status = 'WATCH'
        """)

        result = {}
        for r in cursor.fetchall():
            row = dict(r)
            result[row["symbol"]] = row

        return result

    # -------------------------------------------------
    # READ — SYMBOL LIST
    # -------------------------------------------------
    def get_all_symbols(self) -> set:
        rows = self.conn.execute("""
            SELECT symbol
            FROM tradefriend_watchlist
            WHERE status = 'WATCH'
        """).fetchall()

        return {r["symbol"] for r in rows}

    # -------------------------------------------------
    # UPDATE — MARK TRIGGERED
    # -------------------------------------------------
    def mark_triggered(self, symbol: str):
        if not symbol:
            return

        self.conn.execute("""
            UPDATE tradefriend_watchlist
            SET status = 'TRIGGERED'
            WHERE symbol = ?
        """, (symbol,))
        self.conn.commit()

    # -------------------------------------------------
    # DELETE — STALE WATCHLIST
    # -------------------------------------------------
    def delete_untriggered_older_than(self, days: int = 7):
        self.conn.execute("""
            DELETE FROM tradefriend_watchlist
            WHERE scanned_on <= datetime('now', ?)
              AND status = 'WATCH'
        """, (f'-{days} days',))

        self.conn.commit()

    # -------------------------------------------------
    # HARD RESET (FRESH START)
    # -------------------------------------------------
    def reset_all(self):
        self.conn.execute("DELETE FROM tradefriend_watchlist")
        self.conn.commit()

    # -------------------------------------------------
    # CLOSE CONNECTION
    # -------------------------------------------------
    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
