"""ساخت showcase/index.html از روی نتایج واقعی leads.db (اجرا: .venv/bin/python showcase/build.py)"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABELS = {"c-001": "رضا · خرید سازمانی", "m1": "سارا · اینستاگرام", "c-002": "مریم · دوره آموزشی",
          "c-004": "سؤال ساعت کاری", "c-003": "Ali · کنجکاو", "c-005": "فقط «سلام»"}
ORDER = list(LABELS)

conn = sqlite3.connect(ROOT / "leads.db")
conn.row_factory = sqlite3.Row
rows = {r["source_id"]: dict(r) for r in conn.execute("SELECT * FROM leads")}
samples = []
for sid in ORDER:
    r = rows[sid]
    samples.append({
        "label": LABELS[sid], "channel": r["channel"], "message": r["message"],
        "from": r["email"] or r["phone"] or "",
        "intent": r["intent"], "name": r["name"], "interest": r["interest"],
        "confidence": r["confidence"], "summary": r["summary"], "welcome": r["welcome_message"],
    })
dup = json.loads((ROOT / "new_contacts.json").read_text(encoding="utf-8"))[-1]
samples.append({
    "label": "رضا · پیام دوم", "channel": dup["channel"], "message": dup["message"],
    "from": dup["email"], "duplicate": True,
    "dupReason": "ایمیلش این بار با حروف کوچک و یک فاصله‌ی اضافه نوشته شده، ولی سیستم تشخیص می‌دهد همان آدم است.",
})
html = (ROOT / "showcase/template.html").read_text(encoding="utf-8")
html = html.replace("__DATA__", json.dumps(samples, ensure_ascii=False))
(ROOT / "showcase/index.html").write_text(html, encoding="utf-8")
print(f"showcase/index.html ✓ ({len(samples)} samples)")
