"""ساخت showcase/en/index.html از نتایج واقعی showcase/en/leads_en.db
اجرا: .venv/bin/python showcase/en/build_en.py
(اول خط پردازش را با متغیرهای INPUT_FILE / TEMPLATE_FILE / DB_FILE نسخه‌ی انگلیسی اجرا کنید — README)"""
import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELS = {"e-001": "James · B2B quote", "e-002": "Priya · Instagram", "e-003": "Marco · Instagram",
          "e-005": "Support hours", "e-004": "Tom · just curious", "e-006": "Just “hi”"}

conn = sqlite3.connect(HERE / "leads_en.db")
conn.row_factory = sqlite3.Row
rows = {r["source_id"]: dict(r) for r in conn.execute("SELECT * FROM leads")}
samples = [{
    "label": LABELS[sid], "channel": r["channel"], "message": r["message"],
    "from": (r["email"] or "").strip() or r["phone"] or "",
    "intent": r["intent"], "name": r["name"], "interest": r["interest"],
    "confidence": r["confidence"], "summary": r["summary"], "welcome": r["welcome_message"],
} for sid, r in ((s, rows[s]) for s in LABELS)]
dup = json.loads((HERE / "new_contacts_en.json").read_text(encoding="utf-8"))[-1]
samples.append({
    "label": "James · follow-up", "channel": dup["channel"], "message": dup["message"],
    "from": dup["email"].strip(), "duplicate": True,
    "dupReason": "This time the email had different capitals and a stray space, but the system still recognizes him.",
})
html = (HERE / "template_en.html").read_text(encoding="utf-8")
html = html.replace("__CSS__", (HERE / "_css.txt").read_text(encoding="utf-8"))
html = html.replace("__DATA__", json.dumps(samples, ensure_ascii=False))
(HERE / "index.html").write_text(html, encoding="utf-8")
print(f"showcase/en/index.html ✓ ({len(samples)} samples)")
