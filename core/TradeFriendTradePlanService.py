# core/trade_plan_service.py
import logging

from brokers.angel_client import AngelClient
from utils.logger import get_logger
from utils.symbol_resolver import SymbolResolver
from strategy.long_term_strategy import LongTermStrategy
from strategy.swing_strategy import SwingStrategy
from strategy.intraday_strategy import IntradayStrategy
from config.TradeFriendSettings import DEFAULT_INTERVAL

logger = get_logger(__name__)


class TradePlanService:
    def __init__(self):
        logger.info("Initializing TradePlanService...")

        # --- Broker ---
        self.broker = AngelClient()
        if getattr(self.broker, "smart_api", None) is None:
            logger.error(" Broker login failed (smart_api is None)")
            self.broker = None
        else:
            logger.info(" Broker login successful")

        # --- Resolver ---
        self.resolver = SymbolResolver()
        logger.info(" SymbolResolver initialized")

        # --- Strategy mapping ---
        self.strategy_map = {
            "long": LongTermStrategy,
            "swing": SwingStrategy,
            "intraday": IntradayStrategy,
        }

    # --------------------------
    # Prepare Trade Plan (returns report + strategy instance)
    # --------------------------
    def prepare_trade_plan(self, name_or_symbol, mode, entry_price, qty, strategy_cls=LongTermStrategy):
        logger.info(" Preparing trade plan | Input: %s %s %s %s", name_or_symbol, mode, entry_price, qty)

        trading_symbol, token = None, None

        try:
            # --- Resolve symbol ---
            if mode == "name":
                logger.info("Resolving symbol by name: %s", name_or_symbol)
                mapping = self.resolver.resolve_symbol_tradefinder(name_or_symbol)
                if not mapping:
                    logger.error(" No mapping found for %s", name_or_symbol)
                    raise ValueError(f"{name_or_symbol} → No mapping found")
                trading_symbol = mapping.get("trading_symbol")
                token = mapping.get("token")

            elif mode == "symbol":
                logger.info("Using symbol directly: %s", name_or_symbol)
                trading_symbol = name_or_symbol
                token = self.resolver.get_token(trading_symbol) if hasattr(self.resolver, "get_token") else None

            else:
                logger.error(" Invalid mode: %s", mode)
                raise ValueError("Invalid mode: must be 'name' or 'symbol'")

            if not trading_symbol:
                logger.error(" Unable to resolve trading symbol for %s", name_or_symbol)
                raise ValueError(f"{name_or_symbol} → Unable to resolve trading symbol")

            # --- Historical data ---
            logger.info(" Fetching historical data for %s", trading_symbol)
            df = self.broker.get_historical_data(trading_symbol, token, interval=DEFAULT_INTERVAL, days=350)

            if df is None or df.empty:
                logger.error(" No historical data available for %s", trading_symbol)
                raise ValueError(f"No historical data available for {trading_symbol}")

            # --- Resolve strategy class ---
            if isinstance(strategy_cls, str):
                strategy_cls = self.strategy_map.get(strategy_cls.lower())
                if not strategy_cls:
                    raise ValueError(f"Unknown strategy '{strategy_cls}'")

            logger.info(" Running strategy: %s", getattr(strategy_cls, "__name__", str(strategy_cls)))
            strategy = strategy_cls(df, buy_price=entry_price, qty=qty, symbol=trading_symbol)

            # --- Run analysis ---
            report = strategy.analyze()
            logger.info(" Strategy analysis complete for %s", trading_symbol)

            return report, strategy

        except Exception as e:
            logger.exception(" Error in prepare_trade_plan: %s", str(e))
            raise

    # --------------------------
    # Prepare Trade Plan (Text Output)
    # --------------------------
    def prepare_trade_plan_text(self, name_or_symbol, mode, entry_price, qty, strategy_cls=LongTermStrategy):
        logger.info(" Preparing text trade plan report")

        report, strategy = self.prepare_trade_plan(name_or_symbol, mode, entry_price, qty, strategy_cls)
        text_report = strategy.format_report(report)

        logger.info(" Report formatted successfully for %s", report.get("symbol"))
        return text_report
