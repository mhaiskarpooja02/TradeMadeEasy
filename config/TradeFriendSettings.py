import os
import json

# Base directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
MASTERDATA_DIR = os.path.join(BASE_DIR, "Masterdata")  # <-- new
OUTPUT_FOLDER = os.path.join(BASE_DIR, "output")
CONTROL_FOLDER = os.path.join(BASE_DIR, "control")
RangeBoundInput_DIR= os.path.join(BASE_DIR, "RangeBoundInput")
RangeBoundOutput_DIR= os.path.join(BASE_DIR, "RangeBoundOutput")
INPUT_BASE = os.path.join(BASE_DIR, "Input")

# File paths
CREDENTIALS_FILE = os.path.join(CONFIG_DIR, "credentials.json")  # corrected
INSTRUMENTS_FILE = os.path.join(DATA_DIR, "instruments.json")
HOLDINGS_FILE = os.path.join(DATA_DIR, "holdings.json")
NSE_EQTY_FILE = os.path.join(MASTERDATA_DIR, "NSEEQTYdata.json")  # <-- new
INDICATOR_FILE = os.path.join(CONFIG_DIR, "indicator_helper.json")
CONTROL_FILE = os.path.join("control", "control.json")
TOKEN_FILE = os.path.join(CONFIG_DIR, "dhan_token.json")
SYMBOL_MASTER_FILE = os.path.join(MASTERDATA_DIR, "symbolnamemaster.json")
# Load credentials
with open(CREDENTIALS_FILE, "r") as f:
    creds = json.load(f)

dhan_creds = creds.get("dhan", {})

client_id = dhan_creds.get("client_id")
access_token = dhan_creds.get("access_token")

dhan_apikey=  dhan_creds.get("API_KEY")
dhan_appsecret=  dhan_creds.get("API_Secret")
 
angel_creds = creds.get("angel", {})

api_key = angel_creds.get("API_KEY")
username = angel_creds.get("USERNAME")
pin = angel_creds.get("PIN")
totp_qr = angel_creds.get("TOTP_QR")

# Defaults
DEFAULT_INTERVAL = "1day"
DEFAULT_LOOKBACK = 60  # days of data to fetch

# -------------------------------
# Load indicator parameters
# -------------------------------
with open(INDICATOR_FILE, "r") as f:
    indicators = json.load(f)

EMA_SHORT = indicators.get("ema_short", 9)
EMA_LONG = indicators.get("ema_long", 21)
CANDLES_ABOVE = indicators.get("candles_above", 2)
LOOKBACK_DAYS = indicators.get("lookback_days", 90)
RangeBoundLOOKBACK_DAYS = indicators.get("RangeBoundlookback_days", 365)
DEFAULT_INTERVAL = indicators.get("default_interval", "ONE_DAY")
RSI_PERIOD = indicators.get("rsi_period", 14)
RSI_OVERBOUGHT = indicators.get("rsi_overbought", 70)
RSI_OVERSOLD = indicators.get("rsi_oversold", 30)
ATR_PERIOD = indicators.get("atr_period", 14)
ATR_MULT = indicators.get("atr_mult", 1.5)
VOL_PERIOD = indicators.get("vol_period", 20)
FULL_CONFIRM_VOL_MULT = indicators.get("full_confirm_vol_mult", 1.5)

RECEIVER_EMAILS = indicators.get("email_receivers", [])

email_creds = creds.get("email_Credsettings", {})

SENDER_EMAIL = email_creds.get("sender_email", "")
SENDER_PASSWORD = email_creds.get("sender_password", "")

email_config = indicators.get("email_settings", {})
EMAIL_Enabled = email_config.get("emailenabeled", "")
RECEIVER_EMAILS = email_config.get("receiver_emails", [])
EMAIL_SUBJECT_TEMPLATE = email_config.get("subject_template", "")
EMAIL_BODY_TEMPLATE = email_config.get("body_template", "")

# Check interval in seconds (5 minutes)
CHECK_INTERVAL = 300
