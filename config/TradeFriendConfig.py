# ---------------- CAPITAL & RISK ----------------
SWING_CAPITAL = 10000
RISK_PERCENT = 1.0
ENTRY_TOLERANCE = 0.01   # 1%
SL_BUFFER_PCT = 0.0015   # 0.15% safety buffer
# ---------------- API / BROKER ----------------
REQUEST_DELAY_SEC = 1.2
ERROR_COOLDOWN_SEC = 5
SEARCH_DELAY = 0.35
HISTORY_DELAY = 0.50
RETRY_DELAY = 1.5
MAX_RETRIES = 3

# ---------------- MODE ----------------
PAPER_TRADE = True

# ---------------- SWING RULES ----------------
MAX_OPEN_TRADES = 5
SWING_PLAN_EXPIRY_DAYS = 7
MAX_CAPITAL_UTILIZATION = 0.60

# ---------------- TRAILING SL ----------------
ALLOW_TRAILING_SL = True
TRAIL_START_R = 1.0
TRAIL_ATR_MULTIPLE = 1.5

# ---------------- PARTIAL BOOKING ----------------
ENABLE_PARTIAL_BOOKING = True
PARTIAL_BOOK_RR = 1.0
PARTIAL_BOOK_PERCENT = 0.5
HARD_EXIT_R_MULTIPLE = 2.0
MIN_SCAN_CONFIDENCE = 5
# ---------------- SAFETY ----------------
DISABLE_NEW_TRADES = False
SL_ON_CLOSE = True

# Partial entry support
PARTIAL_ENTRY_ENABLED = True

# Qty to place on first partial entry
PARTIAL_ENTRY_QTY = 1

MORNING_CONFIRM_TIMES = [
    (9, 16),
    (9, 21),
    (9, 26),
    (9, 31),
]