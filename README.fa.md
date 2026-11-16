# اتوماسیون خوش‌آمدگویی و ثبت سرنخ

[English](README.md) · **فارسی**

هر مخاطب جدید ← تحلیل با Claude (نیت + نام + علاقه) ← ثبت در SQLite ← پیام خوش‌آمد شخصی از روی `template.md` ← اگر قصد خرید داشت، اعلان برای فروشنده در `alerts.log`.

## نصب (یک‌بار)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # و کلید ANTHROPIC_API_KEY را در .env بگذارید
```

## اجرا
```bash
.venv/bin/python -m welcome_automation.run              # تحلیل واقعی با Claude
.venv/bin/python -m welcome_automation.run --mock       # بدون کلید API (تحلیل کلیدواژه‌ای، فقط برای تست)
.venv/bin/python -m welcome_automation.run --dry-run    # فقط نمایش؛ چیزی ذخیره/ارسال نمی‌شود
.venv/bin/python -m welcome_automation.run --reset      # پاک‌کردن DB و خروجی‌ها (فقط تست!)
.venv/bin/python -m welcome_automation.run --input other.json
```

## فایل‌ها
| فایل | کاربرد |
|---|---|
| `new_contacts.json` | ورودی تستی (۶ رکورد: ۲ خریدار، ۱ کنجکاو، ۱ سؤال، ۱ مبهم، ۱ تکراری) |
| `template.md` | **قالب پیام — آزادانه ویرایش کنید.** یک بخش برای هر نیت + نام برند |
| `leads.db` | دیتابیس سرنخ‌ها (SQLite) |
| `outbox/` | پیام‌های خوش‌آمد تولیدشده (شبیه‌سازی ارسال) |
| `alerts.log` | اعلان سرنخ‌های خرید برای فروشنده |
| `logs/run_*.log` | لاگ کامل هر اجرا |

دیدن سرنخ‌ها: `sqlite3 -header -column leads.db "select name, intent, interest, confidence from leads"`

## گاردریل‌ها
- **فقط یک پیام برای هر مخاطب:** شناسه‌ی یکتا = ایمیل (حروف کوچک، بدون فاصله) ← وگرنه شماره‌ی تلفن نرمال‌شده (`0912…` و `+98912…` و ارقام فارسی یکی حساب می‌شوند) ← وگرنه `id`. قبل از فراخوانی AI چک می‌شود (هزینه‌ی API برای تکراری صرف نمی‌شود) و ستون `UNIQUE` در دیتابیس لایه‌ی دوم است. ترتیب «اول ثبت، بعد ارسال» یعنی حتی اگر ارسال وسط کار خطا بدهد، پیام دوباره نمی‌رود.
- **خطای AI باعث پیام اشتباه نمی‌شود:** اگر تحلیل یک مخاطب ناموفق بود، آن مخاطب ثبت نمی‌شود و پیامی نمی‌گیرد؛ اجرای بعدی دوباره امتحان می‌شود. اگر مشکل از حساب باشد (کلید نامعتبر یا اعتبار تمام‌شده)، کل اجرا همان اول متوقف می‌شود.
- **پیام مخاطب داده است، نه دستور:** prompt به مدل می‌گوید دستورهای داخل پیام را اجرا نکند.

## اتصال به دنیای واقعی
همه‌ی منطق در تابع `process_contact(contact)` در `welcome_automation/run.py` است و به منبع ورودی وابسته نیست. برای اتصال فقط دو چیز عوض می‌شود: **از کجا مخاطب می‌آید** و **پیام از کجا ارسال می‌شود.**

### ۱) ورودی: فرم وب
Google Forms (با Apps Script)، Typeform، Webflow، Gravity Forms و… همه **webhook** دارند: با هر ارسال فرم یک درخواست POST با JSON می‌فرستند. یک سرور کوچک (مثلاً FastAPI) بالا بیاورید:
```python
# webhook.py — نمونه
from fastapi import FastAPI, Request
app = FastAPI()

@app.post("/webhook/form")
async def form(req: Request):
    data = await req.json()
    contact = {"id": data["response_id"], "channel": "website_form",
               "name": data.get("name", ""), "email": data.get("email", ""),
               "phone": data.get("phone", ""), "message": data.get("message", "")}
    process_contact(contact, ...)   # همان تابع فعلی
    return {"ok": True}
```
روی یک سرور با HTTPS اجرا کنید و آدرس را در تنظیمات webhook فرم بگذارید. **بدون کدنویسی:** Zapier/Make/n8n هم می‌توانند فرم را به همین endpoint وصل کنند.

### ۲) ورودی و خروجی: پیام‌رسان
- **تلگرام:** با BotFather یک ربات بسازید ← `setWebhook` به endpoint خودتان ← پیام‌های ورودی به `process_contact` می‌رسد ← در `messenger.send()` به‌جای نوشتن فایل، `sendMessage` تلگرام را صدا بزنید.
- **واتس‌اپ:** WhatsApp Business Cloud API (Meta) — webhook ورودی + ارسال پیام. نکته: پیام اول به کاربری که خودش شروع نکرده باید با «template message» تأییدشده‌ی Meta باشد.
- **اینستاگرام دایرکت:** Instagram Messaging API (از طریق Meta Business) — مشابه واتس‌اپ.
- **ایمیل:** در `send()` از SMTP یا سرویس‌هایی مثل Gmail API / Mailgun استفاده کنید.

### ۳) اعلان فروشنده
در `alerts.py` تابع `notify_seller` را عوض کنید (یا علاوه بر فایل) تا به گروه تلگرام فروش، کانال Slack یا ایمیل فروشنده پیام بدهد.

### ۴) اجرای خودکار
- حالت webhook: همیشه روشن، بلافاصله پاسخ می‌دهد (پیشنهادی).
- حالت دسته‌ای: با `cron` (یا `launchd` در مک) هر ۱۵ دقیقه اجرا شود، مثلاً:
  `*/15 * * * * cd /path/to/project && .venv/bin/python -m welcome_automation.run`
  منبع ورودی را هم به خروجی Google Sheets یا CRM تغییر دهید.

### ۵) مقیاس بزرگ‌تر
وقتی چند نفر هم‌زمان کار می‌کنند یا حجم بالا رفت، SQLite را با Postgres عوض کنید (فقط `storage.py` تغییر می‌کند) یا سرنخ‌ها را مستقیم در CRM (HubSpot، دیدار، …) ثبت کنید.

## هزینه و مدل
پیش‌فرض `claude-opus-5-5` با `effort: low` (طبقه‌بندی ساده است). برای حجم بالا می‌توانید در `.env` بنویسید `CLAUDE_MODEL=claude-haiku-5-5` (بسیار ارزان‌تر) و نتیجه را روی نمونه‌های خودتان مقایسه کنید.
