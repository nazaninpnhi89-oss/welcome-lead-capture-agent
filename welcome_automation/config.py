"""تنظیمات مرکزی: مسیرها، مدل، و خواندن .env بدون وابستگی اضافه."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """خواندن ساده‌ی فایل .env (KEY=VALUE). متغیرهای موجود در محیط را بازنویسی نمی‌کند."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))

# موتور تحلیل: claude | ollama | mock
PROVIDER = os.environ.get("LLM_PROVIDER", "claude")
# Ollama محلی (رایگان): http://localhost:11434 — Ollama Cloud: https://ollama.com
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")

# اینستاگرام (Instagram API with Instagram Login) — بدون نیاز به صفحه‌ی فیسبوک
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")  # توکن پیج از پنل Meta
IG_APP_SECRET = os.environ.get("IG_APP_SECRET", "")      # برای بررسی امضای webhook
IG_VERIFY_TOKEN = os.environ.get("IG_VERIFY_TOKEN", "")  # رمز دلخواه شما برای تأیید webhook
IG_API_VERSION = os.environ.get("IG_API_VERSION", "v23.0")
WEBHOOK_PORT = int(os.environ.get("WEBHOOK_PORT", "8000"))

# همه‌ی مسیرها با env قابل تغییرند (مثلاً برای نسخه‌ی انگلیسی دمو)؛ مسیر نسبی = نسبت به پوشه‌ی پروژه
def _path(var: str, default: str) -> Path:
    p = Path(os.environ.get(var, default))
    return p if p.is_absolute() else ROOT / p


INPUT_FILE = _path("INPUT_FILE", "new_contacts.json")
TEMPLATE_FILE = _path("TEMPLATE_FILE", "template.md")
DB_FILE = _path("DB_FILE", "leads.db")
ALERTS_FILE = _path("ALERTS_FILE", "alerts.log")
LOGS_DIR = ROOT / "logs"
OUTBOX_DIR = _path("OUTBOX_DIR", "outbox")

INTENTS = ("buying", "question", "other")
