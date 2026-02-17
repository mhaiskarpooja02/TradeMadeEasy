# core/trade_manager.py
"""
TradeManager
------------
- Automatic broker initialization (Dhan, Angel, Motilal) — safe if any fail to init.
- Sync holdings from all brokers (merges into holdings.json).
- Update instruments in SQLite DB (Dhan_instruments.db).
- Monitor instruments during market hours (uses Angel getltp for price checks).
- Control flags via control/control.json (daily_refresh_enabled, force_refresh, last_refresh_date).
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from utils.logger import get_logger
from utils.symbol_resolver import SymbolResolver
from db.dhan_db_helper import DhanDBHelper   # ✅ NEW import

logger = get_logger(__name__)

# Try imports — if they fail, we keep them None and handle gracefully
try:
    from brokers.dhan_client import DhanClient
except Exception as e:
    DhanClient = None
    logger.debug(f"DhanClient import failed: {e}")

try:
    from brokers.angel_client import AngelClient, getltp
except Exception as e:
    AngelClient = None
    getltp = None
    logger.debug(f"AngelClient/getltp import failed: {e}")

try:
    from brokers.motilal_client import MotilalClient
except Exception as e:
    MotilalClient = None
    logger.debug(f"MotilalClient import failed: {e}")


class TradeManager:
    TARGET1_PCT = 0.05   # +5%
    TARGET2_PCT = 0.10   # +10%
    CONTROL_FILE = os.path.join("control", "control.json")
    HOLDINGS_FILE = os.path.join("data", "holdings.json")

    def __init__(self):
        # Initialize DB
        self.db = DhanDBHelper()

        # Initialize available brokers (best-effort)
        self.brokers = self._init_brokers()
        logger.info(f"Initialized brokers: {[type(b).__name__ for b in self.brokers]}")

        # Holdings (still JSON for logging)
        self.holdings: List[Dict[str, Any]] = []
        self.resolver = SymbolResolver()

    # -------------------- Broker init --------------------
    def _init_brokers(self) -> List[Any]:
        brokers = []
        if DhanClient is not None:
            try:
                brokers.append(DhanClient())
            except Exception as e:
                logger.warning(f"Failed to init DhanClient: {e}")
        if AngelClient is not None:
            try:
                brokers.append(AngelClient())
            except Exception as e:
                logger.warning(f"Failed to init AngelClient: {e}")
        if MotilalClient is not None:
            try:
                brokers.append(MotilalClient())
            except Exception as e:
                logger.warning(f"Failed to init MotilalClient: {e}")
        return brokers

    # -------------------- JSON helpers --------------------
    def load_json(self, file_path: str) -> Any:
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Failed to load JSON {file_path}: {e}", exc_info=True)
            return []

    def save_json(self, data: Any, file_path: str) -> None:
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save JSON {file_path}: {e}", exc_info=True)

    # -------------------- Control file helpers --------------------
    def load_control(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.CONTROL_FILE):
                with open(self.CONTROL_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            return {}
        except Exception as e:
            logger.error(f"Failed to load control.json: {e}", exc_info=True)
            return {}

    def save_control(self, data: Dict[str, Any]) -> None:
        try:
            os.makedirs(os.path.dirname(self.CONTROL_FILE), exist_ok=True)
            tmp = self.CONTROL_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            os.replace(tmp, self.CONTROL_FILE)
        except Exception as e:
            logger.error(f"Failed to save control.json: {e}", exc_info=True)

    # -------------------- Daily refresh --------------------
    def daily_refresh(self, force: bool = False) -> None:
        logger.info("Daily refresh is getting called")
        control = self.load_control()
        daily_enabled = control.get("daily_refresh_enabled", True)
        force_refresh = control.get("force_refresh", False)

        if not daily_enabled and not force_refresh and not force:
            logger.info("Daily refresh disabled. Skipping.")
            return

        now = datetime.now()
        if not (force or force_refresh) and (now.hour < 15 or (now.hour == 15 and now.minute < 30)):
            logger.info("Market still open. Skipping daily refresh.")
            return

        logger.info("Running daily refresh after market close...")

        total_changes = self.sync_holdings_with_all_brokers()

        # Update control flags
        control["last_refresh_date"] = now.strftime("%Y-%m-%d")
        control["force_refresh"] = False
        self.save_control(control)

        logger.info(f"Daily refresh done. Total holding changes: {total_changes}")

    # -------------------- Sync holdings --------------------
    def sync_holdings_with_all_brokers(self) -> int:
        logger.info("Syncing holdings from all brokers...")
        total_changes = 0

        for broker in self.brokers:
            broker_name = type(broker).__name__
            logger.info(f"Processing broker: {broker_name}")

            if broker_name == "DhanClient":
                try:
                    self.refresh_holdings(broker)
                    logger.info(f"Dhan holdings refreshed: {len(self.holdings)} items")
                except Exception as e:
                    logger.exception(f"Failed to refresh Dhan holdings: {e}")
                    continue

                if self.holdings:
                    try:
                        changes = self.update_instruments(self.holdings)
                        total_changes += changes
                        logger.info(f"Dhan instruments updated: {changes} changes applied")
                    except Exception as e:
                        logger.exception(f"Failed to update instruments for Dhan: {e}")

            elif broker_name == "AngelClient":
                logger.info("AngelOne integration placeholder")

            elif broker_name == "MotilalClient":
                logger.info("Motilal integration placeholder")

        return total_changes



    def refresh_holdings(self, broker) -> int:
        logger.info(f"Refreshing holdings from broker: {type(broker).__name__}")
        try:
            api_holdings = broker.get_holdings() or []
        except Exception as e:
            logger.error(f"Failed to fetch holdings from broker: {e}", exc_info=True)
            return 0

        logger.info(f"Sample holdings: {api_holdings}")

        self.holdings = api_holdings
        self.save_json(self.holdings, self.HOLDINGS_FILE)
        logger.info(f"Holdings refreshed: {len(api_holdings)} records loaded.")
        return len(api_holdings)

    # -------------------- Instruments update (DB) --------------------
    def update_instruments(self, new_holdings: List[Dict[str, Any]]) -> int:
       if not new_holdings:
           logger.info("No holdings provided for instruments update.")
           return 0

       buffer_pct = 0.02
       added_count, updated_count, removed_count = 0, 0, 0

       existing_instruments = {i["symbol"]: i for i in self.db.get_all()}

       # Collect all symbols from new holdings
       new_symbols = set()

       for h in new_holdings:

           if not isinstance(h, dict):
               logger.warning(f"Unexpected holding type: {type(h)} → {h}")
               continue

           symbol = h.get("tradingSymbol") or h.get("symbol") or ""
           if not symbol:
               continue

           new_symbols.add(symbol)

           qty = int(h.get("totalQty") or h.get("dpQty") or h.get("quantity") or 0)
           avg_price = float(h.get("avgCostPrice") or h.get("avg_price") or 0.0)

           # --- Get LTP safely ---
           ltp = None
           try:
               resolved = self.resolver.resolve_symbol(symbol)
               if resolved:
                   ltp = getltp(resolved)
           except Exception as e:
               logger.warning(f"Failed to fetch LTP for {symbol}: {e}")
               ltp = None

           base_price = ltp or avg_price
           existing = existing_instruments.get(symbol, {})

           t1 = existing.get("target1") or round(base_price * (1 + self.TARGET1_PCT), 2)
           t2 = existing.get("target2") or round(base_price * (1 + self.TARGET2_PCT), 2)
           broker = existing.get("broker") or "DHAN"
           sell_qty1 = qty // 2
           sell_qty2 = qty - sell_qty1

           # --- Determine if monitoring is active ---
           monitor_active = True
           if ltp is not None:
               if ltp < avg_price:
                   monitor_active = False
               elif ltp >= t2 * (1 + buffer_pct):
                   monitor_active = False

           data = {
               "symbol": symbol,
               "broker": broker,
               "quantity": qty,
               "avg_price": avg_price,
               "ltp": ltp,
               "target1": t1,
               "target2": t2,
               "sell_qty_target1": sell_qty1,
               "sell_qty_target2": sell_qty2,
               "mode": "Manual",
               "active_target1": 1 if monitor_active else 0,
               "active_target2": 1 if monitor_active else 0,
           }

           # --- Log & Insert/Update ---
           current_db_record = self.db.get_by_symbol(symbol)
           if current_db_record:
               logger.info(f"Updating instrument: {symbol}")
               updated_count += 1
           else:
               logger.info(f"Inserting new instrument: {symbol}")
               added_count += 1

           self.db.insert_or_update(data)

       # ---------------------- REMOVE MISSING HOLDINGS ----------------------
       existing_symbols = set(existing_instruments.keys())
       symbols_to_remove = existing_symbols - new_symbols

       for sym in symbols_to_remove:
           logger.info(f"Removing instrument not in new holdings: {sym}")
           try:
               self.db.delete_by_symbol(sym)
               removed_count += 1
           except Exception as e:
               logger.error(f"Failed to remove {sym}: {e}")

       # --------------------------------------------------------------------
       logger.info(
           f"Instruments update completed → "
           f"{added_count} added, {updated_count} updated, {removed_count} removed"
       )

       return added_count + updated_count


    # -------------------- Monitoring --------------------
    def monitor_targets(self) -> None:
        logger.info("monitor_targets triggered")
        instruments = self.db.get_all()
        if not instruments:
            logger.warning("No instruments to monitor.")
            return

        if getltp is None:
            logger.warning("getltp() is not available. Monitoring skipped.")
            return

        for instrument in instruments:
            try:
                symbol = instrument.get("symbol")
                avg_price = float(instrument.get("avg_price", 0))
                if not symbol:
                    continue

                resolved = self.resolver.resolve_symbol(symbol)
                if not resolved:
                    continue

                ltp = None
                try:
                    ltp = getltp(resolved)
                except Exception:
                    pass

                if ltp is None:
                    ltp = instrument.get("ltp") or avg_price

                # Always update latest LTP in DB
                instrument["ltp"] = ltp

                if not ltp:
                    continue

                # Target1
                if instrument.get("target1") and instrument.get("sell_qty_target1", 0) > 0:
                    if ltp >= instrument["target1"]:
                        qty = instrument["sell_qty_target1"]
                        broker_name = instrument.get("broker", "DHAN")
                        security_id = instrument.get("securityId")
                        if security_id and self._attempt_place_order(security_id, qty, preferred_broker=broker_name):
                            instrument["sell_qty_target1"] = 0
                            self.db.insert_or_update(instrument)
                            logger.info(f"{symbol} hit Target1 {instrument['target1']} (LTP={ltp})")

                # Target2
                if instrument.get("target2") and instrument.get("sell_qty_target2", 0) > 0:
                    if ltp >= instrument["target2"]:
                        qty = instrument["sell_qty_target2"]
                        broker_name = instrument.get("broker", "DHAN")
                        security_id = instrument.get("securityId")
                        if security_id and self._attempt_place_order(security_id, qty, preferred_broker=broker_name):
                            instrument["sell_qty_target2"] = 0
                            self.db.insert_or_update(instrument)
                            logger.info(f"{symbol} hit Target2 {instrument['target2']} (LTP={ltp})")

            except Exception as e:
                logger.error(f"Error monitoring {instrument}: {e}", exc_info=True)

    # -------------------- Place order attempt --------------------
    def _attempt_place_order(self, security_id: str, qty: int, preferred_broker: str = None) -> bool:
        brokers_to_try = self.brokers

        # Filter preferred broker if given
        if preferred_broker:
            brokers_to_try = [
                b for b in self.brokers 
                if type(b).__name__.upper().startswith(preferred_broker.upper())
            ]
            if not brokers_to_try:
                logger.warning(f"Preferred broker {preferred_broker} not initialized, falling back to all brokers.")
                brokers_to_try = self.brokers

        for broker in brokers_to_try:
            broker_name = type(broker).__name__
            try:
                if not hasattr(broker, "place_order"):
                    logger.warning(f"{broker_name} has no place_order method, skipping.")
                    continue

                # Call Dhan wrapper: only security_id + qty
                success = broker.place_order(security_id=security_id, qty=qty)

                if success:
                    logger.info(f"Order placed via {broker_name} for {security_id} qty={qty}")
                    return True
                else:
                    logger.warning(f"{broker_name} failed to place order for {security_id} qty={qty}")

            except Exception as e:
                logger.exception(f"Error placing order with {broker_name}: {e}")

        logger.warning(f"Failed to place order for {security_id} qty={qty} on all brokers.")
        return False
