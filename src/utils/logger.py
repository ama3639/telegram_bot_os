#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول تنظیم سیستم لاگ‌گیری.

این ماژول مسئول پیکربندی سیستم لاگ‌گیری برنامه است و امکان ثبت لاگ‌ها
در فایل و کنسول را فراهم می‌کند.

تاریخ ایجاد: ۱۴۰۴/۰۱/۰۷
"""

import os
import logging
import time
from logging.handlers import RotatingFileHandler
from typing import Optional

def setup_logger(level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """
    تنظیم و پیکربندی سیستم لاگ‌گیری.
    
    پارامترها:
        level: سطح لاگ‌گیری (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: مسیر فایل لاگ (اختیاری)
    """
    # تنظیم روت لاگر
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # حذف هندلرهای قبلی برای جلوگیری از تکرار
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)
    
    # فرمت پیام‌های لاگ
    log_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # افزودن هندلر کنسول
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # افزودن هندلر فایل (در صورت مشخص شدن فایل لاگ)
    if log_file:
        # اطمینان از وجود دایرکتوری لاگ
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        # ایجاد هندلر فایل با قابلیت چرخش
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # حداکثر ۱۰ مگابایت
            backupCount=5,  # نگهداری ۵ فایل قدیمی
            encoding='utf-8'
        )
        file_handler.setFormatter(log_format)
        root_logger.addHandler(file_handler)
    
    # ایجاد لاگر برای ماژول‌های خارجی با سطح بالاتر
    for logger_name in ['telegram', 'httpx', 'urllib3']:
        ext_logger = logging.getLogger(logger_name)
        ext_logger.setLevel(logging.WARNING)  # سطح WARNING برای کتابخانه‌های خارجی
    
    # لاگ اطلاعات راه‌اندازی
    logger = logging.getLogger(__name__)
    logger.info(f"سیستم لاگ‌گیری با سطح {logging.getLevelName(level)} راه‌اندازی شد.")
    if log_file:
        logger.info(f"لاگ‌ها در فایل {log_file} ذخیره می‌شوند.")

def get_logger(name: str) -> logging.Logger:
    """
    دریافت یک شیء Logger با نام مشخص شده.
    
    پارامترها:
        name: نام لاگر (معمولاً نام ماژول)
        
    بازگشت:
        logging.Logger: شیء لاگر
    """
    return logging.getLogger(name)

def log_execution_time(func):
    """
    دکوراتور برای محاسبه و ثبت زمان اجرای توابع.
    
    پارامترها:
        func: تابعی که زمان اجرای آن محاسبه می‌شود
        
    بازگشت:
        تابع wrapper
    """
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
         
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        logger.debug(f"زمان اجرای {func.__name__}: {execution_time:.4f} ثانیه")
        
        return result
    
    return wrapper

def log_exception(exception: Exception, message: str = None, extra_info: dict = None) -> None:
    """
    ثبت اطلاعات خطا در سیستم لاگ

    پارامترها:
        exception: شیء خطا
        message: پیام اختیاری برای توضیح بیشتر
        extra_info: اطلاعات اضافی مرتبط با خطا
    """
    logger = get_logger(__name__)
    
    if message:
        logger.error(message)
    
    logger.error(f"خطا: {type(exception).__name__} - {str(exception)}")
    
    import traceback
    logger.error("جزئیات خطا:\n" + traceback.format_exc())
    
    if extra_info:
        logger.error(f"اطلاعات اضافی: {extra_info}")
        
def enable_debug_logging() -> None:
    """
    فعال‌سازی لاگ‌گیری در سطح DEBUG
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    logger = get_logger(__name__)
    logger.info("لاگ‌گیری در سطح DEBUG فعال شد.")

def disable_debug_logging() -> None:
    """
    غیرفعال‌سازی لاگ‌گیری در سطح DEBUG و بازگشت به سطح INFO
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logger = get_logger(__name__)
    logger.info("لاگ‌گیری در سطح INFO بازنشانی شد.")