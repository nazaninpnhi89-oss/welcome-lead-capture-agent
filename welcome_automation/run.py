"""نقطه‌ی ورود: خواندن مخاطبان ← ضدتکرار ← تحلیل AI ← ثبت ← خوش‌آمد ← اعلان فروشنده.

اجرا:
    .venv/bin/python -m welcome_automation.run            # با Claude
    .venv/bin/python -m welcome_automation.run --mock     # بدون کلید API
    .venv/bin/python -m welcome_automation.run --provider ollama   # مدل رایگان محلی
    گزینه‌ها: --input FILE  --dry-run  --reset
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from . import alerts, config, messenger
from .analyzer import FatalAPIError, get_analyzer
from .logger_setup import setup_logging
from .storage import LeadStore, contact_key

log = logging.getLogger("pipeline")


def process_contact(contact: dict, *, store: LeadStore, analyzer, sections, settings,
                    seen: set, dry_run: bool, stats: dict) -> None:
    """پردازش یک مخاطب — مستقل از منبع ورودی (فایل، webhook فرم، پیام‌رسان)."""
    key = contact_key(contact)
    tag = f"[{contact.get('id')} | {key}]"

    # گاردریل ۱: قبلاً پیام گرفته یا در همین اجرا دیده شده؟ (قبل از هزینه‌ی API)
    if key in seen or store.is_processed(key):
        log.info("%s SKIP duplicate — قبلاً خوش‌آمد گرفته", tag)
        stats["duplicate"] += 1
        return
    seen.add(key)

    analysis = analyzer.analyze(contact)
    if analysis.get("error"):
        # ثبت نمی‌کنیم و پیام نمی‌فرستیم ← اجرای بعدی دوباره امتحان می‌شود
        stats["error"] += 1
        log.warning("%s تحلیل ناموفق (%s) — ثبت/ارسال نشد؛ در اجرای بعدی دوباره امتحان می‌شود",
                    tag, analysis["error"])
        return
    log.info("%s تحلیل: intent=%s name=«%s» interest=«%s» conf=%.2f",
             tag, analysis["intent"], analysis["name"], analysis["interest"], analysis["confidence"])

    welcome = messenger.render_welcome(analysis, contact, sections, settings)
    is_buying = analysis["intent"] == "buying"

    if dry_run:
        log.info("%s DRY-RUN — پیام:\n%s", tag, welcome)
        stats["processed"] += 1
        stats["buying"] += is_buying
        return

    # گاردریل ۲: درج با UNIQUE — اول ثبت، بعد ارسال؛ پس هیچ‌وقت دو پیام نمی‌رود
    if not store.save_lead(key, contact, analysis, welcome, alerted=is_buying):
        log.info("%s SKIP duplicate (UNIQUE در DB)", tag)
        stats["duplicate"] += 1
        return
    log.info("%s ثبت در leads.db ✓", tag)

    try:
        out = messenger.send(key, contact, welcome)
        log.info("%s پیام خوش‌آمد ← %s", tag, out)
    except Exception as e:  # سرنخ ثبت شده ولی پیام نرفت ← فروشنده باید دستی پیگیری کند
        stats["error"] += 1
        log.error("%s ⚠️ ثبت شد ولی ارسال پیام ناموفق بود — دستی پیگیری کنید: %s", tag, e)

    if is_buying:
        alerts.notify_seller(contact, analysis)
        log.info("%s 🔥 اعلان فروشنده ← alerts.log", tag)
        stats["buying"] += 1
    stats["processed"] += 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="اتوماسیون خوش‌آمدگویی و ثبت سرنخ")
    p.add_argument("--input", type=Path, default=config.INPUT_FILE)
    p.add_argument("--mock", action="store_true", help="تحلیل آفلاین کلیدواژه‌ای (= --provider mock)")
    p.add_argument("--provider", choices=["claude", "ollama", "mock"], default=config.PROVIDER,
                   help="موتور تحلیل (پیش‌فرض از LLM_PROVIDER در .env)")
    p.add_argument("--dry-run", action="store_true", help="فقط نمایش؛ بدون نوشتن DB/outbox/alerts")
    p.add_argument("--reset", action="store_true", help="پاک‌کردن DB و خروجی‌ها (فقط برای تست)")
    args = p.parse_args(argv)

    if args.reset:
        for f in (config.DB_FILE, config.ALERTS_FILE):
            f.unlink(missing_ok=True)
        for f in config.OUTBOX_DIR.glob("*.md") if config.OUTBOX_DIR.exists() else []:
            f.unlink()

    log_path = setup_logging()
    provider = "mock" if args.mock else args.provider
    mode = {"mock": "MOCK", "claude": f"Claude ({config.CLAUDE_MODEL})",
            "ollama": f"Ollama ({config.OLLAMA_MODEL} @ {config.OLLAMA_HOST})"}[provider]
    log.info("=== شروع اجرا | حالت: %s | ورودی: %s | dry_run=%s | reset=%s ===",
             mode, args.input.name, args.dry_run, args.reset)

    try:
        contacts = json.loads(args.input.read_text(encoding="utf-8"))
        sections, settings = messenger.load_template()
    except (OSError, ValueError) as e:
        log.error("خطا در خواندن ورودی/قالب: %s", e)
        return 1

    store = LeadStore()
    analyzer = get_analyzer(provider)
    stats = {"total": len(contacts), "processed": 0, "duplicate": 0, "buying": 0, "error": 0}
    seen: set = set()

    for contact in contacts:
        try:
            process_contact(contact, store=store, analyzer=analyzer, sections=sections,
                            settings=settings, seen=seen, dry_run=args.dry_run, stats=stats)
        except FatalAPIError as e:  # مشکل حساب (اعتبار/کلید) ← ادامه بی‌فایده است
            stats["error"] += 1
            log.error("⛔ اجرا متوقف شد: %s", e)
            break
        except Exception:  # یک مخاطب خراب نباید کل اجرا را متوقف کند
            stats["error"] += 1
            log.exception("[%s] خطای پیش‌بینی‌نشده", contact.get("id"))
    store.close()

    log.info("=== پایان | کل: %(total)d | پردازش: %(processed)d | تکراری: %(duplicate)d | "
             "buying: %(buying)d | خطا: %(error)d ===", stats)
    log.info("لاگ کامل: %s", log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
