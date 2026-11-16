"""ارتباط با Instagram API (with Instagram Login): ارسال دایرکت، گرفتن نام، بررسی امضای webhook."""
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from . import config

log = logging.getLogger("instagram")
GRAPH = "https://graph.instagram.com"


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    url = f"{GRAPH}/{config.IG_API_VERSION}/{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {config.IG_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Instagram API {e.code}: {e.read().decode(errors='replace')[:300]}") from e


def send_text(ig_user_id: str, text: str) -> None:
    """پاسخ در دایرکت. اینستاگرام فقط تا ۲۴ ساعت پس از آخرین پیام کاربر اجازه‌ی پاسخ می‌دهد."""
    _request("POST", "me/messages", {"recipient": {"id": ig_user_id}, "message": {"text": text[:1000]}})


def get_profile(ig_user_id: str) -> dict:
    """نام و نام‌کاربری فرستنده (اختیاری؛ اگر نشد خالی برمی‌گرداند)."""
    if not config.IG_ACCESS_TOKEN:
        return {}
    try:
        return _request("GET", f"{urllib.parse.quote(ig_user_id)}?fields=name,username")
    except Exception as e:
        log.warning("گرفتن پروفایل %s ناموفق: %s", ig_user_id, e)
        return {}


def verify_signature(body: bytes, header: str | None) -> bool:
    """بررسی اینکه درخواست واقعاً از طرف Meta آمده (X-Hub-Signature-256)."""
    if not config.IG_APP_SECRET:
        return True  # در حالت تست محلی بدون secret
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(config.IG_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def extract_messages(payload: dict) -> list[dict]:
    """تبدیل بدنه‌ی webhook اینستاگرام به لیست مخاطب‌ها با همان فرمت new_contacts.json."""
    contacts = []
    if payload.get("object") != "instagram":
        return contacts
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            msg = event.get("message") or {}
            # پیام‌هایی که خودمان فرستاده‌ایم (echo) را نادیده بگیر؛ وگرنه حلقه‌ی بی‌نهایت می‌شود
            if msg.get("is_echo") or not msg.get("text"):
                continue
            sender = event.get("sender", {}).get("id")
            if not sender or sender == entry.get("id"):
                continue
            contacts.append({
                "id": msg.get("mid", sender),
                "ig_id": sender,
                "channel": "instagram_dm",
                "name": "",
                "email": "",
                "phone": "",
                "message": msg["text"],
                "received_at": str(event.get("timestamp", "")),
            })
    return contacts
