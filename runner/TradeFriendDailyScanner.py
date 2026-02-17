from strategy.TradeFriendScanner import TradeFriendScanner
from core.TradeFriendWatchlistEngine import TradeFriendWatchlistEngine


def run_daily_scanner(symbol, df, watchlist_repo):
    scanner = TradeFriendScanner(df, symbol)
    scan_result = scanner.scan()

    engine = TradeFriendWatchlistEngine(watchlist_repo)
    engine.process(scan_result)
