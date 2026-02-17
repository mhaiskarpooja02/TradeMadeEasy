# rangebound_finder.py

import os
from typing import Tuple, List
from utils.logger import get_logger
from brokers.angel_client import AngelClient
from utils.symbol_resolver import SymbolResolver
from db.dhan_db_helper import DhanDBHelper
from core.TradeFriendRangeboundService import RangeboundService
from utils.file_handler import load_symbols_from_csv
import time

logger = get_logger(__name__)


def run_rangebound_finder(input_folder: str, output_folder: str) -> Tuple[bool, List[str]]:
    if not os.path.exists(input_folder):
        logger.error(f"Input folder not found: {input_folder}")
        return False, []

    try:
        symbols = load_symbols_from_csv(input_folder)
        if not symbols:
            logger.warning("No symbols found.")
            return True, []
        logger.info(f"Rangebound finder: {len(symbols)} symbols loaded")
    except Exception as e:
        logger.error(f"CSV load failed: {e}")
        return False, []

    db = DhanDBHelper()
    service = RangeboundService()
    resolver = SymbolResolver()
    broker = AngelClient()
    
    if getattr(broker, "smart_api", None) is None:
        logger.error("Broker login failed.")
        return False, []

    results = []
    rejections = []

    for name in symbols:
        try:
            mapping = resolver.resolve_symbol_tradefinder(name)
            if not mapping:
                rejections.append(f"{name} → No mapping")
                continue

            trading_symbol = mapping["trading_symbol"]
            token = mapping["token"]

            logger.info(f"Processing {trading_symbol} and token {token}...")

          
            df = broker.get_RangeBoundhistorical_data(trading_symbol, token)
            if df is None or df.empty:
                rejections.append(f"{trading_symbol} → No historical data")
                continue

            # Evaluate pure DB metrics
            record = service.evaluate_for_db(df, trading_symbol)
            if not record:
                rejections.append(f"{trading_symbol} → Not Rangebound")
                continue

            # Current LTP
            ltp = float(df["close"].iloc[-1])

            # Calculate dynamic signal (BUY/STRONG BUY/EXIT/WAIT)
            signal = service.calculate_signal(ltp, record, df)

            # Insert only pure metrics into DB
            db.upsert(record)

            results.append(f"{trading_symbol}: {signal}")

        except Exception as e:
            rejections.append(f"{name} → Error {e}")

    if rejections:
        logger.warning(f"Some symbols were rejected: {len(rejections)}")
        for r in rejections:
            logger.warning(r)

    return True, results
