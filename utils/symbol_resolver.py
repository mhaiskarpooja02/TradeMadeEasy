"""
================================================================================
Module: symbol_resolver.py
Description:
    Resolves holdings symbols to Angel One required format (symbol, token, exchange)
    using NSEEQTYdata.json and instruments stored in SQLite (DhanDBHelper).
Usage:
    from utils.symbol_resolver import SymbolResolver
================================================================================
"""
import os
import json

from config.TradeFriendSettings import NSE_EQTY_FILE, MASTERDATA_DIR,SYMBOL_MASTER_FILE

from utils.logger import get_logger
logger = get_logger(__name__)

# ================================================================================
# CLASS: SymbolResolver
# ================================================================================
class SymbolResolver:
    """
    Reads instruments from SQLite and NSE token data to resolve trading symbols 
    for Angel One.

    Attributes:
        holdings (list): List of holdings read from instruments (SQLite).
        nse_data (list): List of token info from NSEEQTYdata.json.
    """

    # ------------------------------------------------------------------------
    def __init__(self):
        """
        Initialize SymbolResolver with holdings (from DB) and NSE token mapping.
        """
        # ✅ Fetch holdings directly from DB
        # self.db = DhanDBHelper()
        # self.holdings = self.db.get_all() or []

        # Load NSE token master
        with open(NSE_EQTY_FILE, "r") as f:
            self.nse_data = json.load(f)

    # ------------------------------------------------------------------------
    def resolve_all(self):
        """
        Resolve all holdings symbols to objects containing:
            - symbol: e.g., 'CSLFINANCE-EQ'
            - token: Angel One / NSE token
            - exchange: NSE (default)

        Returns:
            list of dicts: [{symbol, token, exchange}, ...]
        """
        resolved_list = []
        for item in self.holdings:
            name = item.get("symbol")  # e.g., 'CSLFINANCE'
            if not name:
                continue

            symbol_eq = f"{name}-EQ" if not name.endswith("-EQ") else name
            token_info = next((x for x in self.nse_data if x["symbol"] == symbol_eq), None)

            if not token_info:
                logger.error(f"Token not found for {symbol_eq}, skipping.")
                continue

            resolved_list.append({
                "symbol": symbol_eq,
                "token": token_info["token"],
                "exchange": token_info.get("exch_seg", "NSE")
            })

        logger.info(f"Resolved {len(resolved_list)} symbols for Angel One.")
        return resolved_list

    # ------------------------------------------------------------------------
    def resolve_symbol(self, symbol_name: str):
        """
        Resolve a single symbol to Angel One format.

        Args:
            symbol_name (str): Name of the symbol, e.g., 'CSLFINANCE'

        Returns:
            dict | None: {symbol, token, exchange} or None if not found
        """
        if not symbol_name:
            return None

        # Normalize: append -EQ only if not already there
        symbol_eq = f"{symbol_name}-EQ" if not symbol_name.endswith("-EQ") else symbol_name

        token_info = next((x for x in self.nse_data if x["symbol"] == symbol_eq), None)
        if not token_info:
            logger.error(f"Token not found for {symbol_eq}")
            return None

        resolved = {
            "symbol": symbol_eq,
            "token": token_info["token"],
            "exchange": token_info.get("exch_seg", "NSE"),
            "trading_symbol": symbol_eq,
        }
        logger.info(f"Resolved symbol: {resolved}")
        return resolved

    # ---------------------------------------------------------------------
    # Formatter for resolve_symbol
    # ---------------------------------------------------------------------
    def resolve_symbol_tradefinder(self, trading_symbol):
        """
        Resolve Trading Symbol (already with -EQ) → Token from NSEEQTYdata.json.
        """
        nse_file = os.path.join(MASTERDATA_DIR, "NSEEQTYdata.json")
        if not os.path.exists(nse_file):
            raise FileNotFoundError("NSEEQTYdata.json missing")

        with open(nse_file, "r") as f:
            nse_data = json.load(f)

        token_info = next((item for item in nse_data if item.get("symbol") == trading_symbol), None)
        token = token_info.get("token") if token_info else None

        return {
            "custom_name": "",
            "trading_symbol": trading_symbol,
            "token": token
        }
    # ---------------------------------------------------------------------
    # extract symbol objects
    # ---------------------------------------------------------------------
    
    def extract_symbol_objects(self,result: dict):
        """
        Extract all tradingsymbols ending with -EQ or -SQ
        and build structured objects for them.
        """
        try:
            if not result or "data" not in result:
                return []
    
            extracted = []
            for entry in result["data"]:
                tradingsymbol = entry.get("tradingsymbol", "")
                if tradingsymbol.endswith(("-EQ")):
                    symbol_name = tradingsymbol.replace("-EQ", "")
                    extracted.append({
                        "token": entry.get("symboltoken", ""),
                        "symbol": tradingsymbol,
                        "name": symbol_name,
                        "expiry": "",
                        "strike": "-1.000000",
                        "lotsize": "1",
                        "instrumenttype": "",
                        "exch_seg": entry.get("exchange", "NSE"),
                        "tick_size": "5.000000"
                    })
            return extracted
        except Exception as e:
            logger.error(f"Error extracting symbol objects: {e}")
            return []
        
    # ---------------------------------------------------------------------
    # get_symbol_tradefinder
    # ---------------------------------------------------------------------
    def get_symbol_tradefinder(self, name):
        """
        Resolve Trading Symbol (SEM_CUSTOM_SYMBOL → SEM_TRADING_SYMBOL) from symbolnamemaster.json.
        """
        master_file = SYMBOL_MASTER_FILE
        if not os.path.exists(master_file):
            raise FileNotFoundError("symbolnamemaster.json missing in masterdata folder")

        with open(master_file, "r") as f:
            master_data = json.load(f)

        logger.info(f"Master file loaded: {master_file}")
        logger.info(f"Records loaded: {len(master_data)}")

         # Validate name
        if not name:
            logger.warning("get_symbol_tradefinder received empty or null name.")
            return None

        # Find the matching item
        logger.info(f"Entered into get_symbol_tradefinder with value {name}")

        match = next(
                (item for item in master_data if name.lower() in item["SEM_CUSTOM_SYMBOL"].lower()), 
                None
            )
        if match:
           logger.info(f"Found into get_symbol_tradefinder with value {match['SEM_TRADING_SYMBOL']}")
           return {"trading_symbol": match["SEM_TRADING_SYMBOL"]}
        
        return None
    
    @staticmethod
    def search_by_name( query):
        """
        Return a list of SEM_CUSTOM_SYMBOLs matching partial query (for dropdown suggestions)
        """
        master_file = os.path.join(MASTERDATA_DIR, "symbolnamemaster.json")
        if not os.path.exists(master_file):
            return []

        with open(master_file, "r") as f:
            master_data = json.load(f)

        # Return top matches containing query (case-insensitive)
        results = [item["SEM_CUSTOM_SYMBOL"] for item in master_data if query.lower() in item["SEM_CUSTOM_SYMBOL"].lower()]
        return results[:20]  # limit top 20 suggestions