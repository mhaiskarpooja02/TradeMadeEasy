# core/TradeFriendMarketTimeService.py

from datetime import datetime, time as dtime


class TradeFriendMarketTimeService:
    """
    SINGLE SOURCE OF TRUTH for ALL market time logic.

    RESPONSIBILITIES:
    - Market open / close
    - Intraday trading windows
    - Scheduler phase windows
    - Time bucketing (5-min)
    - Weekend & special trading day handling
    - Safe for UI / DataProvider / Scheduler

    NON-RESPONSIBILITIES:
    - Broker calls
    - LTP fetching
    - Trading logic
    """

    # ==================================================
    # EXCHANGE CONFIG (NSE)
    # ==================================================
    MARKET_OPEN = dtime(9, 15)
    MARKET_CLOSE = dtime(15, 30)


    # ==================================================
    # EXCHANGE CONFIG (NSE)
    # ==================================================
    LTPMARKET_OPEN = dtime(7, 15)
    LTPMARKET_CLOSE = dtime(15, 59)

    # ==================================================
    # STRATEGY WINDOWS
    # ==================================================
    DAILY_SCAN_START = dtime(7, 0)
    DAILY_SCAN_END = dtime(8, 45)

    DECISION_START = dtime(9, 15)
    DECISION_END = dtime(9, 20)

    MORNING_CONFIRM_START = dtime(9, 17)
    MORNING_CONFIRM_END = dtime(9, 32)

    TRIGGER_START = dtime(9, 16)
    TRIGGER_END = dtime(15, 25)

    EOD_REPORT_START = dtime(22, 10)
    EOD_REPORT_END = dtime(22, 20)

    # ==================================================
    # SPECIAL DAYS (OVERRIDES)
    # ==================================================
    # Used for:
    # - Budget day trading on weekend
    # - Special exchange sessions
    # - Emergency market openings
    SPECIAL_TRADING_DAYS = {
         "2026-02-01",  # Example: Sunday special session
    }

    # Optional future hook
    MARKET_HOLIDAYS = {
        # "2026-01-26",  # Republic Day
    }

    # ==================================================
    # CORE CLOCK
    # ==================================================
    @staticmethod
    def now() -> datetime:
        """Centralized clock (mockable later)"""
        return datetime.now()

    @classmethod
    def today(cls) -> str:
        return cls.now().strftime("%Y-%m-%d")

    @classmethod
    def time(cls) -> dtime:
        return cls.now().time()

    @classmethod
    def weekday(cls) -> int:
        return cls.now().weekday()  # 0=Mon ... 6=Sun

    # ==================================================
    # DAY TYPE
    # ==================================================
    @classmethod
    def is_weekend(cls) -> bool:
        return cls.weekday() >= 5

    @classmethod
    def is_special_trading_day(cls) -> bool:
        return cls.today() in cls.SPECIAL_TRADING_DAYS

    @classmethod
    def is_market_holiday(cls) -> bool:
        return cls.today() in cls.MARKET_HOLIDAYS

    @classmethod
    def is_trading_day(cls) -> bool:
        """
        Final authority on whether the market is tradable today
        """
        if cls.is_market_holiday():
            return False

        if cls.is_special_trading_day():
            return True

        return not cls.is_weekend()

    # ==================================================
    # MARKET STATE
    # ==================================================
    @classmethod
    def is_market_open(cls) -> bool:
        if not cls.is_trading_day():
            return False

        t = cls.time()
        return cls.MARKET_OPEN <= t <= cls.MARKET_CLOSE
    @classmethod
    def is_LTPmarket_open(cls) -> bool:
        if not cls.is_trading_day():
            return False

        t = cls.time()
        return cls.LTPMARKET_OPEN <= t <= cls.LTPMARKET_CLOSE

    @classmethod
    def is_pre_market(cls) -> bool:
        if not cls.is_trading_day():
            return False
        return cls.time() < cls.MARKET_OPEN

    @classmethod
    def is_post_market(cls) -> bool:
        if not cls.is_trading_day():
            return True
        return cls.time() > cls.MARKET_CLOSE

    @classmethod
    def market_phase(cls) -> str:
        """
        Returns:
            PRE_MARKET | OPEN | POST_MARKET | CLOSED
        """
        if cls.is_market_open():
            return "OPEN"
        if cls.is_pre_market():
            return "PRE_MARKET"
        if cls.is_post_market():
            return "POST_MARKET"
        return "CLOSED"

    # ==================================================
    # RANGE HELPERS
    # ==================================================
    @classmethod
    def _in_range(cls, start: dtime, end: dtime) -> bool:
        t = cls.time()
        return start <= t <= end

    # ==================================================
    # STRATEGY WINDOWS
    # ==================================================
    @classmethod
    def is_daily_scan_time(cls) -> bool:
        return cls.is_trading_day() and cls._in_range(
            cls.DAILY_SCAN_START, cls.DAILY_SCAN_END
        )

    @classmethod
    def is_decision_time(cls) -> bool:
        return cls.is_trading_day() and cls._in_range(
            cls.DECISION_START, cls.DECISION_END
        )

    @classmethod
    def is_morning_confirm_time(cls) -> bool:
        return cls.is_trading_day() and cls._in_range(
            cls.MORNING_CONFIRM_START, cls.MORNING_CONFIRM_END
        )

    @classmethod
    def is_trigger_time(cls) -> bool:
        return cls.is_trading_day() and cls._in_range(
            cls.TRIGGER_START, cls.TRIGGER_END
        )

    @classmethod
    def is_eod_report_time(cls) -> bool:
        return cls.is_trading_day() and cls._in_range(
            cls.EOD_REPORT_START, cls.EOD_REPORT_END
        )

    # ==================================================
    # TIME BUCKETS
    # ==================================================
    @classmethod
    def five_minute_bucket(cls) -> datetime:
        """
        Returns normalized datetime for 5-minute engine protection
        """
        now = cls.now()
        minute = (now.minute // 5) * 5
        return now.replace(minute=minute, second=0, microsecond=0)

    @classmethod
    def minute_key(cls) -> str:
        return cls.now().strftime("%Y-%m-%d %H:%M")

    # ==================================================
    # SAFE UI / DATA HELPERS
    # ==================================================
    @classmethod
    def can_refresh_ui(cls) -> bool:
        return cls.is_market_open()

    @classmethod
    def can_fetch_ltp(cls, allow_pre_market: bool = False) -> bool:
        if allow_pre_market:
            return cls.is_trading_day()
        return cls.is_LTPmarket_open()

    # ==================================================
    # DEBUG / LOGGING
    # ==================================================
    @classmethod
    def snapshot(cls) -> dict:
        """
        Useful for logs & debugging
        """
        return {
            "now": cls.now().strftime("%Y-%m-%d %H:%M:%S"),
            "weekday": cls.weekday(),
            "is_weekend": cls.is_weekend(),
            "special_trading_day": cls.is_special_trading_day(),
            "holiday": cls.is_market_holiday(),
            "phase": cls.market_phase(),
            "market_open": cls.is_market_open(),
            "daily_scan": cls.is_daily_scan_time(),
            "decision": cls.is_decision_time(),
            "morning_confirm": cls.is_morning_confirm_time(),
            "trigger": cls.is_trigger_time(),
            "eod_report": cls.is_eod_report_time(),
        }
