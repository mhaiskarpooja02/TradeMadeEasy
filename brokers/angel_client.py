"""
================================================================================
Module: angel_client.py
Description:
    Handles Angel One SmartAPI login and fetching LTP for resolved symbols.
    Provides a singleton-style helper function `getltp` for easy use.
Usage:
    from broker.angel_client import getltp
================================================================================
"""
import time
import pyotp
from SmartApi import SmartConnect
from utils.logger import get_logger
import pandas as pd
from datetime import datetime, timedelta
from config.TradeFriendSettings import api_key, username, pin, totp_qr,DEFAULT_INTERVAL,LOOKBACK_DAYS, RangeBoundLOOKBACK_DAYS

logger = get_logger(__name__)

# ------------------------------------------------------------------------
# Singleton Client Holder
# ------------------------------------------------------------------------
_client = None


# ================================================================================
# CLASS: AngelClient
# ================================================================================
class AngelClient:
    """
    Handles Angel One SmartAPI login, LTP fetch, and historical data.
    """
    # ================================================================================
    
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.smart_api = None
        self.login()
        self._initialized = True


    # ================================================================================
    def login(self):
        """Login to SmartAPI and store session if successful."""
        try:
            smart_api = SmartConnect(api_key=api_key)
            totp = pyotp.TOTP(totp_qr).now()
            data = smart_api.generateSession(username, pin, totp)

            if data.get("status", False):
                self.smart_api = smart_api
                logger.info(" Logged in to Angel One SmartAPI")
            else:
                logger.error(" Angel One login failed")
        except Exception as e:
            logger.error(f"SmartAPI login error: {e}")

    # ================================================================================
    def get_ltp(self, resolved_symbol: dict):
        """Fetch LTP for a single resolved symbol."""
        try:
            logger.info(f"Fetched LTP for {resolved_symbol['symbol']}")
            data = self.smart_api.ltpData(
                resolved_symbol["exchange"],
                resolved_symbol["symbol"],
                str(resolved_symbol["token"])
            )

            if not data or not data.get("data"):
                logger.warning(
                    f"⚠️ Empty LTP payload from Angel | {resolved_symbol['symbol']}"
                )
                return None   # ⛔ NOT an exception
        
            ltp = data["data"]["ltp"]

            if not data or not data.get("data"):
              logger.warning(
                  f"⚠️ Empty LTP payload from Angel | {resolved_symbol['symbol']}"
              )
              return None   # ⛔ NOT an exception

            logger.info(f"Fetched LTP for {resolved_symbol['symbol']}: {ltp}")
            return ltp
        except Exception as e:
            logger.error(f"Failed to fetch LTP for {resolved_symbol['symbol']}: {e}")
            return None

    # ================================================================================
    def get_ltp_bulk(self, resolved_list):
        """Fetch LTP for multiple resolved symbols."""
        results = {}
        for item in resolved_list:
            ltp = self.get_ltp(item)
            if ltp is not None:
                results[item["symbol"]] = ltp
        logger.info(f"Fetched LTP for {len(results)} symbols.")
        return results

    # ================================================================================
    def get_holdings(self):
        """Placeholder for holdings API (currently empty)."""
        return []
    # ================================================================================
    def search_symbol(self, exchange: str, symbol: str):
        """
        Search a symbol on Angel SmartAPI.
        Returns: raw response dict (same as API).
        """
        try:
            logger.info(f" Searching symbol {symbol} in Angel API...")
            result = self.smart_api.searchScrip(exchange, symbol)
            return result
        except Exception as e:
            logger.error(f"Search failed for {symbol}: {e}")
            return {}

    # ================================================================================
    def get_historical_data(
        self,
        symbol,
        token,
        interval=DEFAULT_INTERVAL,
        days=None,
        max_retries=3,
        delay=2
    ):
        """
        Fetch historical OHLC candles with retry & session reset handling.
        """
        session_reset_done = False
        if days is None:
            days = LOOKBACK_DAYS 
            

        for attempt in range(1, max_retries + 1):
            try:
                to_date = datetime.now()
                from_date = to_date - timedelta(days=days)
                
                params = {
                    "exchange": "NSE",
                    "symboltoken": str(token),
                    "interval": interval,
                    "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
                    "todate": to_date.strftime("%Y-%m-%d %H:%M"),
                    "symbol": symbol,
                }

                data = self.smart_api.getCandleData(params)
                msg = data.get("message", "Unknown error") if isinstance(data, dict) else "No response"

                if not data or "data" not in data:
                    logger.error(f"{symbol} ({token}) -> No historical data | Response: {msg}")
                    return None

                if isinstance(data.get("data"), list) and len(data["data"]) == 0:
                    logger.warning(f"{symbol} ({token}) → No historical data available (empty list)")
                    return None

                if "Session" in msg and not session_reset_done:
                    logger.warning("⚠️ Session expired. Re-logging in...")
                    self.login()
                    session_reset_done = True
                    continue

                df = pd.DataFrame(
                    data["data"],
                    columns=["datetime", "open", "high", "low", "close", "volume"],
                )
                df["datetime"] = pd.to_datetime(df["datetime"])
                return df

            except Exception as e:
                err_msg = str(e)
                logger.error(f"Attempt {attempt}/{max_retries} failed for {symbol} ({token}): {err_msg}")

                if "No data" in err_msg or "No historical" in err_msg:
                    return None

            if attempt < max_retries:
                logger.info(f"Retrying {symbol} ({token}) after {delay}s...")
                time.sleep(delay)

        logger.error(f" Failed to fetch candles for {symbol} ({token}) after {max_retries} attempts")
        return None

    # ================================================================================
    def get_RangeBoundhistorical_data(
        self,
        symbol,
        token,
        interval=DEFAULT_INTERVAL,
        days=None,
        max_retries=3,
        delay=2
    ):
        """
        Fetch historical OHLC candles with retry & session reset handling.
        """
        session_reset_done = False
        if days is None:
            days = RangeBoundLOOKBACK_DAYS 
            

        for attempt in range(1, max_retries + 1):
            try:
                to_date = datetime.now()
                from_date = to_date - timedelta(days=days)
                logger.info(f"For ({token}) Date Range : from_date {from_date}  to_date {to_date}.")
                params = {
                    "exchange": "NSE",
                    "symboltoken": str(token),
                    "interval": interval,
                    "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
                    "todate": to_date.strftime("%Y-%m-%d %H:%M"),
                    "symbol": symbol,
                }

                data = self.smart_api.getCandleData(params)
                msg = data.get("message", "Unknown error") if isinstance(data, dict) else "No response"

                if not data or "data" not in data:
                    logger.error(f"{symbol} ({token}) -> No historical data | Response: {msg}")
                    return None

                if isinstance(data.get("data"), list) and len(data["data"]) == 0:
                    logger.warning(f"{symbol} ({token}) → No historical data available (empty list)")
                    return None

                if "Session" in msg and not session_reset_done:
                    logger.warning("⚠️ Session expired. Re-logging in...")
                    self.login()
                    session_reset_done = True
                    continue

                df = pd.DataFrame(
                    data["data"],
                    columns=["datetime", "open", "high", "low", "close", "volume"],
                )
                df["datetime"] = pd.to_datetime(df["datetime"])
                return df

            except Exception as e:
                err_msg = str(e)
                logger.error(f"Attempt {attempt}/{max_retries} failed for {symbol} ({token}): {err_msg}")

                if "No data" in err_msg or "No historical" in err_msg:
                    return None

            if attempt < max_retries:
                logger.info(f"Retrying {symbol} ({token}) after {delay}s...")
                time.sleep(delay)

        logger.error(f" Failed to fetch candles for {symbol} ({token}) after {max_retries} attempts")
        return None


    # ================================================================================
    def get_intraday_candles(self, symbol: str, token: str, interval="FIFTEEN_MINUTE", lookback_days=5):
            """
            Fetch intraday candles for the last N days using live market data (FULL mode).

            Args:
                symbol (str): Symbol name (e.g., "RELIANCE")
                token (str): Instrument token (e.g., "3045")
                interval (str): Interval string ("ONE_MINUTE", "FIVE_MINUTE", "FIFTEEN_MINUTE")
                lookback_days (int): Number of past days to fetch

            Returns:
                Dict[str, pd.DataFrame]:
                    {
                        "prev": last 3 candles of previous trading day,
                        "today": candles of the current day
                    }
            """
            try:
                import pandas as pd
                from datetime import datetime

                # Interval mapping
                interval_map = {
                    "ONE_MINUTE": "1T",
                    "FIVE_MINUTE": "5T",
                    "FIFTEEN_MINUTE": "15T"
                }
                resample_interval = interval_map.get(interval, "15T")

                # Fetch live market data
                exchangeTokens = {"1": [14552]}
               
                marketData = self.smart_api.getMarketData(mode="FULL", exchangeTokens=exchangeTokens)

                if not marketData or "NSE" not in marketData or token not in marketData["NSE"]:
                    logger.error(f" No market data available for {symbol} ({token})")
                    return {"prev": pd.DataFrame(), "today": pd.DataFrame()}

                ticks = marketData["NSE"][token]
                if not ticks:
                    logger.warning(f" No ticks found for {symbol} ({token})")
                    return {"prev": pd.DataFrame(), "today": pd.DataFrame()}

                # Convert ticks to DataFrame
                df = pd.DataFrame(ticks)
                df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.sort_values("datetime", inplace=True)

                # Aggregate into OHLCV candles
                candles = df.resample(resample_interval, on="datetime").agg({
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum"
                })
                candles.dropna(inplace=True)
                candles.reset_index(inplace=True)
                candles["date"] = candles["datetime"].dt.date

                today_date = pd.Timestamp.today().date()
                trading_days = sorted(d for d in candles["date"].unique() if d <= today_date)

                prev_day_last3 = pd.DataFrame()
                today_candles = pd.DataFrame()

                # Previous trading day last 3 candles
                prev_days = [d for d in trading_days if d < today_date]
                if prev_days:
                    prev_day_last = prev_days[-1]
                    prev_day_last3 = candles[candles["date"] == prev_day_last].tail(3)

                # Today’s candles
                today_candles = candles[candles["date"] == today_date]

                logger.info(f" {symbol} ({token}) → prev_day_last3: {len(prev_day_last3)} | today_candles: {len(today_candles)}")
                return {"prev": prev_day_last3, "today": today_candles}

            except Exception as e:
                logger.error(f" Error fetching intraday candles for {symbol} ({token}): {e}")
                return {"prev": pd.DataFrame(), "today": pd.DataFrame()}

    # ================================================================================
    def place_order(self, payload: dict) -> str:
        """
        Place order via Angel SmartAPI.

        Expected payload:
        {
            "variety": "NORMAL",
            "tradingsymbol": "SBIN-EQ",
            "symboltoken": "3045",
            "transactiontype": "BUY",
            "exchange": "NSE",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": 0,
            "quantity": 2
        }

        Returns:
            order_id (str)
        """
        try:
            if not self.smart_api:
                raise Exception("Angel client not logged in")

            order_id = self.smart_api.placeOrder(payload)
            return order_id

        except Exception as e:
            logger.error(f"Angel place_order failed: {e}")
            raise

# ================================================================================
# Singleton-style Helper Functions
# ================================================================================
def init_client():
    """
    Initialize and cache a single AngelClient instance (singleton).
    Returns:
        AngelClient
    """
    global _client
    if _client is None:
        _client = AngelClient()
    return _client


def getltp(resolved_symbol: dict):
    """
    Fetch LTP directly without manually creating AngelClient.
    Ensures singleton client is reused.

    Args:
        resolved_symbol (dict): {symbol, token, exchange}

    Returns:
        float | None: Last traded price
    """
    client = init_client()
    return client.get_ltp(resolved_symbol)

def search_symbol(exchange: str, symbol: str):
    """
    Singleton-style search symbol helper.
    Calls AngelClient.search_symbol internally.
    """
    client = init_client()
    return client.search_symbol(exchange, symbol)


