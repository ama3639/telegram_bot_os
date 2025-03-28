#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
این ماژول شامل هندلرهای پیام‌های تلگرام برای ربات است.
هندلرها به دسته‌های مختلف تقسیم شده‌اند: کاربران، ادمین‌ها و پرداخت‌ها.
"""

from handlers.admin_handlers import register_admin_handlers
from handlers.user_handlers import register_user_handlers
from handlers.payment_handlers import register_payment_handlers
# from handlers.telegram_handler import TelegramHandler

__all__ = [
    'register_admin_handlers',
    'register_user_handlers',
    'register_payment_handlers',
    'TelegramHandler',
]

# تنظیم لاگر برای هندلرها
import logging
logger = logging.getLogger('telegram.handlers')

async def register_all_handlers(application, config, database, cache):
    """
    ثبت تمام هندلرهای تلگرام در اپلیکیشن.
    
    Args:
        application: اپلیکیشن تلگرام برای ثبت هندلرها
        config: تنظیمات برنامه
        database: پایگاه داده
        cache: سیستم کش
        
    Returns:
        None
    """
    logger.info("ثبت هندلرهای تلگرام...")
    
    # ثبت هندلرهای کاربر - اولویت پایین (اجرا در آخر)
    register_user_handlers(application)
    logger.debug("هندلرهای کاربر ثبت شدند")
    
    # ثبت هندلرهای پرداخت - اولویت متوسط
    register_payment_handlers(application, config, database, cache)
    logger.debug("هندلرهای پرداخت ثبت شدند")
    
    # ثبت هندلرهای ادمین - اولویت بالا (اجرا در اول)
    register_admin_handlers(application, config, database, cache)
    logger.debug("هندلرهای ادمین ثبت شدند")
    
    logger.info("تمامی هندلرهای تلگرام با موفقیت ثبت شدند")