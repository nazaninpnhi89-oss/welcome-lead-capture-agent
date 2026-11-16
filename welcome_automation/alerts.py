"""اعلان سرنخ جدی (buying) برای فروشنده. فعلاً در alerts.log؛ بعداً تلگرام/اسلک/ایمیل."""
from datetime import datetime

from . import config


def notify_seller(contact: dict, analysis: dict) -> None:
    contact_info = " / ".join(x for x in [(contact.get("email") or "").strip(), contact.get("phone") or "",
                                       f"Instagram ID: {contact['ig_id']}" if contact.get("ig_id") else ""] if x)
    block = (
        f"🔥 [{datetime.now().isoformat(timespec='seconds')}] سرنخ خرید جدید\n"
        f"   نام: {analysis['name'] or '—'}\n"
        f"   تماس: {contact_info or '—'}  (کانال: {contact.get('channel')})\n"
        f"   علاقه: {analysis['interest'] or '—'}\n"
        f"   اطمینان: {analysis['confidence']:.0%}\n"
        f"   خلاصه: {analysis['summary_fa']}\n"
        f"   پیام اصلی: {contact.get('message')}\n"
        f"{'-' * 60}\n"
    )
    with open(config.ALERTS_FILE, "a", encoding="utf-8") as f:
        f.write(block)
