#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول مدیریت تنظیمات ربات.

این ماژول مسئول بارگذاری تنظیمات از فایل .env و سایر منابع است.
همچنین امکان تنظیم پیکربندی‌های پیش‌فرض و بررسی صحت تنظیمات را فراهم می‌کند.

تاریخ ایجاد: ۱۴۰۴/۰۱/۰۷
"""

import os
import logging
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# تنظیمات پیش‌فرض
DEFAULT_CONFIG = {
    'TIMEZONE': 'Asia/Tehran',
    'DEFAULT_LANGUAGE': 'fa',
    'AVAILABLE_LANGUAGES': ['fa', 'en', 'ar', 'tr', 'hi', 'zh'],
    'LOG_LEVEL': 'INFO',
    'ADMIN_IDS': [],  # شناسه‌های ادمین‌ها
    'CACHE_TTL': 3600,  # زمان نگهداری کش به ثانیه
    'DB_TYPE': 'sqlite',  # نوع پایگاه داده (sqlite, mysql, postgresql)
    'MAX_CONNECTIONS': 10,  # حداکثر تعداد اتصالات همزمان به پایگاه داده
    'REQUEST_TIMEOUT': 30,  # حداکثر زمان انتظار برای درخواست‌های API
    'ENABLE_ANALYTICS': False,  # فعال‌سازی آنالیتیکس
    'BACKUP_ENABLED': True,  # فعال‌سازی پشتیبان‌گیری خودکار
    'BACKUP_INTERVAL': 86400,  # فاصله زمانی پشتیبان‌گیری (روزانه)
    'MAX_MESSAGE_LENGTH': 4096,  # حداکثر طول پیام در تلگرام
    'SUBSCRIPTION_PLANS': {
        'basic': {
            'price': 100000,  # تومان
            'duration': 30,  # روز
            'features': ['feature1', 'feature2']
        },
        'premium': { 
            'price': 250000,
            'duration': 30,
            'features': ['feature1', 'feature2', 'feature3', 'feature4']
        },
        'vip': {
            'price': 500000,
            'duration': 90,
            'features': ['feature1', 'feature2', 'feature3', 'feature4', 'feature5']
        }
    }
}


class Config:
    """
    کلاس مدیریت تنظیمات برنامه.
    این کلاس مسئول بارگذاری، ذخیره‌سازی و دسترسی به تنظیمات برنامه است.
    """
    _instance = None

    def __new__(cls, env_path: str = '.env'):
        """
        الگوی Singleton برای اطمینان از وجود تنها یک نمونه از تنظیمات
        
        Args:
            env_path: مسیر فایل .env
        """
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, env_path: str = '.env'):
        """
        مقداردهی اولیه کلاس Config
        
        Args:
            env_path: مسیر فایل .env
        """
        # از مقداردهی مجدد جلوگیری می‌کنیم
        if self._initialized:
            return
            
        self._config = DEFAULT_CONFIG.copy()
        self._env_path = env_path
        
        # بارگذاری تنظیمات از منابع مختلف
        self._load_env_variables()
        
        # علامت‌گذاری مقداردهی اولیه
        self._initialized = True
        
        logger.debug("کلاس Config با موفقیت مقداردهی شد.")

    def _load_env_variables(self) -> None:
        """
        بارگذاری متغیرهای محیطی از فایل .env
        """
        # بارگذاری فایل .env
        if os.path.exists(self._env_path):
            load_dotenv(self._env_path)
            logger.info(f"فایل .env از مسیر {self._env_path} بارگذاری شد.")
        else:
            logger.warning(f"فایل .env در مسیر {self._env_path} یافت نشد.")
        
        # بارگذاری متغیرهای محیطی مهم
        env_vars = {
            'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
            'DATABASE_URL': os.getenv('DATABASE_URL'),
            'ADMIN_IDS': os.getenv('ADMIN_IDS', ''),
            'TIMEZONE': os.getenv('TIMEZONE'),
            'DEFAULT_LANGUAGE': os.getenv('DEFAULT_LANGUAGE'),
            'LOG_LEVEL': os.getenv('LOG_LEVEL'),
            'PAYMENT_API_KEY': os.getenv('PAYMENT_API_KEY'),
            'CRYPTO_PAYMENT_API_KEY': os.getenv('CRYPTO_PAYMENT_API_KEY'),
            'BINANCE_API_KEY': os.getenv('BINANCE_API_KEY'),
            'BINANCE_SECRET_KEY': os.getenv('BINANCE_SECRET_KEY'),
            'KUCOIN_API_KEY': os.getenv('KUCOIN_API_KEY'),
            'KUCOIN_SECRET_KEY': os.getenv('KUCOIN_SECRET_KEY'),
            'KUCOIN_PASSPHRASE': os.getenv('KUCOIN_PASSPHRASE'),
            'ENABLE_ML': os.getenv('ENABLE_ML', 'False'),
            'ML_MODEL_PATH': os.getenv('ML_MODEL_PATH'),
            'ENCRYPTION_KEY': os.getenv('ENCRYPTION_KEY'),
            'CACHE_TTL': os.getenv('CACHE_TTL'),
            'BACKUP_ENABLED': os.getenv('BACKUP_ENABLED'),
            'BACKUP_INTERVAL': os.getenv('BACKUP_INTERVAL'),
            'SUBSCRIPTION_PLANS': os.getenv('SUBSCRIPTION_PLANS'),
        }
        
        # بارگذاری مقادیر غیر-خالی
        for key, value in env_vars.items():
            if value is not None:
                if key == 'ADMIN_IDS' and value:
                    try:
                        # تبدیل رشته به لیست اعداد
                        self._config[key] = [int(admin_id.strip()) for admin_id in value.split(',') if admin_id.strip()]
                    except ValueError:
                        logger.warning(f"مقدار نامعتبر برای ADMIN_IDS: {value}")
                        self._config[key] = []
                elif key in ['ENABLE_ML', 'BACKUP_ENABLED']:
                    self._config[key] = value.lower() in ['true', '1', 'yes', 'y']
                elif key in ['CACHE_TTL', 'BACKUP_INTERVAL']:
                    try:
                        self._config[key] = int(value)
                    except ValueError:
                        logger.warning(f"مقدار نامعتبر برای {key}: {value}")
                elif key == 'SUBSCRIPTION_PLANS' and value:
                    try:
                        self._config[key] = json.loads(value)
                    except json.JSONDecodeError:
                        logger.warning(f"مقدار JSON نامعتبر برای SUBSCRIPTION_PLANS: {value}")
                else:
                    self._config[key] = value
    
    def load_json_config(self, file_path: str) -> None:
        """
        بارگذاری تنظیمات از فایل JSON
        
        Args:
            file_path: مسیر فایل JSON
            
        Raises:
            FileNotFoundError: اگر فایل پیدا نشود
            json.JSONDecodeError: اگر فایل JSON معتبر نباشد
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                json_config = json.load(file)
                self._config.update(json_config)
                logger.info(f"تنظیمات از فایل JSON در مسیر {file_path} بارگذاری شد.")
        except FileNotFoundError:
            logger.error(f"فایل تنظیمات یافت نشد: {file_path}")
            raise
        except json.JSONDecodeError:
            logger.error(f"فایل تنظیمات JSON نامعتبر است: {file_path}")
            raise
    
    def validate(self) -> bool:
        """
        بررسی صحت تنظیمات ضروری
        
        Returns:
            bool: True اگر تنظیمات معتبر باشند، False در غیر این صورت
        """
        required_keys = ['TELEGRAM_BOT_TOKEN']
        
        for key in required_keys:
            if key not in self._config or not self._config[key]:
                logger.error(f"تنظیم ضروری '{key}' یافت نشد یا خالی است.")
                return False
        
        logger.debug("بررسی صحت تنظیمات با موفقیت انجام شد.")
        return True
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        دریافت مقدار یک تنظیم خاص با پشتیبانی از مقدار پیش‌فرض
        
        Args:
            key: کلید مورد نظر
            default: مقدار پیش‌فرض در صورت عدم وجود کلید
            
        Returns:
            Any: مقدار تنظیم یا مقدار پیش‌فرض
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        تنظیم مقدار یک کلید
        
        Args:
            key: کلید مورد نظر
            value: مقدار جدید
        """
        self._config[key] = value
        logger.debug(f"مقدار '{key}' به '{value}' تنظیم شد.")
    
    def get_all(self) -> Dict[str, Any]:
        """
        دریافت تمام تنظیمات
        
        Returns:
            Dict[str, Any]: دیکشنری حاوی تمام تنظیمات
        """
        return self._config.copy()
    
    def get_list(self, key: str, default: list = None) -> list:
        """
        دریافت یک تنظیم به عنوان لیست
        
        Args:
            key: کلید مورد نظر
            default: مقدار پیش‌فرض در صورت عدم وجود کلید
            
        Returns:
            list: مقدار تنظیم به عنوان لیست
        """
        value = self.get(key, default)
        
        if value is None:
            return []
        
        if isinstance(value, list):
            return value
        
        if isinstance(value, str):
            # تبدیل رشته جدا شده با کاما به لیست
            return [item.strip() for item in value.split(',') if item.strip()]
        
        # تبدیل مقادیر دیگر به لیست
        return [value]
    
    def get_dict(self, key: str, default: dict = None) -> dict:
        """
        دریافت یک تنظیم به عنوان دیکشنری
        
        Args:
            key: کلید مورد نظر
            default: مقدار پیش‌فرض در صورت عدم وجود کلید
            
        Returns:
            dict: مقدار تنظیم به عنوان دیکشنری
        """
        value = self.get(key, default)
        
        if value is None:
            return {}
        
        if isinstance(value, dict):
            return value
        
        if isinstance(value, str):
            try:
                # تبدیل رشته JSON به دیکشنری
                return json.loads(value)
            except json.JSONDecodeError:
                logger.warning(f"مقدار '{key}' یک JSON معتبر نیست: {value}")
                return {}
        
        logger.warning(f"مقدار '{key}' قابل تبدیل به دیکشنری نیست: {value}")
        return {}
    
    def get_int(self, key: str, default: int = 0) -> int:
        """
        دریافت یک تنظیم به عنوان عدد صحیح
        
        Args:
            key: کلید مورد نظر
            default: مقدار پیش‌فرض در صورت عدم وجود کلید
            
        Returns:
            int: مقدار تنظیم به عنوان عدد صحیح
        """
        value = self.get(key, default)
        
        if isinstance(value, int):
            return value
        
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"مقدار '{key}' قابل تبدیل به عدد صحیح نیست: {value}")
            return default
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """
        دریافت یک تنظیم به عنوان عدد اعشاری
        
        Args:
            key: کلید مورد نظر
            default: مقدار پیش‌فرض در صورت عدم وجود کلید
            
        Returns:
            float: مقدار تنظیم به عنوان عدد اعشاری
        """
        value = self.get(key, default)
        
        if isinstance(value, float):
            return value
        
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"مقدار '{key}' قابل تبدیل به عدد اعشاری نیست: {value}")
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        دریافت یک تنظیم به عنوان مقدار منطقی
        
        Args:
            key: کلید مورد نظر
            default: مقدار پیش‌فرض در صورت عدم وجود کلید
            
        Returns:
            bool: مقدار تنظیم به عنوان مقدار منطقی
        """
        value = self.get(key, default)
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            return value.lower() in ['true', '1', 'yes', 'y']
        
        if isinstance(value, (int, float)):
            return bool(value)
        
        return default
    
    def to_env_format(self) -> str:
        """
        تبدیل تنظیمات به قالب فایل .env
        
        Returns:
            str: محتوای فایل .env
        """
        lines = []
        
        for key, value in self._config.items():
            if isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False)
            
            lines.append(f"{key}={value}")
        
        return '\n'.join(lines)
    
    def save_to_env(self, file_path: str = None) -> bool:
        """
        ذخیره تنظیمات در فایل .env
        
        Args:
            file_path: مسیر فایل .env (اختیاری)
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if file_path is None:
            file_path = self._env_path
        
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(self.to_env_format())
            
            logger.info(f"تنظیمات در فایل .env در مسیر {file_path} ذخیره شد.")
            return True
        except Exception as e:
            logger.error(f"خطا در ذخیره تنظیمات: {str(e)}")
            return False


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    بارگذاری تنظیمات از منابع مختلف و ترکیب آن‌ها
    
    Args:
        config_path: مسیر فایل تنظیمات JSON (اختیاری)
        
    Returns:
        Dict[str, Any]: دیکشنری حاوی تنظیمات نهایی
    """
    # ایجاد نمونه‌ای از کلاس Config
    config_manager = Config()
    
    # افزودن تنظیمات از فایل JSON (در صورت وجود)
    if config_path and os.path.exists(config_path):
        try:
            config_manager.load_json_config(config_path)
            logger.info(f"تنظیمات از فایل {config_path} بارگذاری شد.")
        except Exception as e:
            logger.error(f"خطا در بارگذاری فایل تنظیمات: {str(e)}")
    
    # بررسی صحت تنظیمات
    if not config_manager.validate():
        logger.warning("برخی تنظیمات ضروری یافت نشدند!")
    
    return config_manager.get_all()


def get_db_path(args_db_path: Optional[str] = None) -> str:
    """
    دریافت مسیر فایل پایگاه داده
    
    Args:
        args_db_path: مسیر ارائه شده در آرگومان‌ها (اختیاری)
        
    Returns:
        str: مسیر فایل پایگاه داده
    """
    if args_db_path:
        return args_db_path
    
    # دریافت از Config
    config = Config()
    
    # بررسی وجود DATABASE_URL کامل
    database_url = config.get('DATABASE_URL')
    if database_url and database_url.startswith('sqlite:///'):
        # استخراج مسیر از DATABASE_URL
        db_path = database_url.replace('sqlite:///', '')
    else:
        # استفاده از مسیر پیش‌فرض
        db_path = config.get('DB_PATH', 'data/db/bot.db')
    
    return db_path