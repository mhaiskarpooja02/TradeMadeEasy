import os, datetime
from typing import Tuple, List
from utils.indicators import IndicatorEngine
from utils.file_handler import save_pdf, save_text, load_symbols_from_csv
from utils.logger import get_logger, sanitize_for_log
from db.missing_token_db import MissingTokenDB
from brokers.angel_client import AngelClient
from utils.sendemail import send_email_with_attachments
from utils.symbol_resolver import SymbolResolver



from db.tradefindinstrument_db import TradeFindDB
from config.TradeFriendSettings import (
    OUTPUT_FOLDER,
    EMAIL_SUBJECT_TEMPLATE, EMAIL_BODY_TEMPLATE,
    SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAILS,EMAIL_Enabled
)

logger = get_logger(__name__)

def _derive_trade_date_from_input_folder(input_folder: str) -> str:
    base = os.path.basename(os.path.normpath(input_folder))
    try:
        if base.isdigit() and len(base) == 8:
            return datetime.datetime.strptime(base, "%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        pass
    return datetime.datetime.now().strftime("%Y-%m-%d")

def run_trade_finder(input_folder: str, output_base_folder: str) -> Tuple[bool, List[str]]:
    if not os.path.exists(input_folder) or not os.path.isdir(input_folder):
        logger.error(f"Input folder not found: {input_folder}")
        return False, []

    try:
        names = load_symbols_from_csv(input_folder)
        if not names:
            logger.warning(f"No symbols found in {input_folder}")
            return True, []
        logger.info(f"Found {len(names)} symbols in {input_folder}")
    except Exception as e:
        logger.error(f"Error loading symbols: {e}")
        return False, []

    broker = AngelClient()
    if getattr(broker, "smart_api", None) is None:
        logger.error("Broker login failed.")
        return False, []

    resolver = SymbolResolver()
    ema_signals, bb_signals, rejections = [], [], []

    for name in names:
        try:
            mapping = resolver.resolve_symbol_tradefinder(name)
            if not mapping:
                rejections.append(f"{name} → No mapping found")
                continue
            trading_symbol, token = mapping.get("trading_symbol"), mapping.get("token")
            if not token:
                rejections.append(f"{trading_symbol} → No token")
                continue

            df = broker.get_historical_data(trading_symbol, token)
            if df is None or df.empty:
                rejections.append(f"{trading_symbol} → No historical data")
                continue

            required_cols = {"close", "high", "low", "open", "volume"}
            missing = required_cols - set(df.columns)
            if missing:
                rejections.append(f"{trading_symbol} → Missing columns {missing}")
                continue

            engine = IndicatorEngine(df, trading_symbol)

            # ----- EMA Crossover First -----
            signal = engine.check_ema_crossover()
            if signal.get("reason"):
                # EMA failed → Try Bollinger Band
                bb_signal = engine.bollinger_momentum()
                if bb_signal.get("signal") != "No Bollinger Signal":
                    bb_signals.append(bb_signal)
                    logger.info(sanitize_for_log(
                        f"BB Signal: {trading_symbol} → {bb_signal.get('signal')} at {bb_signal.get('close')}"
                    ))
                else:
                    rejections.append(f"{trading_symbol} → EMA & BB conditions not met")
            else:
                ema_signals.append(signal)
                logger.info(sanitize_for_log(
                    f"EMA Signal: {trading_symbol} BUY at {signal.get('entry')}"
                ))

        except Exception as e:
            logger.exception(f"Error processing {name}: {e}")
            rejections.append(f"{name} → Error {e}")

    trade_date = _derive_trade_date_from_input_folder(input_folder)
    dated_output = os.path.join(output_base_folder, trade_date)
    os.makedirs(dated_output, exist_ok=True)

    result_files = []

    # ===== Save EMA Signals =====
    if ema_signals:
        try:
            ema_file = os.path.join(dated_output, "signals_ema.pdf")
            report = engine.format_signals_daily(ema_signals, trade_date)
            #save_text(ema_file, report)
            # Save the report in PDF format (mobile friendly)
            save_pdf(ema_file, report, title=f"EMA Signals Report – {trade_date}")
            logger.info(f"EMA Signals saved to {ema_file}")
            result_files.append(ema_file)
        except Exception as e:
            logger.exception(f"Failed to save EMA signals: {e}")

    # ===== Save BB Signals =====
    if bb_signals:
        try:
            bb_file = os.path.join(dated_output, "signals_bb.pdf")
            report = engine.format_signals_bb_daily(bb_signals, trade_date)
            #save_text(bb_file, report)
            save_pdf(bb_file, report, title=f"Bollinger Band Signals Report – {trade_date}")
            logger.info(f"BB Signals saved to {bb_file}")
            result_files.append(bb_file)
        except Exception as e:
            logger.exception(f"Failed to save BB signals: {e}")

    # ===== Send Consolidated Email =====
    if result_files:
        try:
            subject = EMAIL_SUBJECT_TEMPLATE.format(date=trade_date)
            body = EMAIL_BODY_TEMPLATE.format(
                date=trade_date,
                signal_count=len(ema_signals) + len(bb_signals),
                symbols=", ".join(sig.get("symbol", "") for sig in (ema_signals +  bb_signals))
            )
            logger.info(f"EMAIL_Enabled  status {EMAIL_Enabled}")
            if EMAIL_Enabled:
                logger.info(f"RECEIVER_EMAILS list {RECEIVER_EMAILS}")
                logger.info(f"EMAIL_Enabled  status {EMAIL_Enabled}")
                send_email_with_attachments(
                    sender_email=SENDER_EMAIL,
                    sender_password=SENDER_PASSWORD,
                    receiver_emails=RECEIVER_EMAILS,
                    subject=subject,
                    body=body,
                    file_paths=result_files
                )
            else:
                logger.info("📧 Email sending is disabled in indicator_helper.json — skipping email dispatch.")


            logger.info(f"📧 Consolidated email sent to {RECEIVER_EMAILS} with {len(result_files)} attachments")
        except Exception as e:
            logger.exception(f"Failed to send consolidated email: {e}")
    

    # ===== Save Rejections =====
    if rejections:
        try:
            rej_file = os.path.join(dated_output, "rejections.txt")
            formatted_rejections = [f"• {r}" for r in rejections if r]
            header = f"Rejection Report — {trade_date}\nTotal: {len(formatted_rejections)} entries\n\n"
            save_text(rej_file, header + "\n".join(formatted_rejections))
            logger.info(f"Rejections saved to {rej_file}")

            db = MissingTokenDB()
            for rej in rejections:
                if "No token" in rej:
                    symbol = rej.split("→")[0].strip()
                    db.add_or_update(symbol, name=symbol, active=1)
        except Exception as e:
            logger.exception(f"Failed to save rejections: {e}")


   

    logger.info("Trade Finder Finished")
    return True, result_files



def run_existing_trade_finder(output_base_folder: str) -> Tuple[bool, List[str]]:
    """
    Runs Trade Finder on symbols stored in tradefindinstrument DB.
    No input folder required.
    """
    db = TradeFindDB()
    symbols = db.get_active()
        # ✅ Always enforce active = 1
        # symbols = [s for s in allsymbols if s.get("active", 1) == 1]

    if not symbols:
        logger.exception("No Symbols", "No symbols to process.")
        return True, []
            
    active_count = len(symbols)
    logger.info(f"Active symbols count: {active_count}")

    broker = AngelClient()
    if getattr(broker, "smart_api", None) is None:
        logger.error("Broker login failed.")
        return False, []

    resolver = SymbolResolver()
    ema_signals, bb_signals, rejections = [], [], []

    for symbol in symbols:
        name = None  # ✅ prevent UnboundLocalError
        try:
            name = symbol["symbol"]
            mapping = resolver.resolve_symbol_tradefinder(name)
            if not mapping:
                rejections.append(f"{name} → No mapping found")
                continue

            trading_symbol, token = mapping.get("trading_symbol"), mapping.get("token")
            if not token:
                rejections.append(f"{trading_symbol} → No token")
                continue

            df = broker.get_historical_data(trading_symbol, token)
            if df is None or df.empty:
                rejections.append(f"{trading_symbol} → No historical data")
                continue

            required_cols = {"close", "high", "low", "open", "volume"}
            missing = required_cols - set(df.columns)
            if missing:
                rejections.append(f"{trading_symbol} → Missing columns {missing}")
                continue

            engine = IndicatorEngine(df, trading_symbol)

            # ----- EMA Crossover First -----
            signal = engine.check_ema_crossover()
            if signal.get("reason"):
                bb_signal = engine.bollinger_momentum()
                if bb_signal.get("signal") != "No Bollinger Signal":
                    bb_signals.append(bb_signal)
                    logger.info(sanitize_for_log(
                        f"BB Signal: {trading_symbol} → {bb_signal.get('signal')} at {bb_signal.get('close')}"
                    ))
                else:
                    rejections.append(f"{trading_symbol} → EMA & BB conditions not met")
            else:
                ema_signals.append(signal)
                logger.info(sanitize_for_log(
                    f"EMA Signal: {trading_symbol} BUY at {signal.get('entry')}"
                ))

        except Exception as e:
            logger.exception(f"Error processing {name}: {e}")
            rejections.append(f"{name} → Error {e}")

    trade_date = datetime.datetime.today().strftime("%Y%m%d")  # Use current date
    dated_output = os.path.join(output_base_folder, trade_date)
    os.makedirs(dated_output, exist_ok=True)

    result_files = []

    # ===== Save EMA Signals =====
    if ema_signals:
        try:
            ema_file = os.path.join(dated_output, "signals_ema.pdf")
            report = engine.format_signals_daily(ema_signals, trade_date)
            save_pdf(ema_file, report, title=f"EMA Signals Report – {trade_date}")
            logger.info(f"EMA Signals saved to {ema_file}")
            result_files.append(ema_file)
        except Exception as e:
            logger.exception(f"Failed to save EMA signals: {e}")

    # ===== Save BB Signals =====
    if bb_signals:
        try:
            bb_file = os.path.join(dated_output, "signals_bb.pdf")
            report = engine.format_signals_bb_daily(bb_signals, trade_date)
            save_pdf(bb_file, report, title=f"Bollinger Band Signals Report – {trade_date}")
            logger.info(f"BB Signals saved to {bb_file}")
            result_files.append(bb_file)
        except Exception as e:
            logger.exception(f"Failed to save BB signals: {e}")

    # ===== Send Consolidated Email =====
    if result_files:
        try:
            subject = EMAIL_SUBJECT_TEMPLATE.format(date=trade_date)
            body = EMAIL_BODY_TEMPLATE.format(
                date=trade_date,
                signal_count=len(ema_signals) + len(bb_signals),
                symbols=", ".join(sig.get("symbol", "") for sig in (ema_signals + bb_signals))
            )
            if EMAIL_Enabled:
                send_email_with_attachments(
                    sender_email=SENDER_EMAIL,
                    sender_password=SENDER_PASSWORD,
                    receiver_emails=RECEIVER_EMAILS,
                    subject=subject,
                    body=body,
                    file_paths=result_files
                )
                logger.info(f"📧 Email sent to {RECEIVER_EMAILS} with {len(result_files)} attachments")
            else:
                logger.info("📧 Email sending disabled — skipping dispatch")
        except Exception as e:
            logger.exception(f"Failed to send consolidated email: {e}")

    # ===== Save Rejections =====
    if rejections:
        try:
            rej_file = os.path.join(dated_output, "rejections.txt")
            formatted_rejections = [f"• {r}" for r in rejections if r]
            header = f"Rejection Report — {trade_date}\nTotal: {len(formatted_rejections)} entries\n\n"
            save_text(rej_file, header + "\n".join(formatted_rejections))
            logger.info(f"Rejections saved to {rej_file}")

            db_missing = MissingTokenDB()
            for rej in rejections:
                if "No token" in rej:
                    symbol = rej.split("→")[0].strip()
                    db_missing.add_or_update(symbol, name=symbol, active=1)
        except Exception as e:
            logger.exception(f"Failed to save rejections: {e}")

    logger.info("Existing Trade Finder Finished")
    return True, result_files
