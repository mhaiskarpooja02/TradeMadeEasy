from strategy.TradeFriendEntry import TradeFriendEntry
from strategy.TradeFriendScoring import TradeFriendScoring
from core.TradeFriendPositionSizer import TradeFriendPositionSizer
from core.TradeFriendDecisionEngine import TradeFriendDecisionEngine


def run_morning_entry(symbol, df, capital, trade_repo):
    entry_strategy = TradeFriendEntry(df, symbol)
    signal = entry_strategy.confirm_entry()

    if not signal:
        return None

    decision_engine = TradeFriendDecisionEngine(
        scorer=TradeFriendScoring(),
        sizer=TradeFriendPositionSizer(risk_percent=1),
        trade_repo=trade_repo
    )

    return decision_engine.evaluate(df, signal, capital)
