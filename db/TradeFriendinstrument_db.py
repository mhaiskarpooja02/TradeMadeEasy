import os
import re
import sqlite3
from datetime import datetime


# -----------------------------
# DB PATH (separate database)
# -----------------------------
DB_FOLDER = "db"
DB_FILE = os.path.join(DB_FOLDER, "tradefindinstrument.db")

# Ensure folder exists
os.makedirs(DB_FOLDER, exist_ok=True)

VALID_SYMBOL_RE = re.compile(r"^[A-Z0-9\-]+$")  # RELIANCE-EQ

# -----------------------------
# DB Helper Class
# -----------------------------
class TradeFindDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._ensure_table()
        self._ensure_indexes()

    # ---------------------------------------------------
    # CONTEXT MANAGER
    # ---------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    # ---------------------------------------------------
    # TABLE
    # ---------------------------------------------------
    def _ensure_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tradefindinstrument (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                trading_symbol TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                is_active INTEGER DEFAULT 1,
                added_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deactivated_on TIMESTAMP
            )
        """)
        self.conn.commit()

    # ---------------------------------------------------
    # INDEXES
    # ---------------------------------------------------
    def _ensure_indexes(self):
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tfi_symbol
            ON tradefindinstrument(symbol)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tfi_trading_symbol
            ON tradefindinstrument(trading_symbol)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tfi_token
            ON tradefindinstrument(token)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tfi_active
            ON tradefindinstrument(is_active)
        """)
        self.conn.commit()

    # ---------------------------------------------------
    # 🔒 VALIDATION
    # ---------------------------------------------------
    def _validate_symbol(self, symbol):
        return isinstance(symbol, str) and bool(VALID_SYMBOL_RE.match(symbol.strip()))

    # ---------------------------------------------------
    # resolve_active_symbol
    # ---------------------------------------------------
    def resolve_active_symbol(self, symbol):
        """
        Returns dict compatible with Angel broker:
        {
            exchange,
            symbol,
            token
        }
        """
        self.cursor.execute("""
            SELECT trading_symbol, token
            FROM tradefindinstrument
            WHERE symbol = ?
              AND is_active = 1
            LIMIT 1
        """, (symbol,))
    
        row = self.cursor.fetchone()
        if not row:
            return None
    
        return {
            "exchange": "NSE",              # hardcoded for equity
            "symbol": row["trading_symbol"],
            "token": row["token"]
        }


    # ---------------------------------------------------
    # UPSERT (AUTO-REACTIVATE)
    # ---------------------------------------------------
    def upsert_symbol(self, symbol, trading_symbol, token):
        try:

            if not self._validate_symbol(symbol):
                raise ValueError(f"Invalid symbol: {symbol}")

            if not isinstance(trading_symbol, str) or not trading_symbol.strip():
                raise ValueError("Invalid trading_symbol")

            if not isinstance(token, str) or not token.strip():
                raise ValueError("Invalid token")
            

            self.cursor.execute("""
                INSERT INTO tradefindinstrument (
                    symbol, trading_symbol, token, is_active, deactivated_on
                )
                VALUES (?, ?, ?, 1, NULL)
                ON CONFLICT(symbol)
                DO UPDATE SET
                    trading_symbol = excluded.trading_symbol,
                    token = excluded.token,
                    is_active = 1,
                    deactivated_on = NULL
            """, (symbol, trading_symbol, token))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError as e:
            print(f"[DB CONSTRAINT ERROR] {symbol}: {e}")
            return False
        except Exception as e:
            print(f"[DB ERROR] {symbol}: {e}")
            return False
        
    # ---------------------------------------------------
    # 🧹 CLEANUP (RUN ONCE)
    # ---------------------------------------------------
    def cleanup_invalid_symbols(self):
        self.cursor.execute("""
            DELETE FROM tradefindinstrument
            WHERE symbol IS NULL
               OR TRIM(symbol) = ''
               OR symbol LIKE '<sqlite3.Row%'
               OR symbol LIKE '%object at%'
        """)
        self.conn.commit()

    # ---------------------------------------------------
    # SOFT DELETE / ACTIVATE
    # ---------------------------------------------------
    def deactivate_symbol(self, symbol):
        self.cursor.execute("""
            UPDATE tradefindinstrument
            SET is_active = 0,
                deactivated_on = CURRENT_TIMESTAMP
            WHERE symbol = ?
        """, (symbol,))
        self.conn.commit()

    def activate_symbol(self, symbol):
        self.cursor.execute("""
            UPDATE tradefindinstrument
            SET is_active = 1,
                deactivated_on = NULL
            WHERE symbol = ?
        """, (symbol,))
        self.conn.commit()

    # ---------------------------------------------------
    # READERS
    # ---------------------------------------------------
    def get_active(self):
        self.cursor.execute("""
            SELECT symbol, trading_symbol, token
            FROM tradefindinstrument
            WHERE is_active = 1
            ORDER BY symbol
        """)
        return self.cursor.fetchall()
    
    

    def get_inactive(self):
        self.cursor.execute("""
            SELECT symbol, trading_symbol, token, deactivated_on
            FROM tradefindinstrument
            WHERE is_active = 0
            ORDER BY symbol
        """)
        return self.cursor.fetchall()

    def search(self, text, active_only=True):
        pattern = f"%{text.upper()}%"
        sql = """
            SELECT symbol, trading_symbol, token, is_active
            FROM tradefindinstrument
            WHERE (UPPER(symbol) LIKE ?
               OR UPPER(trading_symbol) LIKE ?)
        """
        params = [pattern, pattern]

        if active_only:
            sql += " AND is_active = 1"

        sql += " ORDER BY symbol"

        self.cursor.execute(sql, params)
        return self.cursor.fetchall()

    # ---------------------------------------------------
    # STATS
    # ---------------------------------------------------
    def get_stats(self):
        self.cursor.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(is_active = 1) AS active,
                SUM(is_active = 0) AS inactive
            FROM tradefindinstrument
        """)
        return dict(self.cursor.fetchone())

    # ---------------------------------------------------
    # ONE-TIME RESET (MANUAL)
    # ---------------------------------------------------
    @staticmethod
    def reset_tradefind_table():
        if os.path.exists(DB_FILE):
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS tradefindinstrument")
            conn.commit()
            conn.close()
            print("⚠ tradefindinstrument table RESET")

            
# ---------------------------------------------------
# FILE PARSING (“NAME → TEXT” format)
# ---------------------------------------------------
def extract_symbols_from_files(file_list):
    """
    Read multiple text files and extract cleaned symbols before the '→' arrow.
    Removes bullet characters and symbols after →.
    """
    symbols = set()

    for file_path in file_list:
        if not os.path.exists(file_path):
            print(f"[FILE MISSING] {file_path}")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if "→" not in line:
                    continue

                before_arrow = line.split("→")[0].strip()

                # Remove • - whitespace prefix
                cleaned = re.sub(r"^[•\-\s]+", "", before_arrow)

                # Extract symbol pattern like MAXVOLT-EQ
                match = re.search(r"[A-Z0-9\-]+", cleaned)
                if match:
                    symbols.add(match.group())

    return sorted(symbols)


# ---------------------------------------------------
# MAIN SAVE FUNCTION
# ---------------------------------------------------
def save_files_to_db(file_list):
    """
    Complete workflow:
    - extract symbols from multiple files
    - insert into DB
    - return info
    """
    db = TradeFindDB()

    symbols = extract_symbols_from_files(file_list)
    print(f"Extracted {len(symbols)} unique symbols:")
    print(symbols)

    inserted = db.bulk_insert(symbols)
    print(f"\nInserted {inserted} new symbols into DB.")

    return symbols, inserted


# ---------------------------------------------------
# Example Usage (Remove if you don’t want auto-run)
# ---------------------------------------------------
if __name__ == "__main__":
    # Provide text files here
    sample_files = [
        "scan1.txt",
        "scan2.txt"
    ]
    TradeFindDB.reset_tradefind_table()
    # save_files_to_db(sample_files)

    db = TradeFindDB()
    # print("\nAll symbols:", db.get_all_symbols())
    # print("\nSearch 'MAN':", db.search("MAN"))
