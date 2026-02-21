import sqlite3
import os
from datetime import datetime

from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo




class TradeFriendOrderConfigReader:
    """
    Simple utility to read entire TradeFriend settings
    in one call without passing any column name.
    """

    def __init__(self):
        self.repo = TradeFriendSettingsRepo()

    def get(self) -> dict:
        """
        Return full settings row as dictionary (single line fetch).
        """
        return dict(self.repo.fetch() or {})
    

# -----------------------------------------
# USAGE
# -----------------------------------------
if __name__ == "__main__":
    config = TradeFriendOrderConfigReader().get()
    print(config)