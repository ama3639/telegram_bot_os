#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول مدیریت چندزبانگی.

این ماژول مسئول بارگذاری و مدیریت پیام‌های چندزبانه برنامه است.

تاریخ ایجاد: ۱۴۰۴/۰۱/۰۷
"""

import os
import json
import logging
from typing import Dict, Any, Optional
import threading

from src.utils.cache import Cache

logger = logging.getLogger(__name__)

# سینگلتون برای مدیریت ترجمه‌ها
class Localization:
    """
    کلاس مدیریت چندزبانگی برنامه.
    این کلاس به صورت سینگلتون پیاده‌سازی شده است.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Localization, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.messages: Dict[str, Dict[str, str]] = {}
        self.default_language = 'fa'
        self.available_languages = []
        self.cache = Cache()
         
        self._initialized = True
        logger.info("سیستم چندزبانگی ایجاد شد.")
    
    def load_languages(self, locales_dir: str = 'locales') -> None:
        """
        بارگذاری فایل‌های ترجمه از دایرکتوری.
        
        پارامترها:
            locales_dir: مسیر دایرکتوری حاوی فایل‌های ترجمه
        """
        if not os.path.exists(locales_dir):
            logger.error(f"دایرکتوری '{locales_dir}' یافت نشد!")
            return
        
        # پیدا کردن زبان‌های موجود
        available_languages = []
        for lang_dir in os.listdir(locales_dir):
            lang_path = os.path.join(locales_dir, lang_dir)
            if os.path.isdir(lang_path):
                msg_file = os.path.join(lang_path, 'messages.json')
                if os.path.isfile(msg_file):
                    available_languages.append(lang_dir)
        
        self.available_languages = available_languages
        logger.info(f"زبان‌های یافت شده: {', '.join(available_languages)}")
        
        # بارگذاری پیام‌های هر زبان
        for lang in available_languages:
            self._load_language(locales_dir, lang)
    
    def _load_language(self, locales_dir: str, language: str) -> None:
        """
        بارگذاری فایل پیام‌های یک زبان.
        
        پارامترها:
            locales_dir: مسیر دایرکتوری حاوی فایل‌های ترجمه
            language: کد زبان
        """
        msg_file = os.path.join(locales_dir, language, 'messages.json')
        
        try:
            with open(msg_file, 'r', encoding='utf-8') as f:
                messages = json.load(f)
            
            self.messages[language] = messages
            logger.info(f"فایل پیام‌های زبان '{language}' با {len(messages)} پیام بارگذاری شد.")
            
        except Exception as e:
            logger.error(f"خطا در بارگذاری فایل پیام‌های زبان '{language}': {str(e)}")
    
    def set_default_language(self, language: str) -> None:
        """
        تنظیم زبان پیش‌فرض.
        
        پارامترها:
            language: کد زبان
        
        استثناها:
            ValueError: اگر زبان در دسترس نباشد.
        """
        if language not in self.available_languages:
            raise ValueError(f"زبان '{language}' در دسترس نیست!")
        
        self.default_language = language
        logger.info(f"زبان پیش‌فرض به '{language}' تغییر یافت.")
    
    def get_message(self, key: str, language: Optional[str] = None) -> str:
        """
        دریافت پیام ترجمه شده.
        
        پارامترها:
            key: کلید پیام
            language: کد زبان (اگر None باشد، از زبان پیش‌فرض استفاده می‌شود)
            
        بازگشت:
            str: پیام ترجمه شده یا کلید اصلی در صورت عدم وجود ترجمه
        """
        # استفاده از زبان پیش‌فرض اگر زبان مشخص نشده باشد
        lang = language or self.default_language
        
        # بررسی کش
        cache_key = f"message:{lang}:{key}"
        cached_message = self.cache.get(cache_key)
        if cached_message is not None:
            return cached_message
        
        # اگر زبان موجود نباشد، از زبان پیش‌فرض استفاده می‌کنیم
        if lang not in self.messages:
            logger.warning(f"زبان '{lang}' یافت نشد. استفاده از زبان پیش‌فرض '{self.default_language}'.")
            lang = self.default_language
        
        # بررسی وجود کلید در پیام‌های زبان
        if lang in self.messages and key in self.messages[lang]:
            message = self.messages[lang][key]
            self.cache.set(cache_key, message)
            return message
        
        # اگر در زبان انتخابی یافت نشد، بررسی زبان پیش‌فرض
        if lang != self.default_language and self.default_language in self.messages and key in self.messages[self.default_language]:
            message = self.messages[self.default_language][key]
            self.cache.set(cache_key, message)
            return message
        
        # اگر پیام یافت نشد، خود کلید را بازمی‌گردانیم
        logger.warning(f"پیام با کلید '{key}' در زبان '{lang}' یافت نشد.")
        self.cache.set(cache_key, key)
        return key
    
    def get_all_messages(self, language: Optional[str] = None) -> Dict[str, str]:
        """
        دریافت تمام پیام‌های یک زبان.
        
        پارامترها:
            language: کد زبان (اگر None باشد، از زبان پیش‌فرض استفاده می‌شود)
            
        بازگشت:
            Dict[str, str]: دیکشنری حاوی تمام پیام‌های زبان
        """
        lang = language or self.default_language
        
        if lang not in self.messages:
            logger.warning(f"زبان '{lang}' یافت نشد. استفاده از زبان پیش‌فرض '{self.default_language}'.")
            lang = self.default_language
        
        return self.messages.get(lang, {})
    
    def reload(self, locales_dir: str = 'locales') -> None:
        """
        بارگذاری مجدد فایل‌های ترجمه.
        
        پارامترها:
            locales_dir: مسیر دایرکتوری حاوی فایل‌های ترجمه
        """
        self.messages = {}
        self.cache.clear()
        self.load_languages(locales_dir)
        logger.info("فایل‌های ترجمه مجدداً بارگذاری شدند.")


# رابط‌های عمومی ماژول
_localization = Localization()

def load_languages(locales_dir: str = 'locales') -> None:
    """
    بارگذاری فایل‌های ترجمه از دایرکتوری.
    
    پارامترها:
        locales_dir: مسیر دایرکتوری حاوی فایل‌های ترجمه
    """
    _localization.load_languages(locales_dir)

def set_default_language(language: str) -> None:
    """
    تنظیم زبان پیش‌فرض.
    
    پارامترها:
        language: کد زبان
    """
    _localization.set_default_language(language)

def get_message(key: str, language: Optional[str] = None, **kwargs) -> str:
    """
    دریافت پیام ترجمه شده.
    
    پارامترها:
        key: کلید پیام
        language: کد زبان (اگر None باشد، از زبان پیش‌فرض استفاده می‌شود)
        **kwargs: پارامترهای جایگزینی در رشته
        
    بازگشت:
        str: پیام ترجمه شده یا کلید اصلی در صورت عدم وجود ترجمه
    """
    message = _localization.get_message(key, language)
    
    # اعمال پارامترهای جایگزینی
    if kwargs:
        try:
            return message.format(**kwargs)
        except KeyError as e:
            logger.error(f"خطا در جایگزینی پارامتر‌ها در پیام '{key}': {str(e)}")
    
    return message

# تابع get_text به عنوان نام مستعار برای get_message اضافه شده است
def get_text(key: str, language: Optional[str] = None, **kwargs) -> str:
    """
    دریافت متن ترجمه شده (نام مستعار برای get_message).
    
    پارامترها:
        key: کلید متن
        language: کد زبان (اگر None باشد، از زبان پیش‌فرض استفاده می‌شود)
        **kwargs: پارامترهای جایگزینی در رشته
        
    بازگشت:
        str: متن ترجمه شده یا کلید اصلی در صورت عدم وجود ترجمه
    """
    return get_message(key, language, **kwargs)

def get_all_messages(language: Optional[str] = None) -> Dict[str, str]:
    """
    دریافت تمام پیام‌های یک زبان.
    
    پارامترها:
        language: کد زبان (اگر None باشد، از زبان پیش‌فرض استفاده می‌شود)
        
    بازگشت:
        Dict[str, str]: دیکشنری حاوی تمام پیام‌های زبان
    """
    return _localization.get_all_messages(language)

def get_available_languages() -> list:
    """
    دریافت لیست زبان‌های موجود.
    
    بازگشت:
        list: لیست کدهای زبان‌های موجود
    """
    return _localization.available_languages

def reload(locales_dir: str = 'locales') -> None:
    """
    بارگذاری مجدد فایل‌های ترجمه.
    
    پارامترها:
        locales_dir: مسیر دایرکتوری حاوی فایل‌های ترجمه
    """
    _localization.reload(locales_dir)
    
def set_language(language: str) -> None:
    """
    تنظیم زبان پیش‌فرض برنامه.
    
    این تابع یک نام مستعار برای set_default_language است.
    
    پارامترها:
        language: کد زبان
    """
    _localization.set_default_language(language)    
    
def format_number(number: float, language: Optional[str] = None, decimal_places: int = 2) -> str:
    """
    فرمت‌بندی عدد بر اساس زبان انتخابی

    پارامترها:
        number: عدد مورد نظر برای فرمت‌بندی
        language: کد زبان (اختیاری)
        decimal_places: تعداد اعشار (پیش‌فرض 2)

    بازگشت:
        str: عدد فرمت‌بندی شده
    """
    try:
        # برای فارسی از اعداد فارسی استفاده می‌شود
        if language == 'fa' or (language is None and _localization.default_language == 'fa'):
            # تبدیل اعداد به فارسی
            fa_digits = '۰۱۲۳۴۵۶۷۸۹'
            formatted = f"{number:.{decimal_places}f}".translate(str.maketrans('0123456789.', fa_digits + '٫'))
        else:
            # برای سایر زبان‌ها از فرمت استاندارد استفاده می‌شود
            formatted = f"{number:.{decimal_places}f}"
        
        return formatted
    except Exception as e:
        logger.error(f"خطا در فرمت‌بندی عدد: {str(e)}")
        return str(number)

def translate_error(error_key: str, language: Optional[str] = None, **kwargs) -> str:
    """
    ترجمه خطا با کلید مشخص

    پارامترها:
        error_key: کلید خطا
        language: کد زبان (اختیاری)
        **kwargs: پارامترهای جایگزینی در رشته خطا

    بازگشت:
        str: متن خطای ترجمه شده
    """
    try:
        return get_message(f"error.{error_key}", language, **kwargs)
    except Exception as e:
        logger.error(f"خطا در ترجمه خطا: {str(e)}")
        return error_key