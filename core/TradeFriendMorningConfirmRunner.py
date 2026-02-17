# core/TradeFriendMorningConfirmRunner.py

from datetime import datetime
import json
import os

from config.TradeFriendConfig import MORNING_CONFIRM_TIMES
from utils.logger import get_logger

logger = get_logger(__name__)

STATE_FILE = "control/tradefriend_run_state.json"


class TradeFriendMorningConfirmRunner:
    """
    PHASE-1.5 : Morning Validation
    --------------------------------
    - Confirms READY trades
    - Slot based (time gated)
    - Day + slot protected (JSON state)
    - NO LTP
    - NO execution
    """

    def __init__(self, trade_repo):
        self.trade_repo = trade_repo

    # ==================================================
    # STATE
    # ==================================================

    def _load_state(self):
        if not os.path.exists(STATE_FILE):
            return {
                "morning_confirm": {
                    "last_run_date": None,
                    "last_run_slot": None
                }
            }

        with open(STATE_FILE, "r") as f:
            return json.load(f)

    def _save_state(self, state):
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    # ==================================================
    # MAIN RUN
    # ==================================================

    def run(self):
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_slot = (now.hour, now.minute)

        if current_slot not in MORNING_CONFIRM_TIMES:
            return  # ⛔ Outside allowed window

        state = self._load_state()
        mc_state = state.get("morning_confirm", {})

        if (
            mc_state.get("last_run_date") == today
            and mc_state.get("last_run_slot") == current_slot
        ):
            return  # ⛔ Already executed for this slot today

        logger.info(f"🌅 Morning Confirm started @ {current_slot}")

        self._process_ready_trades()

        # ✅ Mark slot as executed
        state["morning_confirm"] = {
            "last_run_date": today,
            "last_run_slot": current_slot
        }
        self._save_state(state)

    # ==================================================
    # PROCESS
    # ==================================================

    def _process_ready_trades(self):
        ready_trades = self.trade_repo.fetch_ready_trades()

        for trade in ready_trades:
            self._confirm_trade(trade)

    def _confirm_trade(self, trade):
        """
        VALIDATION ONLY
        """
        if trade["confidence"] < 5:
            self.trade_repo.invalidate_trade(
                trade["id"],
                "Morning confirm failed: low confidence"
            )
            return

        # ✅ Promote trade state
        self.trade_repo.mark_confirmed(trade["id"])

        logger.info(f"✅ Morning confirmed | {trade['symbol']}")
