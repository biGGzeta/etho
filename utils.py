# utils.py
import logging
import json
import sys
from datetime import datetime, timezone
from typing import Optional

try:
    import requests  # for Telegram (optional)
except Exception:
    requests = None

# Defaults if config doesn't define them
try:
    from config import LOG_JSON, LOG_LEVEL, TELEGRAM_ENABLED, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
except Exception:
    LOG_JSON = False
    LOG_LEVEL = "INFO"
    TELEGRAM_ENABLED = False
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT_ID = ""

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Include any extra dict-like attributes (avoid built-ins)
        for key, val in record.__dict__.items():
            if key in ("msg", "args", "levelname", "levelno", "pathname", "filename",
                       "module", "exc_info", "exc_text", "stack_info", "lineno",
                       "funcName", "created", "msecs", "relativeCreated",
                       "thread", "threadName", "processName", "process"):
                continue
            try:
                json.dumps({key: val})
                payload[key] = val
            except TypeError:
                payload[key] = str(val)
        return json.dumps(payload, ensure_ascii=False)

def get_logger(name: Optional[str] = None) -> logging.Logger:
    logger_name = name or "eth_grid_bot"
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger  # already configured

    level = getattr(logging, (LOG_LEVEL or "INFO").upper(), logging.INFO)
    logger.setLevel(level)

    handler = logging.StreamHandler(stream=sys.stdout)
    if LOG_JSON:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger

def iso_ts() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

def send_telegram(text: str, silent: bool = False) -> bool:
    """Send a Telegram message if TELEGRAM_ENABLED is True and tokens are set.
    Returns True if sent, False otherwise.
    """
    if not TELEGRAM_ENABLED:
        return False
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    if requests is None:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": str(TELEGRAM_CHAT_ID),
            "text": text,
            "disable_notification": bool(silent),
        }
        r = requests.post(url, data=payload, timeout=10)
        return r.ok
    except Exception:
        return False
