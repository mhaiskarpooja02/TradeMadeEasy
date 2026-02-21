# Servieces/TradeFriendLtpService.py

from core.TradeFriendDataProvider import TradeFriendDataProvider
from Servieces.TradeFriendMarketTimeService import TradeFriendMarketTimeService as MTS
from utils.logger import get_logger

logger = get_logger(__name__)


class TradeFriendLtpService:

    def __init__(self, ttl_seconds: int = 20):
        self.provider = TradeFriendDataProvider()
        self.ttl_seconds = ttl_seconds
        self.ltp_cache = {}

    # ============================================================
    # PUBLIC METHOD (Use this everywhere)
    # ============================================================
    def get_ltp(self, symbol: str):

        # 1️⃣ Try cache first
        cached_price = self._get_ltp_from_cache(symbol)
        if cached_price is not None:
            logger.info(f"[CACHE HIT] {symbol}")
            return cached_price

        # 2️⃣ Fetch from provider
        ltp = self._fetch_from_provider(symbol)

        if ltp is not None:
            self.ltp_cache[symbol] = (ltp, MTS.now())
            logger.info(f"[PROVIDER FETCH] {symbol}")
            return ltp

        # 3️⃣ Fallback to last known price
        logger.warning(f"[FALLBACK USED] {symbol}")
        return self.ltp_cache.get(symbol, (None, None))[0]

    # ============================================================
    # INTERNAL METHODS
    # ============================================================
    def _get_ltp_from_cache(self, symbol: str):

        cached = self.ltp_cache.get(symbol)
        if not cached:
            return None

        price, ts = cached
        if not ts:
            return None

        age = (MTS.now() - ts).total_seconds()

        if age <= self.ttl_seconds:
            return price

        return None

    def _fetch_from_provider(self, symbol: str):
        try:
            return self.provider.get_ltp_byLtp(symbol)
        except Exception as e:
            logger.error(f"LTP fetch failed for {symbol}: {e}")
            return None


# ============================================================
# SINGLETON INSTANCE (Global Shared Cache)
# ============================================================
ltp_service_instance = TradeFriendLtpService()