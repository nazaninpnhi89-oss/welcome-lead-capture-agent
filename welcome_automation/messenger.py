"""ساخت پیام خوش‌آمد از template.md و «ارسال» آن (فعلاً ذخیره در outbox/)."""
import re

from . import config

DEFAULT_NAME = "دوست عزیز"
DEFAULT_INTEREST = "خدمات ما"


class _SafeDict(dict):
    def __missing__(self, key):  # متغیر ناشناخته ← همان‌طور که هست
        return "{" + key + "}"


def load_template(path=config.TEMPLATE_FILE) -> tuple[dict, dict]:
    """قالب را به بخش‌ها (بر اساس ## سرتیتر) و تنظیمات تقسیم می‌کند."""
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    sections, current = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(\w+)\s*$", line)
        if m:
            current = m.group(1).lower()
            sections[current] = []
        elif current:
            sections[current].append(line)
    sections = {k: "\n".join(v).strip() for k, v in sections.items()}
    settings = {}
    for line in sections.pop("settings", "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            settings[k.strip()] = v.strip()
    missing = [i for i in config.INTENTS if i not in sections]
    if missing:
        raise ValueError(f"template.md بخش‌های {missing} را ندارد")
    return sections, settings


def render_welcome(analysis: dict, contact: dict, sections: dict, settings: dict) -> str:
    # «رضا احمدی» ← «رضا» برای لحن صمیمی؛ اسم انگلیسی هم همین‌طور
    name = analysis.get("name") or ""
    # مقدار پیش‌فرض را می‌شود در بخش ## settings قالب عوض کرد (default_name / default_interest)
    first = name.split()[0] if name else settings.get("default_name", DEFAULT_NAME)
    values = _SafeDict(settings)
    values.update(
        name=first,
        interest=analysis.get("interest") or settings.get("default_interest", DEFAULT_INTEREST),
        channel=contact.get("channel", ""),
    )
    return sections[analysis["intent"]].format_map(values)


def send(contact_key: str, contact: dict, message: str) -> str:
    """ارسال پیام. همیشه یک نسخه در outbox/ ذخیره می‌شود؛
    اگر مخاطب از اینستاگرام آمده و توکن تنظیم شده، واقعاً در دایرکت فرستاده می‌شود.
    در صورت شکست ارسال واقعی، استثنا بالا می‌رود."""
    config.OUTBOX_DIR.mkdir(exist_ok=True)
    safe = re.sub(r"[^\w.@+-]", "_", contact_key)
    path = config.OUTBOX_DIR / f"{safe}.md"
    path.write_text(f"<!-- to: {contact_key} via {contact.get('channel')} -->\n{message}\n", encoding="utf-8")
    try:
        where = str(path.relative_to(config.ROOT))
    except ValueError:  # outbox outside the project folder (e.g. in tests)
        where = str(path)
    if contact.get("ig_id") and config.IG_ACCESS_TOKEN:
        from . import instagram

        instagram.send_text(contact["ig_id"], message)
        where += " + دایرکت اینستاگرام ✓"
    return where
