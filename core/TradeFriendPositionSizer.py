# core/TradeFriendPositionSizer.py

from utils.logger import get_logger
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo

logger = get_logger(__name__)


class TradeFriendPositionSizer:
    """
    PURPOSE:
    - Calculate trade quantity using PRICE → FIXED QTY slabs
    - Enforce per-trade & available swing capital limits
    - Fully amount-based (no % risk logic)
    - Clean constraint layering (no silent double mutation)
    """

    def __init__(self):
        self.settings_repo = TradeFriendSettingsRepo()

    # -------------------------------------------------
    # MAIN
    # -------------------------------------------------
    def calculate(self, entry_price: float) -> dict:
        """
        Always returns:
        {
            qty: int,
            entry: float,
            position_value: float
        }
        """

        if not entry_price or entry_price <= 0:
            raise ValueError("Invalid entry price")

        raw_settings = self.settings_repo.fetch()
        settings = dict(raw_settings) if raw_settings else {}

        logger.info(
            f"PositionSizer.calculate() | Entry={entry_price} | Settings={settings}"
        )

        # -------------------------------------------------
        # 1️⃣ BASE QTY FROM PRICE SLABS
        # -------------------------------------------------
        base_qty = self._qty_by_price(entry_price, settings)

        if base_qty <= 0:
            logger.info(f"Qty disabled by price slabs | Entry={entry_price}")
            return self._zero_qty(entry_price)

        # -------------------------------------------------
        # 2️⃣ CAPITAL CONSTRAINTS
        # -------------------------------------------------
        max_per_trade = float(settings.get("max_per_trade_capital") or 0)
        available_capital = float(settings.get("available_swing_capital") or 0)

        qty_by_trade_cap = float("inf")
        if max_per_trade > 0:
            qty_by_trade_cap = int(max_per_trade / entry_price)

        qty_by_available_cap = float("inf")
        if available_capital > 0:
            qty_by_available_cap = int(available_capital / entry_price)

        # Final allowed quantity
        final_qty = min(base_qty, qty_by_trade_cap, qty_by_available_cap)

        if final_qty <= 0:
            logger.info(
                "Qty reduced to zero after capital constraints | "
                f"Entry={entry_price} | "
                f"BaseQty={base_qty} | "
                f"MaxTradeCap={max_per_trade} | "
                f"AvailCap={available_capital}"
            )
            return self._zero_qty(entry_price)

        position_value = round(final_qty * entry_price, 2)

        logger.info(
            f"Position Sized | Entry={entry_price} | "
            f"BaseQty={base_qty} | FinalQty={final_qty} | "
            f"PositionValue={position_value}"
        )

        return {
            "qty": int(final_qty),
            "entry": float(entry_price),
            "position_value": position_value
        }

    # -------------------------------------------------
    # PRICE → QTY SLABS
    # -------------------------------------------------
    def _qty_by_price(self, price: float, settings: dict) -> int:
        """
        Highest matching slab wins
        """

        slabs = [
            (2000, settings.get("qty_gt_2000", 0)),
            (1500, settings.get("qty_gt_1500", 0)),
            (1000, settings.get("qty_gt_1000", 0)),
            (700,  settings.get("qty_gt_700", 0)),
            (500,  settings.get("qty_gt_500", 0)),
            (200,  settings.get("qty_gt_200", 0)),
            (100,  settings.get("qty_gt_100", 0)),
        ]

        for min_price, qty in slabs:
            try:
                qty = int(qty or 0)
            except Exception:
                qty = 0

            if price >= min_price and qty > 0:
                return qty

        return 0

    # -------------------------------------------------
    # ZERO-QTY SAFE RETURN
    # -------------------------------------------------
    def _zero_qty(self, entry_price: float) -> dict:
        return {
            "qty": 0,
            "entry": float(entry_price),
            "position_value": 0.0
        }
