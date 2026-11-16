"""سرور webhook اینستاگرام: دایرکت‌های جدید را می‌گیرد و به همان خط پردازش می‌دهد.

اجرا:
    .venv/bin/python -m welcome_automation.webhook_server
آدرس‌ها:
    GET  /webhook/instagram  ← تأیید webhook توسط Meta (hub.challenge)
    POST /webhook/instagram  ← دریافت پیام‌ها
    GET  /health             ← چک سلامت
"""
import json
import logging
import queue
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config, instagram, messenger
from .analyzer import FatalAPIError, get_analyzer
from .logger_setup import setup_logging
from .run import process_contact
from .storage import LeadStore

log = logging.getLogger("webhook")
PATH = "/webhook/instagram"
jobs: "queue.Queue[dict]" = queue.Queue()


def worker() -> None:
    """یک کارگر پشت صف: پیام‌ها یکی‌یکی پردازش می‌شوند (DB و مدل هم‌زمان درگیر نمی‌شوند)."""
    store = LeadStore()
    analyzer = get_analyzer(config.PROVIDER)
    seen: set = set()
    while True:
        contact = jobs.get()
        stats = {"processed": 0, "duplicate": 0, "buying": 0, "error": 0}
        try:
            # قالب هر بار تازه خوانده می‌شود ← ویرایش template.md بدون ری‌استارت اعمال می‌شود
            sections, settings = messenger.load_template()
            if not contact["name"]:
                profile = instagram.get_profile(contact["ig_id"])
                contact["name"] = profile.get("name") or profile.get("username") or ""
            process_contact(contact, store=store, analyzer=analyzer, sections=sections,
                            settings=settings, seen=seen, dry_run=False, stats=stats)
        except FatalAPIError as e:
            log.error("⛔ %s — این پیام پردازش نشد", e)
        except Exception:
            log.exception("خطا در پردازش پیام %s", contact.get("id"))
        finally:
            jobs.task_done()


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code: int, body: str = "", ctype: str = "text/plain") -> None:
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/health":
            return self._reply(200, "ok")
        if url.path != PATH:
            return self._reply(404, "not found")
        q = dict(urllib.parse.parse_qsl(url.query))
        if q.get("hub.mode") == "subscribe" and config.IG_VERIFY_TOKEN and \
                q.get("hub.verify_token") == config.IG_VERIFY_TOKEN:
            log.info("✓ webhook توسط Meta تأیید شد")
            return self._reply(200, q.get("hub.challenge", ""))
        log.warning("تأیید webhook رد شد (verify_token اشتباه)")
        return self._reply(403, "forbidden")

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != PATH:
            return self._reply(404, "not found")
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if not instagram.verify_signature(body, self.headers.get("X-Hub-Signature-256")):
            log.warning("امضای نامعتبر — درخواست رد شد")
            return self._reply(401, "bad signature")
        try:
            contacts = instagram.extract_messages(json.loads(body))
        except json.JSONDecodeError:
            return self._reply(400, "bad json")
        for c in contacts:
            log.info("📩 دایرکت جدید از %s: %s", c["ig_id"], c["message"][:60])
            jobs.put(c)
        # Meta انتظار پاسخ سریع دارد؛ پردازش در پس‌زمینه انجام می‌شود
        return self._reply(200, "EVENT_RECEIVED")

    def log_message(self, fmt, *args):  # لاگ پیش‌فرض http.server را به logging بفرست
        log.debug(fmt, *args)


def main() -> None:
    log_path = setup_logging()
    if not config.IG_ACCESS_TOKEN:
        log.warning("IG_ACCESS_TOKEN تنظیم نشده — پیام‌ها فقط در outbox/ ذخیره می‌شوند (حالت تست)")
    if not config.IG_APP_SECRET:
        log.warning("IG_APP_SECRET تنظیم نشده — امضای درخواست‌ها بررسی نمی‌شود (فقط برای تست)")
    threading.Thread(target=worker, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", config.WEBHOOK_PORT), Handler)
    log.info("=== سرور اینستاگرام روی پورت %d | موتور: %s | لاگ: %s ===",
             config.WEBHOOK_PORT, config.PROVIDER, log_path)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("سرور متوقف شد")


if __name__ == "__main__":
    main()
