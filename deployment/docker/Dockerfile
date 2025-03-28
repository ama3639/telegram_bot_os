# ایجاد یک ایمیج داکر برای ربات تلگرام چندبخشی
FROM python:3.10-slim

# تنظیم محیط غیرتعاملی
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# انتخاب دایرکتوری کاری
WORKDIR /app

# نصب وابستگی‌های سیستمی مورد نیاز
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libssl-dev \
        git \
        curl \
        tzdata \
        sqlite3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# تنظیم منطقه زمانی
ENV TZ=Asia/Tehran

# کپی کردن فایل‌های وابستگی
COPY requirements.txt .

# نصب وابستگی‌های پایتون
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# کپی کردن کد برنامه
COPY . .

# ایجاد دایرکتوری‌های مورد نیاز
RUN mkdir -p data/backups/daily data/backups/weekly data/csv data/db data/reports \
    logs \
    cache

# تنظیم دسترسی‌ها
RUN chmod +x tools/*.py

# اجرای اسکریپت‌های اولیه برای راه‌اندازی پایگاه داده (اگر وجود نداشته باشد)
RUN if [ ! -f data/db/bot.db ]; then \
        sqlite3 data/db/bot.db < data/db/init_database.sql; \
    fi

# افشای پورت برای API (اگر موجود باشد)
EXPOSE 8000

# اسکریپت راه‌اندازی
CMD ["python", "__main__.py"]