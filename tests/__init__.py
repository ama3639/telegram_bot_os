#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
پکیج تست‌های برنامه

این پکیج شامل تست‌های مختلف برای بررسی عملکرد صحیح اجزای مختلف ربات تلگرام است.
تست‌ها شامل موارد زیر می‌شوند:
- تست API‌های خارجی
- تست پرداخت رمزارزی
- تست یکپارچگی پرداخت
- تست هندلر تلگرام
- تست اصلاح منطقه زمانی
"""

import os
import sys

# افزودن مسیر ریشه پروژه به sys.path برای واردسازی ماژول‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# تنظیم متغیرهای محیطی مورد نیاز برای تست
os.environ.setdefault('TESTING', 'True')

__all__ = [
    'test_api',
    'test_crypto_payment',
    'test_payment_integration',
    'test_telegram_handler',
    'test_timezone_fix',
    'test_timezone_fix_windows',
    'run_tests'
] 