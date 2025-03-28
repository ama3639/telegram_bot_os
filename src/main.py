#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
فایل اصلی برنامه.

این فایل نقطه ورود اصلی برنامه است و وظیفه راه‌اندازی و مدیریت ربات تلگرام را بر عهده دارد.

تاریخ ایجاد: ۱۴۰۴/۰۱/۰۷
"""

import os
import sys
import logging
import argparse
from dotenv import load_dotenv

# تنظیم مسیر برای import‌های نسبی
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.append(parent_dir)

# ماژول‌های داخلی
from src.core.bot import TelegramBot
from src.core.config import load_config
from src.core.database import Database
from src.utils.logger import setup_logger
from src.utils.cache import Cache
from src.utils.timezone_utils import get_current_datetime

def parse_arguments():
    """
    تجزیه آرگومان‌های خط فرمان
    
    بازگشت:
        argparse.Namespace: آرگومان‌های تجزیه شده
    """
    parser = argparse.ArgumentParser(description='ربات تلگرام - Mr.Trader')
    
    parser.add_argument('--debug', action='store_true', help='فعال‌سازی حالت دیباگ')
    parser.add_argument('--config', type=str, default='.env', help='مسیر فایل تنظیمات')
    parser.add_argument('--db', type=str, default='data/db/bot.db', help='مسیر فایل پایگاه داده')
    parser.add_argument('--log', type=str, default='logs/telegram_bot.log', help='مسیر فایل لاگ')
    
    return parser.parse_args()

def main():
    """
    تابع اصلی برنامه
    """
    # تجزیه آرگومان‌های خط فرمان
    args = parse_arguments()
    
    # راه‌اندازی logger
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logger(log_level, args.log)
    logger = logging.getLogger(__name__)
    
    # بارگذاری تنظیمات محیطی
    load_dotenv(args.config)
    
    logger.info("شروع راه‌اندازی ربات تلگرام...")
    logger.info(f"زمان فعلی: {get_current_datetime()}")
    
    try:
        # بارگذاری تنظیمات
        config = load_config()
        logger.info("تنظیمات با موفقیت بارگذاری شدند.")
        
        # اتصال به پایگاه داده
        database = Database(args.db)
        logger.info("اتصال به پایگاه داده برقرار شد.")
        
        # ایجاد سیستم کش
        cache = Cache()
        logger.info("سیستم کش راه‌اندازی شد.")
        
        # ایجاد و راه‌اندازی ربات
        bot = TelegramBot(config, database, cache)
        logger.info("ربات با موفقیت ایجاد شد.")
        
        # شروع ربات
        bot.start()
        
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()