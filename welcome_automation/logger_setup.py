"""لاگ کامل هر اجرا: یک فایل جدا در logs/ + نمایش در کنسول."""
import logging
from datetime import datetime

from . import config


def setup_logging() -> str:
    config.LOGS_DIR.mkdir(exist_ok=True)
    path = config.LOGS_DIR / f"run_{datetime.now():%Y%m%d_%H%M%S}.log"
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(sh)
    # لاگ‌های پرحجم کتابخانه‌ها را ساکت کن
    for noisy in ("httpx", "httpx2", "anthropic", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return str(path.relative_to(config.ROOT))
