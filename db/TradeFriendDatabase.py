import sqlite3
import os

# DB path
DB_FOLDER = "dbdata"
DB_FILE = os.path.join(DB_FOLDER, "tradefriend_algo.db")

# Ensure db folder exists
os.makedirs(DB_FOLDER, exist_ok=True)


class TradeFriendDatabase:
    def __init__(self, db_path=DB_FILE):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def execute(self, query, params=()):
        cur = self.conn.cursor()
        cur.execute(query, params)
        self.conn.commit()
        return cur

    def fetchall(self, query, params=()):
        cur = self.execute(query, params)
        return cur.fetchall()

    def fetchone(self, query, params=()):
        cur = self.execute(query, params)
        return cur.fetchone()
