"""ذخیره‌سازی سرنخ‌ها در SQLite + گاردریل ضدتکرار (contact_key یکتا)."""
import re
import sqlite3
from datetime import datetime

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_key     TEXT NOT NULL UNIQUE,
    source_id       TEXT,
    name            TEXT,
    email           TEXT,
    phone           TEXT,
    channel         TEXT,
    message         TEXT,
    intent          TEXT,
    interest        TEXT,
    confidence      REAL,
    summary         TEXT,
    analysis_error  TEXT,
    welcome_message TEXT,
    alerted         INTEGER DEFAULT 0,
    received_at     TEXT,
    created_at      TEXT NOT NULL
);
"""

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", (phone or "").translate(_PERSIAN_DIGITS))
    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = digits[2:]
    return digits.lstrip("0")  # 09123456789 و +989123456789 ← 9123456789


def contact_key(contact: dict) -> str:
    """شناسه‌ی یکتای مخاطب: ایمیل ← تلفن ← id."""
    if contact.get("ig_id"):  # شناسه‌ی ثابت فرستنده در اینستاگرام (IGSID)
        return f"ig:{contact['ig_id']}"
    email = (contact.get("email") or "").strip().lower()
    if email:
        return f"email:{email}"
    phone = normalize_phone(contact.get("phone", ""))
    if phone:
        return f"phone:{phone}"
    return f"id:{contact.get('id')}"


class LeadStore:
    def __init__(self, path=config.DB_FILE):
        self.conn = sqlite3.connect(path)
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def is_processed(self, key: str) -> bool:
        return self.conn.execute("SELECT 1 FROM leads WHERE contact_key = ?", (key,)).fetchone() is not None

    def save_lead(self, key: str, contact: dict, analysis: dict, welcome: str, alerted: bool) -> bool:
        """درج سرنخ. اگر کلید تکراری بود (لایه‌ی دوم گاردریل) False برمی‌گرداند."""
        try:
            with self.conn:
                self.conn.execute(
                    """INSERT INTO leads (contact_key, source_id, name, email, phone, channel, message,
                        intent, interest, confidence, summary, analysis_error, welcome_message, alerted,
                        received_at, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (key, contact.get("id"), analysis["name"], (contact.get("email") or "").strip(),
                     contact.get("phone"), contact.get("channel"), contact.get("message"),
                     analysis["intent"], analysis["interest"], analysis["confidence"],
                     analysis["summary_fa"], analysis.get("error"), welcome, int(alerted),
                     contact.get("received_at"), datetime.now().isoformat(timespec="seconds")),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def close(self):
        self.conn.close()
