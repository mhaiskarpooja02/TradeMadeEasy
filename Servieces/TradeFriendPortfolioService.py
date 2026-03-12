# Servieces/TradeFriendPortfolioService.py

from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from Servieces.TradeFriendTradeViewService import TradeFriendTradeViewService
from Servieces.TradeFriendLtpService import ltp_service_instance
from utils.logger import get_logger

logger = get_logger(__name__)


class TradeFriendPortfolioService:

    def __init__(self):
        self.trade_repo = TradeFriendTradeRepo()
        self.ltp_service = ltp_service_instance

    # ==========================================================
    # INTERNAL: Build active rows once
    # ==========================================================
    def _build_active_rows(self):

        trades = self.trade_repo.fetch_active_trades()
        rows = []

        for trade in trades:

            if not isinstance(trade, dict):
                trade = dict(trade)

            symbol = trade.get("symbol")

            if not symbol:
                continue

            ltp = self.ltp_service.get_ltp(symbol)

            row = TradeFriendTradeViewService.active_trade_row(trade, ltp)

            if row:
                rows.append(row)

        return rows

    # ==========================================================
    # PUBLIC: Full Snapshot (Home + Dashboard)
    # ==========================================================
    def get_portfolio_snapshot(self, limit=50):

        rows = self._build_active_rows()

        gainers = []
        losers = []
        total = 0.0

        for row in rows:

            values = row["values"]
            pnl = values[7]

            if not isinstance(pnl, (int, float)):
                continue

            total += pnl

            data = {
                "symbol": values[0],
                "entry": values[1],
                "ltp": values[2],
                "qty": values[6],
                "pnl": pnl
            }

            if pnl > 0:
                gainers.append(data)
            elif pnl < 0:
                losers.append(data)

        gainers.sort(key=lambda x: x["pnl"], reverse=True)
        losers.sort(key=lambda x: x["pnl"])

        snapshot = {
            "gainers": gainers[:limit],
            "losers": losers[:limit],
            "total_pnl": round(total, 2)
        }

        return snapshot

    # ==========================================================
    # OPTIONAL: Backward Compatibility Methods
    # ==========================================================
    def get_active_trade_rows(self):
        return self._build_active_rows()

    def get_top_movers(self, limit=100):
        snapshot = self.get_portfolio_snapshot(limit)
        return snapshot["gainers"], snapshot["losers"]

    def get_total_portfolio_pnl(self):
        snapshot = self.get_portfolio_snapshot()
        return snapshot["total_pnl"]