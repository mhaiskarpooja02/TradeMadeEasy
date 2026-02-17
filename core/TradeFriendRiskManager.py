# core/TradeFriendRiskManager.py

from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo


class TradeFriendRiskManager:
    """
    PURPOSE:
    - Enforce swing trading guardrails
    - Amount-based (no percentages)
    - Stateless (reads repo + trade_repo only)
    - Returns allowed_qty for PositionSizer
    """

    def __init__(self):
        self.settings = TradeFriendSettingsRepo()

    # -------------------------------------------------
    # MAIN CHECK
    # -------------------------------------------------
    def can_take_trade(self, trade_repo, position_value: float, entry_price: float):
        """
        Returns:
            allowed: bool
            reason: str
            allowed_qty: int (based on price brackets)
        """
        #settings_data = self.settings.fetch()  # single fetch
        raw_settings = self.settings.fetch()
        settings_data = dict(raw_settings)  # 🔒 CRITICAL FIX
        # 1️⃣ MAX OPEN TRADES
        max_open_trades = settings_data["max_open_trades"] or 0
        if max_open_trades > 0 and trade_repo.count_open_trades() >= max_open_trades:
            return False, "Max open trades limit reached", 0

        # 2️⃣ TOTAL SWING CAPITAL
        max_swing_capital = settings_data["max_swing_capital"] or 0
        available_swing_capital = settings_data["available_swing_capital"] or 0
        used_capital = trade_repo.sum_open_position_value() or 0

        if max_swing_capital > 0 and (used_capital + position_value) > max_swing_capital:
            return False, "Max swing capital exceeded", 0

        if available_swing_capital > 0 and position_value > available_swing_capital:
            return False, "Position exceeds available swing capital", 0

        # 3️⃣ PER-TRADE CAPITAL
        max_per_trade = settings_data["max_per_trade_capital"] or 0
        if max_per_trade > 0 and position_value > max_per_trade:
            return False, "Per-trade capital cap exceeded", 0

        # 4️⃣ PRICE BRACKET VALIDATION
        allowed_qty = self._allowed_qty_for_price(entry_price, settings_data)
        if allowed_qty <= 0:
            return False, "Price not allowed per configured brackets", 0

        return True, "Allowed", allowed_qty

    # -------------------------------------------------
    # PRICE BRACKET CHECK
    # -------------------------------------------------
    def _allowed_qty_for_price(self, price: float, settings_data: dict) -> int:
        """
        Determine quantity allowed for a given price using settings
        """
        brackets = [
            {"min": 100, "qty": settings_data.get("qty_gt_100", 0)},
            {"min": 200, "qty": settings_data.get("qty_gt_200", 0)},
            {"min": 500, "qty": settings_data.get("qty_gt_500", 0)},
            {"min": 700, "qty": settings_data.get("qty_gt_700", 0)},
            {"min": 1000, "qty": settings_data.get("qty_gt_1000", 0)},
            {"min": 1500, "qty": settings_data.get("qty_gt_1500", 0)},
            {"min": 2000, "qty": settings_data.get("qty_gt_2000", 0)},
        ]

        allowed_qty = 0
        for b in brackets:
            if price >= b["min"] and b["qty"]:
                allowed_qty = b["qty"]

        return allowed_qty
