import logging
import os
import sys
import shutil
from datetime import datetime, timedelta

from config.TradeFriendSettings import LOG_DIR

# ---------------------------------------------------------------------
# Ensure base log directory exists
# ---------------------------------------------------------------------
os.makedirs(LOG_DIR, exist_ok=True)

# ---------------------------------------------------------------------
# Safe text sanitizer
# ---------------------------------------------------------------------
def sanitize_for_log(text: str) -> str:
    """Remove or replace characters not supported by console encoding."""
    if not isinstance(text, str):
        return str(text)
    try:
        return text.encode(
            sys.stdout.encoding or "utf-8", errors="replace"
        ).decode("utf-8")
    except Exception:
        return text.encode("ascii", errors="ignore").decode("ascii")


# ---------------------------------------------------------------------
# Cleanup old log folders
# ---------------------------------------------------------------------
def cleanup_old_logs(days: int = 14):
    """
    Delete log folders older than X days.
    Folder format must be YYYY-MM-DD
    """
    cutoff = datetime.now() - timedelta(days=days)

    for folder in os.listdir(LOG_DIR):
        folder_path = os.path.join(LOG_DIR, folder)

        if not os.path.isdir(folder_path):
            continue

        try:
            folder_date = datetime.strptime(folder, "%Y-%m-%d")
            if folder_date < cutoff:
                shutil.rmtree(folder_path)
        except Exception:
            # Ignore non-date folders
            pass


# ---------------------------------------------------------------------
# Get today's log directory
# ---------------------------------------------------------------------
def get_today_log_dir():
    today = datetime.now().strftime("%Y-%m-%d")
    daily_path = os.path.join(LOG_DIR, today)

    os.makedirs(daily_path, exist_ok=True)

    # Cleanup old folders
    cleanup_old_logs(days=14)

    return daily_path


# ---------------------------------------------------------------------
# Base logger builder
# ---------------------------------------------------------------------
def _build_file_handler(file_path: str, level=logging.INFO):
    handler = logging.FileHandler(
        file_path,
        encoding="utf-8",
        delay=True
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(
          "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    ))
    return handler


# ---------------------------------------------------------------------
# Main logger (APP LOG) - Console + File
# ---------------------------------------------------------------------
def get_logger(name=__name__):
    """
    Main application logger:
    - Daily folder logs
    - Console output
    - UTF-8 safe
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:

        log_dir = get_today_log_dir()
        log_file = os.path.join(log_dir, "app.log")

        # File handler
        fh = _build_file_handler(log_file, logging.INFO)

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        ))

        if hasattr(ch.stream, "reconfigure"):
            try:
                ch.stream.reconfigure(encoding="utf-8")
            except Exception:
                pass

        logger.addHandler(fh)
        logger.addHandler(ch)

        logger.propagate = False

        # Sanitize log text
        _wrap_logger_methods(logger)

    return logger


# ---------------------------------------------------------------------
# Order logger (FILE ONLY - DEBUG LEVEL)
# ---------------------------------------------------------------------
def get_order_logger():
    """
    Dedicated logger for order placement.
    - File only
    - DEBUG level
    """
    logger = logging.getLogger("orders")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:

        log_dir = get_today_log_dir()
        log_file = os.path.join(log_dir, "orders.log")

        fh = _build_file_handler(log_file, logging.DEBUG)

        logger.addHandler(fh)
        logger.propagate = False

        _wrap_logger_methods(logger)

    return logger


def get_brokerorder_logger():
    """
    Dedicated logger for order placement.
    - File only
    - DEBUG level
    """
    logger = logging.getLogger("broker_orders")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:

        log_dir = get_today_log_dir()
        log_file = os.path.join(log_dir, "brokerorders.log")

        fh = _build_file_handler(log_file, logging.DEBUG)

        logger.addHandler(fh)
        logger.propagate = False

        _wrap_logger_methods(logger)

    return logger


# ---------------------------------------------------------------------
# Monitor logger (FILE ONLY)
# ---------------------------------------------------------------------
def get_monitor_logger():
    """
    Dedicated logger for swing monitor.
    - File only
    - INFO level
    """
    logger = logging.getLogger("monitor")
    logger.setLevel(logging.INFO)

    if not logger.handlers:

        log_dir = get_today_log_dir()
        log_file = os.path.join(log_dir, "monitor.log")

        fh = _build_file_handler(log_file, logging.INFO)

        logger.addHandler(fh)
        logger.propagate = False

        _wrap_logger_methods(logger)

    return logger

# ---------------------------------------------------------------------
# Decision Runner logger (FILE ONLY - INFO LEVEL)
# ---------------------------------------------------------------------
def get_decision_runner_logger():
    """
    Dedicated logger for decision runner.
    - File only
    - INFO level
    """
    logger = logging.getLogger("decision_runner")
    logger.setLevel(logging.INFO)

    if not logger.handlers:

        log_dir = get_today_log_dir()
        log_file = os.path.join(log_dir, "decision_runner.log")

        fh = _build_file_handler(log_file, logging.INFO)

        logger.addHandler(fh)
        logger.propagate = False

        _wrap_logger_methods(logger)

    return logger


# ---------------------------------------------------------------------
# Daily Scan logger (FILE ONLY - INFO LEVEL)
# ---------------------------------------------------------------------
def get_daily_scan_logger():
    """
    Dedicated logger for daily scan process.
    - File only
    - INFO level
    """
    logger = logging.getLogger("daily_scan")
    logger.setLevel(logging.INFO)

    if not logger.handlers:

        log_dir = get_today_log_dir()
        log_file = os.path.join(log_dir, "daily_scan.log")

        fh = _build_file_handler(log_file, logging.INFO)

        logger.addHandler(fh)
        logger.propagate = False

        _wrap_logger_methods(logger)

    return logger

# ---------------------------------------------------------------------
# Wrap logger methods for sanitization
# ---------------------------------------------------------------------
def _wrap_logger_methods(logger):
    _info = logger.info
    _warning = logger.warning
    _error = logger.error
    _exception = logger.exception
    _debug = logger.debug

    logger.info = lambda msg, *a, **kw: _info(
        sanitize_for_log(str(msg)), *a, **kw
    )
    logger.warning = lambda msg, *a, **kw: _warning(
        sanitize_for_log(str(msg)), *a, **kw
    )
    logger.error = lambda msg, *a, **kw: _error(
        sanitize_for_log(str(msg)), *a, **kw
    )
    logger.exception = lambda msg, *a, **kw: _exception(
        sanitize_for_log(str(msg)), *a, **kw
    )
    logger.debug = lambda msg, *a, **kw: _debug(
        sanitize_for_log(str(msg)), *a, **kw
    )
