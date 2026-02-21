# runner/TradeFriendTradeViewService.py

from utils.logger import get_logger

logger = get_logger(__name__)


class TradeFriendTradeViewService:

    # ==================================================
    # ACTIVE TRADE ROW (Pure Transformer)
    # ==================================================
    @staticmethod
    def active_trade_row(trade: dict, ltp):

        try:
            symbol = trade.get("symbol")

            entry = float(trade.get("entry", 0))
            sl = float(trade.get("sl", 0))
            target = float(trade.get("target", 0))

            # Quantities
            init_qty = int(trade.get("initial_qty") or trade.get("qty") or 0)
            rem_qty = int(trade.get("remaining_qty", init_qty))

            # Derived status
            status = trade.get("status", "OPEN")
            if rem_qty <= 0:
                status = "CLOSED"
            elif rem_qty < init_qty:
                status = "PARTIAL"

            # Risk & PnL
            risk_per_unit = abs(entry - sl)

            pnl = (
                round((ltp - entry) * rem_qty, 2)
                if isinstance(ltp, (int, float)) and rem_qty > 0
                else "--"
            )

            r_mult = (
                round((ltp - entry) / risk_per_unit, 2)
                if isinstance(ltp, (int, float)) and risk_per_unit > 0
                else "--"
            )

            # Progress to target
            progress = "--"
            if isinstance(ltp, (int, float)) and target != entry:
                progress = f"{round(((ltp - entry) / (target - entry)) * 100, 1)}%"

            # Row color tag
            tag = ""
            if isinstance(pnl, (int, float)):
                if pnl > 0:
                    tag = "profit"
                elif pnl < 0:
                    tag = "loss"

            return {
                "values": (
                    symbol,
                    round(entry, 2),
                    ltp if ltp else "--",
                    round(sl, 2),
                    round(target, 2),
                    init_qty,
                    rem_qty,
                    pnl,
                    r_mult,
                    progress,
                    status
                ),
                "tag": tag
            }

        except Exception:
            logger.exception(
                f"Active row build failed | trade={trade} | ltp={ltp}"
            )
            return None

    # ==================================================
    # HISTORY TRADE ROW
    # ==================================================
    @staticmethod
    def history_trade_row(trade: dict):

        try:
            entry = float(trade["entry"])
            exit_price = float(trade["exit_price"])
            qty = int(trade["qty"])

            pnl = round((exit_price - entry) * qty, 2)
            risk = abs(entry - float(trade["sl"])) or 1
            r_mult = round((exit_price - entry) / risk, 2)

            return (
                trade["symbol"],
                round(entry, 2),
                round(exit_price, 2),
                qty,
                pnl,
                r_mult,
                trade["exit_reason"],
                trade["closed_on"]
            )

        except Exception:
            logger.exception(
                f"Failed to build history trade row | trade={trade}"
            )
            return None
