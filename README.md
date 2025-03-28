# ربات تلگرام مدولار چندمنظوره

![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Python-Telegram-Bot](https://img.shields.io/badge/PTB-20.7-blue)

این یک پروژه ربات تلگرام مدولار، جامع و انعطاف‌پذیر است که با استفاده از زبان پایتون و کتابخانه python-telegram-bot نسخه 20.7 ساخته شده است. این ربات قابلیت ارتباط با API‌های مختلف، ذخیره‌سازی داده و پردازش درخواست‌های پیچیده را دارد.

## ویژگی‌ها

- 🔄 ساختار مدولار و انعطاف‌پذیر
- 🌐 پشتیبانی از چندین زبان (فارسی، انگلیسی، عربی، ترکی و...)
- 🔐 سیستم احراز هویت و سطوح دسترسی
- 💰 سیستم پرداخت و اشتراک
- 📈 پشتیبانی از API‌های مختلف (بایننس، کوکوین و...)
- 📊 سیستم گزارش‌گیری و آمار
- 📱 رابط کاربری تلگرامی کارآمد
- 🔄 سیستم پشتیبان‌گیری خودکار
- 🧠 آماده برای اتصال به سیستم‌های هوش مصنوعی

## سازگاری با نسخه ۲۰.۷ کتابخانه python-telegram-bot

این ربات با نسخه ۲۰.۷ کتابخانه python-telegram-bot سازگار شده است. تغییرات اصلی عبارتند از:

- استفاده از ساختار نوین `Application` به جای `Updater` و `Dispatcher`
- پیاده‌سازی تمام متدهای ارتباط با تلگرام به صورت ناهمگام (`async/await`)
- تغییر در فیلترها و نحوه ثبت هندلرها
- پشتیبانی از روش‌های جدید راه‌اندازی ربات در حالت polling یا webhook

## پیش‌نیازها

- Python 3.9+
- pip (برای نصب وابستگی‌ها)
- توکن ربات تلگرام
- کتابخانه python-telegram-bot نسخه ۲۰.۷+

## نصب و راه‌اندازی

### 1. دریافت کد منبع

```bash
git clone https://github.com/yourusername/telegram-modular-bot.git
cd telegram-modular-bot
```

### 2. ایجاد محیط مجازی (اختیاری اما توصیه می‌شود)

```bash
python -m venv venv
# در لینوکس/مک
source venv/bin/activate
# در ویندوز
venv\Scripts\activate
```

### 3. نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

### 4. تنظیم فایل .env

فایل `.env.example` را به `.env` تغییر نام داده و آن را با اطلاعات خود پر کنید:

```
TELEGRAM_BOT_TOKEN=7827540568:AAGLYFfEynhXldW6w4-1X2qMMn3VcTxDMvM
ADMIN_IDS=1517662886
...
```

### 5. اجرای ربات

```bash
python __main__.py
```

یا با گزینه دیباگ برای گزارش‌های بیشتر:

```bash
python __main__.py --debug
```

## نمونه کد راه‌اندازی ربات

```python
from telegram.ext import Application

# نمونه راه‌اندازی ربات با ساختار جدید
async def main():
    application = Application.builder().token(TOKEN).build()
    
    # افزودن هندلرها
    application.add_handler(...)
    
    # راه‌اندازی ربات
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## ساختار پروژه

```
project_bot_medular/
├── 1. data/                      # داده‌های ذخیره شده
├── 2. deployment/                # فایل‌های مربوط به استقرار
├── 3. locales/                   # فایل‌های ترجمه
├── 4. logs/                      # فایل‌های لاگ سیستم
├── 5. src/                       # کد منبع پروژه
│   ├── 5.1. api/                 # رابط‌های API
│   ├── 5.2. accounting/          # ماژول مدیریت مالی
│   ├── 5.3. core/                # هسته اصلی برنامه
│   ├── 5.4. handlers/            # هندلرهای تلگرام
│   ├── 5.5. models/              # مدل‌های داده
│   ├── 5.6. strategies/          # استراتژی‌های تحلیل
│   ├── 5.7. utils/               # توابع کمکی
│   ├── 5.8. __init__.py          # فایل آغازگر پکیج
│   └── 5.9. main.py              # فایل اصلی برنامه
├── 6. tests/                     # تست‌های برنامه
├── 7. tools/                     # ابزارهای توسعه و نگهداری
├── 8. docs/                      # مستندات پروژه
├── 9. cache/                     # فایل‌های کش موقت
├── 10. .env                      # فایل تنظیمات محیطی (محرمانه)
├── 11. .env.example              # نمونه فایل تنظیمات
├── 12. .gitignore                # فایل‌های نادیده گرفته شده در گیت
├── 13. LICENSE                   # فایل مجوز استفاده
├── 14. README.md                 # مستندات پروژه (این فایل)
├── 15. requirements.txt          # وابستگی‌های پروژه
└── 16. __main__.py               # نقطه ورود اصلی برنامه
```

## دستورات ربات

- `/start` - شروع استفاده از ربات
- `/help` - نمایش راهنمای استفاده
- `/about` - اطلاعات درباره ربات
- `/profile` - مشاهده پروفایل کاربری
- `/settings` - تنظیمات ربات
- `/subscribe` - خرید اشتراک
- `/contact` - ارتباط با پشتیبانی
- `/language` - تغییر زبان ربات

### دستورات ادمین

- `/admin` - پنل مدیریت
- `/stats` - آمار ربات
- `/users` - مدیریت کاربران
- `/broadcast` - ارسال پیام به کاربران
- `/status` - وضعیت سیستم
- `/extend_subscription` - تمدید اشتراک کاربران

## توسعه و افزودن قابلیت‌های جدید

برای افزودن قابلیت‌های جدید، می‌توانید:

1. در پوشه `handlers` هندلرهای جدید اضافه کنید (توجه کنید که تمامی توابع هندلر باید `async` باشند)
2. در پوشه `api` رابط‌های API جدید ایجاد کنید
3. در پوشه `utils` توابع کمکی جدید بنویسید

همچنین می‌توانید با استفاده از سیستم پلاگین، قابلیت‌های خود را در قالب پلاگین توسعه دهید.

## نکات مهم در استفاده از نسخه 20.7 کتابخانه

- تمام توابع هندلر باید به صورت `async def` تعریف شوند.
- برای دسترسی به آپدیت و کانتکست از پارامترهای `Update` و `ContextTypes.DEFAULT_TYPE` استفاده کنید.
- استفاده از `filters` به جای `Filters` در نسخه جدید.
- استفاده از `await` برای تمامی فراخوانی‌های API تلگرام.

## مهاجرت به SQL

این پروژه در حال حاضر از SQLite استفاده می‌کند، اما برای مهاجرت به سایر پایگاه‌های داده مانند MySQL یا PostgreSQL:

1. تنظیمات `DATABASE_URL` را در فایل `.env` تغییر دهید
2. از اسکریپت‌های مهاجرت در پوشه `tools/db_migration` استفاده کنید

## ارتباط با هوش مصنوعی

برای فعال کردن قابلیت‌های هوش مصنوعی:

1. تنظیم `ENABLE_ML=True` در فایل `.env`
2. افزودن مدل‌های هوش مصنوعی در پوشه `src/strategies/machine_learning`

## زمانبندی وظایف

برای استفاده از وظایف زمانبندی شده (مانند یادآوری به کاربران) از قابلیت job queue در نسخه 20.7 استفاده کنید:

```python
# افزودن زمانبندی
application.job_queue.run_repeating(send_inactive_reminder, interval=86400)  # اجرا روزانه
application.job_queue.run_repeating(send_subscription_expiry_reminder, interval=43200)  # اجرا هر 12 ساعت
```

## مستندات بیشتر

برای اطلاعات بیشتر به پوشه `docs` مراجعه کنید.

## لایسنس

این پروژه تحت مجوز MIT منتشر شده است.