#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول مدیریت کش.

این ماژول مسئول مدیریت کش داده‌ها در حافظه است و با استفاده از آن می‌توان
از فراخوانی‌های تکراری API یا محاسبات سنگین جلوگیری کرد.

تاریخ ایجاد: ۱۴۰۴/۰۱/۰۷
"""

import logging
import time
import threading
import json
import os
import hashlib
from typing import Dict, Any, Optional, Callable, Tuple

logger = logging.getLogger(__name__)

class CacheExpiry:
    """ثابت‌های زمان انقضای کش."""
    ONE_MINUTE = 60
    FIVE_MINUTES = 300
    TEN_MINUTES = 600
    THIRTY_MINUTES = 1800
    ONE_HOUR = 3600
    TWO_HOURS = 7200
    FOUR_HOURS = 14400
    EIGHT_HOURS = 28800
    TWELVE_HOURS = 43200
    ONE_DAY = 86400
    TWO_DAYS = 172800
    ONE_WEEK = 604800
    TWO_WEEKS = 1209600
    ONE_MONTH = 2592000

class Cache:
    """
    کلاس مدیریت کش داده‌ها در حافظه.
    """
    
    def __init__(self, default_ttl: int = 3600):
        """
        مقداردهی اولیه کلاس کش.
        
        پارامترها:
            default_ttl: زمان پیش‌فرض نگهداری کش به ثانیه
        """
        self.cache: Dict[str, Tuple[Any, float]] = {}  # کلید -> (مقدار، زمان انقضا)
        self.default_ttl = default_ttl  # زمان پیش‌فرض نگهداری کش
        self.lock = threading.RLock()  # قفل برای دسترسی همزمان
        
        # راه‌اندازی تایمر برای پاکسازی خودکار
        self.cleanup_timer = threading.Timer(300, self._auto_cleanup)  # هر ۵ دقیقه
        self.cleanup_timer.daemon = True
        self.cleanup_timer.start()
        
        logger.info("سیستم کش با موفقیت راه‌اندازی شد.")
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        افزودن یا به‌روزرسانی مقدار در کش.
        
        پارامترها:
            key: کلید کش
            value: مقدار مورد نظر
            ttl: زمان نگهداری به ثانیه (اگر None باشد، از مقدار پیش‌فرض استفاده می‌شود)
        """
        # محاسبه زمان انقضا
        expiry_time = time.time() + (ttl if ttl is not None else self.default_ttl)
        
        with self.lock:
            self.cache[key] = (value, expiry_time)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        دریافت مقدار از کش.
        
        پارامترها:
            key: کلید کش
            default: مقدار پیش‌فرض در صورت عدم وجود یا منقضی شدن کش
            
        بازگشت:
            Any: مقدار کش شده یا مقدار پیش‌فرض
        """
        with self.lock:
            if key not in self.cache:
                return default
            
            value, expiry_time = self.cache[key]
            
            # بررسی انقضا
            if time.time() > expiry_time:
                del self.cache[key]
                return default
            
            return value
    
    def delete(self, key: str) -> bool:
        """
        حذف مقدار از کش.
        
        پارامترها:
            key: کلید کش
            
        بازگشت:
            bool: True اگر کلید موجود بود و حذف شد، False در غیر این صورت
        """
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """
        بررسی وجود و معتبر بودن کلید در کش.
        
        پارامترها:
            key: کلید کش
            
        بازگشت:
            bool: True اگر کلید موجود و معتبر باشد، False در غیر این صورت
        """
        with self.lock:
            if key not in self.cache:
                return False
            
            _, expiry_time = self.cache[key]
            if time.time() > expiry_time:
                del self.cache[key]
                return False
            
            return True
    
    def clear(self) -> None:
        """
        پاکسازی کامل کش.
        """
        with self.lock:
            self.cache.clear()
            logger.info("کش کاملاً پاکسازی شد.")
    
    def _auto_cleanup(self) -> None:
        """
        پاکسازی خودکار مقادیر منقضی شده.
        این تابع به صورت خودکار و به صورت دوره‌ای اجرا می‌شود.
        """
        current_time = time.time()
        expired_keys = []
        
        try:
            with self.lock:
                # یافتن کلیدهای منقضی شده
                for key, (_, expiry_time) in self.cache.items():
                    if current_time > expiry_time:
                        expired_keys.append(key)
                
                # حذف کلیدهای منقضی شده
                for key in expired_keys:
                    del self.cache[key]
            
            if expired_keys:
                logger.debug(f"{len(expired_keys)} کلید منقضی شده از کش حذف شدند.")
        
        except Exception as e:
            logger.error(f"خطا در پاکسازی خودکار کش: {str(e)}")
        
        finally:
            # تنظیم مجدد تایمر
            self.cleanup_timer = threading.Timer(300, self._auto_cleanup)
            self.cleanup_timer.daemon = True
            self.cleanup_timer.start()
    
    def __del__(self) -> None:
        """
        پاکسازی منابع هنگام حذف شیء.
        """
        try:
            if hasattr(self, 'cleanup_timer') and self.cleanup_timer:
                self.cleanup_timer.cancel()
        except:
            pass

# اضافه کردن alias برای کلاس Cache به عنوان MemoryCache
# این کار مشکل واردسازی را حل می‌کند
MemoryCache = Cache

def cached(ttl: Optional[int] = None):
    """
    دکوراتور برای کش کردن نتایج توابع.
    
    پارامترها:
        ttl: زمان نگهداری به ثانیه (اگر None باشد، از مقدار پیش‌فرض استفاده می‌شود)
        
    بازگشت:
        تابع دکوراتور
    
    مثال استفاده:
        @cached(ttl=60)
        def expensive_function(param1, param2):
            # محاسبات سنگین
            return result
    """
    def decorator(func: Callable):
        # ایجاد یک نمونه کش اختصاصی برای هر تابع
        func_cache = Cache(default_ttl=ttl if ttl is not None else 3600)
        
        def wrapper(*args, **kwargs):
            # ایجاد کلید کش بر اساس نام تابع و پارامترها
            cache_key = f"{func.__name__}:{json.dumps(args, sort_keys=True)}:{json.dumps(sorted(kwargs.items()), sort_keys=True)}"
            
            # بررسی وجود مقدار در کش
            cached_result = func_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"نتیجه از کش برای تابع {func.__name__} بازگردانده شد")
                return cached_result
            
            # اجرای تابع و ذخیره نتیجه در کش
            result = func(*args, **kwargs)
            func_cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    
    return decorator


class DiskCache:
    """
    کلاس مدیریت کش داده‌ها روی دیسک.
    این کلاس برای کش کردن داده‌های بزرگ یا داده‌هایی که باید پس از راه‌اندازی مجدد برنامه حفظ شوند استفاده می‌شود.
    """
    
    def __init__(self, cache_dir: str = 'cache', default_ttl: int = 3600):
        """
        مقداردهی اولیه کلاس کش دیسک.
        
        پارامترها:
            cache_dir: مسیر دایرکتوری کش
            default_ttl: زمان پیش‌فرض نگهداری کش به ثانیه
        """
        self.cache_dir = cache_dir
        self.default_ttl = default_ttl
        self.lock = threading.RLock()
        
        # اطمینان از وجود دایرکتوری کش
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # پاکسازی فایل‌های منقضی شده در زمان راه‌اندازی
        self._cleanup()
        
        # راه‌اندازی تایمر برای پاکسازی خودکار
        self.cleanup_timer = threading.Timer(1800, self._auto_cleanup)  # هر ۳۰ دقیقه
        self.cleanup_timer.daemon = True
        self.cleanup_timer.start()
        
        logger.info(f"سیستم کش دیسک در مسیر '{cache_dir}' راه‌اندازی شد.")
    
    def _get_cache_path(self, key: str) -> str:
        """
        دریافت مسیر فایل کش برای یک کلید.
        
        پارامترها:
            key: کلید کش
            
        بازگشت:
            str: مسیر فایل کش
        """
        # هش کردن کلید برای ایجاد نام فایل امن
        hashed_key = hashlib.md5(key.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, f"{hashed_key}.cache")
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        افزودن یا به‌روزرسانی مقدار در کش دیسک.
        
        پارامترها:
            key: کلید کش
            value: مقدار مورد نظر
            ttl: زمان نگهداری به ثانیه (اگر None باشد، از مقدار پیش‌فرض استفاده می‌شود)
        """
        # محاسبه زمان انقضا
        expiry_time = time.time() + (ttl if ttl is not None else self.default_ttl)
        
        # ساختار داده‌ای کش
        cache_data = {
            'expiry_time': expiry_time,
            'value': value
        }
        
        cache_path = self._get_cache_path(key)
        
        with self.lock:
            try:
                with open(cache_path, 'wb') as f:
                    # استفاده از pickle برای سریالیزاسیون داده‌ها
                    import pickle
                    pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            except Exception as e:
                logger.error(f"خطا در ذخیره‌سازی کش دیسک: {str(e)}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        دریافت مقدار از کش دیسک.
        
        پارامترها:
            key: کلید کش
            default: مقدار پیش‌فرض در صورت عدم وجود یا منقضی شدن کش
            
        بازگشت:
            Any: مقدار کش شده یا مقدار پیش‌فرض
        """
        cache_path = self._get_cache_path(key)
        
        with self.lock:
            if not os.path.exists(cache_path):
                return default
            
            try:
                with open(cache_path, 'rb') as f:
                    import pickle
                    cache_data = pickle.load(f)
                
                # بررسی انقضا
                if time.time() > cache_data['expiry_time']:
                    # حذف فایل منقضی شده
                    os.remove(cache_path)
                    return default
                
                return cache_data['value']
            except Exception as e:
                logger.error(f"خطا در بازیابی کش دیسک: {str(e)}")
                
                # در صورت خطا، فایل کش را حذف می‌کنیم
                try:
                    os.remove(cache_path)
                except:
                    pass
                
                return default
    
    def delete(self, key: str) -> bool:
        """
        حذف مقدار از کش دیسک.
        
        پارامترها:
            key: کلید کش
            
        بازگشت:
            bool: True اگر کلید موجود بود و حذف شد، False در غیر این صورت
        """
        cache_path = self._get_cache_path(key)
        
        with self.lock:
            if os.path.exists(cache_path):
                try:
                    os.remove(cache_path)
                    return True
                except Exception as e:
                    logger.error(f"خطا در حذف کش دیسک: {str(e)}")
            
            return False
    
    def exists(self, key: str) -> bool:
        """
        بررسی وجود و معتبر بودن کلید در کش دیسک.
        
        پارامترها:
            key: کلید کش
            
        بازگشت:
            bool: True اگر کلید موجود و معتبر باشد، False در غیر این صورت
        """
        cache_path = self._get_cache_path(key)
        
        with self.lock:
            if not os.path.exists(cache_path):
                return False
            
            try:
                with open(cache_path, 'rb') as f:
                    import pickle
                    cache_data = pickle.load(f)
                
                # بررسی انقضا
                if time.time() > cache_data['expiry_time']:
                    # حذف فایل منقضی شده
                    os.remove(cache_path)
                    return False
                
                return True
            except Exception:
                # در صورت خطا، فایل کش را حذف می‌کنیم
                try:
                    os.remove(cache_path)
                except:
                    pass
                
                return False
    
    def clear(self) -> None:
        """
        پاکسازی کامل کش دیسک.
        """
        with self.lock:
            try:
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith('.cache'):
                        os.remove(os.path.join(self.cache_dir, filename))
                logger.info("کش دیسک کاملاً پاکسازی شد.")
            except Exception as e:
                logger.error(f"خطا در پاکسازی کش دیسک: {str(e)}")
    
    def _cleanup(self) -> None:
        """
        پاکسازی فایل‌های کش منقضی شده.
        """
        current_time = time.time()
        
        try:
            for filename in os.listdir(self.cache_dir):
                if not filename.endswith('.cache'):
                    continue
                
                cache_path = os.path.join(self.cache_dir, filename)
                
                try:
                    with open(cache_path, 'rb') as f:
                        import pickle
                        cache_data = pickle.load(f)
                    
                    # حذف فایل‌های منقضی شده
                    if current_time > cache_data['expiry_time']:
                        os.remove(cache_path)
                except Exception:
                    # در صورت خطا، فایل کش را حذف می‌کنیم
                    try:
                        os.remove(cache_path)
                    except:
                        pass
        except Exception as e:
            logger.error(f"خطا در پاکسازی کش دیسک: {str(e)}")
    
    def _auto_cleanup(self) -> None:
        """
        پاکسازی خودکار فایل‌های منقضی شده.
        این تابع به صورت خودکار و به صورت دوره‌ای اجرا می‌شود.
        """
        try:
            self._cleanup()
        finally:
            # تنظیم مجدد تایمر
            self.cleanup_timer = threading.Timer(1800, self._auto_cleanup)
            self.cleanup_timer.daemon = True
            self.cleanup_timer.start()
    
    def __del__(self) -> None:
        """
        پاکسازی منابع هنگام حذف شیء.
        """
        try:
            if hasattr(self, 'cleanup_timer') and self.cleanup_timer:
                self.cleanup_timer.cancel()
        except:
            pass


class CacheManager:
    """
    کلاس مدیریت انواع مختلف کش.
    این کلاس امکان استفاده یکپارچه از انواع مختلف کش را فراهم می‌کند.
    """
    
    def __init__(self, memory_ttl: int = 3600, disk_ttl: int = 86400, disk_cache_dir: str = 'cache'):
        """
        مقداردهی اولیه مدیریت کش.
        
        پارامترها:
            memory_ttl: زمان پیش‌فرض نگهداری کش حافظه به ثانیه
            disk_ttl: زمان پیش‌فرض نگهداری کش دیسک به ثانیه
            disk_cache_dir: مسیر دایرکتوری کش دیسک
        """
        self.memory_cache = Cache(default_ttl=memory_ttl)
        self.disk_cache = DiskCache(cache_dir=disk_cache_dir, default_ttl=disk_ttl)
        self.default_storage = 'memory'  # انتخاب پیش‌فرض محل ذخیره‌سازی
        
        logger.info("سیستم مدیریت کش راه‌اندازی شد.")
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, storage: str = None) -> None:
        """
        افزودن یا به‌روزرسانی مقدار در کش.
        
        پارامترها:
            key: کلید کش
            value: مقدار مورد نظر
            ttl: زمان نگهداری به ثانیه (اگر None باشد، از مقدار پیش‌فرض استفاده می‌شود)
            storage: محل ذخیره‌سازی ('memory' یا 'disk') - اگر None باشد، از پیش‌فرض استفاده می‌شود
        """
        storage = storage or self.default_storage
        
        if storage == 'disk':
            self.disk_cache.set(key, value, ttl)
        else:
            self.memory_cache.set(key, value, ttl)
    
    def get(self, key: str, default: Any = None, storage: str = None) -> Any:
        """
        دریافت مقدار از کش.
        
        پارامترها:
            key: کلید کش
            default: مقدار پیش‌فرض در صورت عدم وجود یا منقضی شدن کش
            storage: محل ذخیره‌سازی ('memory' یا 'disk') - اگر None باشد، از پیش‌فرض استفاده می‌شود
            
        بازگشت:
            Any: مقدار کش شده یا مقدار پیش‌فرض
        """
        storage = storage or self.default_storage
        
        if storage == 'disk':
            return self.disk_cache.get(key, default)
        else:
            return self.memory_cache.get(key, default)
    
    def get_from_both(self, key: str, default: Any = None) -> Tuple[Any, str]:
        """
        دریافت مقدار از هر دو نوع کش (اولویت با حافظه).
        
        پارامترها:
            key: کلید کش
            default: مقدار پیش‌فرض در صورت عدم وجود یا منقضی شدن کش
            
        بازگشت:
            Tuple[Any, str]: مقدار کش شده و منبع آن ('memory', 'disk' یا 'default')
        """
        # ابتدا بررسی کش حافظه
        memory_value = self.memory_cache.get(key)
        if memory_value is not None:
            return memory_value, 'memory'
        
        # سپس بررسی کش دیسک
        disk_value = self.disk_cache.get(key)
        if disk_value is not None:
            # ذخیره در کش حافظه برای دسترسی سریع‌تر در آینده
            self.memory_cache.set(key, disk_value)
            return disk_value, 'disk'
        
        return default, 'default'
    
    def delete(self, key: str, storage: str = None) -> bool:
        """
        حذف مقدار از کش.
        
        پارامترها:
            key: کلید کش
            storage: محل ذخیره‌سازی ('memory', 'disk' یا 'all') - اگر None باشد، از پیش‌فرض استفاده می‌شود
            
        بازگشت:
            bool: True اگر کلید در حداقل یکی از کش‌ها موجود بود و حذف شد
        """
        storage = storage or self.default_storage
        result = False
        
        if storage in ('memory', 'all'):
            result = self.memory_cache.delete(key) or result
        
        if storage in ('disk', 'all'):
            result = self.disk_cache.delete(key) or result
        
        return result
    
    def exists(self, key: str, storage: str = None) -> bool:
        """
        بررسی وجود و معتبر بودن کلید در کش.
        
        پارامترها:
            key: کلید کش
            storage: محل ذخیره‌سازی ('memory', 'disk' یا 'any') - اگر None باشد، از پیش‌فرض استفاده می‌شود
            
        بازگشت:
            bool: True اگر کلید موجود و معتبر باشد، False در غیر این صورت
        """
        storage = storage or self.default_storage
        
        if storage == 'memory':
            return self.memory_cache.exists(key)
        elif storage == 'disk':
            return self.disk_cache.exists(key)
        elif storage == 'any':
            return self.memory_cache.exists(key) or self.disk_cache.exists(key)
        
        return False
    
    def clear(self, storage: str = 'all') -> None:
        """
        پاکسازی کش.
        
        پارامترها:
            storage: محل ذخیره‌سازی ('memory', 'disk' یا 'all')
        """
        if storage in ('memory', 'all'):
            self.memory_cache.clear()
        
        if storage in ('disk', 'all'):
            self.disk_cache.clear()
        
        logger.info(f"پاکسازی کش ({storage}) انجام شد.")
    
    def set_default_storage(self, storage: str) -> None:
        """
        تنظیم محل پیش‌فرض ذخیره‌سازی.
        
        پارامترها:
            storage: محل ذخیره‌سازی ('memory' یا 'disk')
        """
        if storage not in ('memory', 'disk'):
            raise ValueError("محل ذخیره‌سازی باید 'memory' یا 'disk' باشد.")
        
        self.default_storage = storage
        logger.info(f"محل پیش‌فرض ذخیره‌سازی کش به '{storage}' تغییر یافت.")


def disk_cached(ttl: Optional[int] = None, cache_dir: str = 'cache'):
    """
    دکوراتور برای کش کردن نتایج توابع در دیسک.
    
    پارامترها:
        ttl: زمان نگهداری به ثانیه (اگر None باشد، از مقدار پیش‌فرض استفاده می‌شود)
        cache_dir: مسیر دایرکتوری کش
        
    بازگشت:
        تابع دکوراتور
    
    مثال استفاده:
        @disk_cached(ttl=3600)
        def expensive_function(param1, param2):
            # محاسبات سنگین
            return result
    """
    def decorator(func: Callable):
        # ایجاد یک نمونه کش دیسک اختصاصی برای هر تابع
        func_cache = DiskCache(cache_dir=os.path.join(cache_dir, func.__name__), default_ttl=ttl if ttl is not None else 86400)
        
        def wrapper(*args, **kwargs):
            # ایجاد کلید کش بر اساس نام تابع و پارامترها
            cache_key = f"{func.__name__}:{json.dumps(args, sort_keys=True)}:{json.dumps(sorted(kwargs.items()), sort_keys=True)}"
            
            # بررسی وجود مقدار در کش
            cached_result = func_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"نتیجه از کش دیسک برای تابع {func.__name__} بازگردانده شد")
                return cached_result
            
            # اجرای تابع و ذخیره نتیجه در کش
            result = func(*args, **kwargs)
            func_cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    
    return decorator