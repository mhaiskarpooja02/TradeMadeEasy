# runner/TradeFriendTradeViewService.py

from utils.logger import get_logger

logger = get_logger(__name__)


class TradeFriendTradeViewService:

    # ==================================================
    # ACTIVE TRADE ROW (Dashboard)
    # ==================================================
    @staticmethod
   
    def active_trade_row(trade, ltp):
        logger.info(
        "📊 ACTIVE_TRADE_ROW | symbol=%s | qty=%s | remaining_qty=%s | status=%s",
        trade.get("symbol"),
        trade.get("initial_qty"),
        trade.get("remaining_qty"),
        trade.get("status")
    )

        try:
            symbol = trade.get("symbol")

            entry = float(trade.get("entry", 0))
            sl = float(trade.get("sl", 0))
            target = float(trade.get("target", 0))

            # 🔑 Quantities
            init_qty = int(
                trade.get("initial_qty")
                or trade.get("qty")
                or 0
            )
            rem_qty = int(
                trade.get("remaining_qty", init_qty)
            )

            # -----------------------
            # Derived status (UI truth)
            # -----------------------
            status = trade.get("status", "OPEN")
            if rem_qty <= 0:
                status = "CLOSED"
            elif rem_qty < init_qty:
                status = "PARTIAL"

            # -----------------------
            # Risk & PnL
            # -----------------------
            risk_per_unit = abs(entry - sl)
            pnl = (
                round((ltp - entry) * rem_qty, 2)
                if ltp and rem_qty > 0
                else "--"
            )

            r_mult = (
                round((ltp - entry) / risk_per_unit, 2)
                if ltp and risk_per_unit > 0
                else "--"
            )

            # -----------------------
            # Progress to target
            # -----------------------
            progress = "--"
            if ltp and target != entry:
                progress = f"{round(((ltp - entry) / (target - entry)) * 100, 1)}%"

            # -----------------------
            # Row color tag
            # -----------------------
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
                    ltp or "--",
                    round(sl, 2),
                    round(target, 2),
                    init_qty,     # ✅ ADD THIS
                    rem_qty,          # ✅ show remaining qty
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
    def history_trade_row(trade):
        try:
            entry = float(trade["entry"])
            exit_price = float(trade["exit_price"])
            qty = int(trade["qty"])

            pnl = round((exit_price - entry) * qty, 2)
            risk = abs(entry - float(trade["sl"])) or 1
            r_mult = round((exit_price - entry) / risk, 2)

            row = (
                trade["symbol"],
                round(entry, 2),
                round(exit_price, 2),
                qty,
                pnl,
                r_mult,
                trade["exit_reason"],
                trade["closed_on"]
            )

            logger.debug(
                f"History row built | {trade['symbol']} | "
                f"Exit={exit_price} | PnL={pnl} | R={r_mult}"
            )

            return row

        except Exception as e:
            logger.exception(
                f"Failed to build history trade row | trade={trade}"
            )
            return None
