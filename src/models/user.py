#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
این ماژول شامل کلاس مدل User برای مدیریت اطلاعات کاربران ربات است.
"""


from datetime import timezone
import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from src.utils.timezone_utils import get_current_datetime, timezone
import json

from src.utils.security import (
    encrypt_sensitive_data, 
    decrypt_sensitive_data
)
from src.utils.timezone_utils import get_user_timezone, convert_to_user_timezone

logger = logging.getLogger('models.user')

class User:
    """
    مدل کاربر برای ذخیره و مدیریت اطلاعات کاربران.
    """
    
    def __init__(self, db, user_id: int):
        """
        مقداردهی اولیه مدل کاربر.
        
        Args:
            db: آبجکت دیتابیس
            user_id: شناسه کاربر تلگرام
        """
        self.db = db
        self.user_id = user_id
        self._data = {}
        self._is_loaded = False
        self._is_new = False
    
    def load(self) -> bool:
        """
        بارگذاری اطلاعات کاربر از دیتابیس.
        
        Returns:
            bool: True در صورت موفقیت، False در صورت عدم وجود کاربر
        """
        try:
            user_data = self.db.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (self.user_id,)
            )
            
            if not user_data:
                self._is_new = True
                self._is_loaded = False
                return False
            
            # تبدیل نتیجه کوئری به دیکشنری
            columns = [column[0] for column in self.db.cursor.description]
            self._data = dict(zip(columns, user_data[0]))
            
            self._is_loaded = True
            return True
            
        except Exception as e:
            logger.error(f"خطا در بارگذاری اطلاعات کاربر {self.user_id}: {e}")
            self._is_loaded = False
            return False
    
    def save(self) -> bool:
        """
        ذخیره تغییرات کاربر در دیتابیس.
        
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        try:
            if not self._is_loaded and not self._is_new:
                logger.error(f"تلاش برای ذخیره کاربر {self.user_id} بدون بارگذاری قبلی")
                return False
            
            if self._is_new:
                # درج رکورد جدید
                columns = list(self._data.keys())
                placeholders = ["?"] * len(columns)
                values = [self._data.get(column) for column in columns]
                
                query = f"INSERT INTO users ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                self.db.execute(query, values)
                
                self._is_new = False
                self._is_loaded = True
                return True
            else:
                # به‌روزرسانی رکورد موجود
                set_clause = ", ".join([f"{column} = ?" for column in self._data.keys() if column != "user_id"])
                values = [self._data.get(column) for column in self._data.keys() if column != "user_id"]
                values.append(self.user_id)  # برای شرط WHERE
                
                query = f"UPDATE users SET {set_clause} WHERE user_id = ?"
                self.db.execute(query, values)
                return True
                
        except Exception as e:
            logger.error(f"خطا در ذخیره اطلاعات کاربر {self.user_id}: {e}")
            return False
    
    @property
    def exists(self) -> bool:
        """
        بررسی وجود کاربر در دیتابیس.
        
        Returns:
            bool: True اگر کاربر وجود داشته باشد، False در غیر این صورت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._is_loaded and not self._is_new
    
    @property
    def is_registered(self) -> bool:
        """
        بررسی ثبت‌نام کامل کاربر.
        
        Returns:
            bool: True اگر کاربر ثبت‌نام کامل را انجام داده باشد، False در غیر این صورت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('is_registered', 0) == 1
    
    @property
    def is_admin(self) -> bool:
        """
        بررسی آیا کاربر ادمین است.
        
        Returns:
            bool: True اگر کاربر ادمین باشد، False در غیر این صورت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('is_admin', 0) == 1
    
    @property
    def is_active(self) -> bool:
        """
        بررسی فعال بودن کاربر.
        
        Returns:
            bool: True اگر کاربر فعال باشد، False در غیر این صورت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('is_active', 0) == 1
    
    @property
    def full_name(self) -> str:
        """
        دریافت نام کامل کاربر.
        
        Returns:
            str: نام کامل کاربر
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('full_name', '')
    
    @full_name.setter
    def full_name(self, value: str) -> None:
        """
        تنظیم نام کامل کاربر.
        
        Args:
            value: نام کامل جدید
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            self._is_new = True
            self._data['user_id'] = self.user_id
            
        self._data['full_name'] = value
    
    @property
    def email(self) -> str:
        """
        دریافت آدرس ایمیل کاربر.
        
        Returns:
            str: آدرس ایمیل کاربر
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('email', '')
    
    @email.setter
    def email(self, value: str) -> None:
        """
        تنظیم آدرس ایمیل کاربر.
        
        Args:
            value: آدرس ایمیل جدید
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            self._is_new = True
            self._data['user_id'] = self.user_id
            
        self._data['email'] = value
    
    @property
    def phone(self) -> str:
        """
        دریافت شماره تلفن کاربر.
        
        Returns:
            str: شماره تلفن کاربر
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('phone', '')
    
    @phone.setter
    def phone(self, value: str) -> None:
        """
        تنظیم شماره تلفن کاربر.
        
        Args:
            value: شماره تلفن جدید
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            self._is_new = True
            self._data['user_id'] = self.user_id
            
        self._data['phone'] = value
    
    @property
    def language_code(self) -> str:
        """
        دریافت کد زبان کاربر.
        
        Returns:
            str: کد زبان کاربر
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('language_code', 'fa')
    
    @language_code.setter
    def language_code(self, value: str) -> None:
        """
        تنظیم کد زبان کاربر.
        
        Args:
            value: کد زبان جدید
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            self._is_new = True
            self._data['user_id'] = self.user_id
            
        self._data['language_code'] = value
    
    @property
    def timezone(self) -> str:
        """
        دریافت منطقه زمانی کاربر.
        
        Returns:
            str: منطقه زمانی کاربر
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('timezone', 'Asia/Tehran')
    
    @timezone.setter
    def timezone(self, value: str) -> None:
        """
        تنظیم منطقه زمانی کاربر.
        
        Args:
            value: منطقه زمانی جدید
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            self._is_new = True
            self._data['user_id'] = self.user_id
            
        self._data['timezone'] = value
    
    @property
    def joined_date(self) -> Optional[datetime]:
        """
        دریافت تاریخ عضویت کاربر.
        
        Returns:
            datetime: تاریخ عضویت کاربر
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        joined_date = self._data.get('joined_date')
        if joined_date is None:
            return None
        
        # تبدیل به آبجکت datetime اگر رشته باشد
        if isinstance(joined_date, str):
            try:
                return datetime.fromisoformat(joined_date)
            except ValueError:
                return None
        
        return joined_date
    
    @property
    def last_activity(self) -> Optional[datetime]:
        """
        دریافت تاریخ آخرین فعالیت کاربر.
        
        Returns:
            datetime: تاریخ آخرین فعالیت کاربر
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        last_activity = self._data.get('last_activity')
        if last_activity is None:
            return None
        
        # تبدیل به آبجکت datetime اگر رشته باشد
        if isinstance(last_activity, str):
            try:
                return datetime.fromisoformat(last_activity)
            except ValueError:
                return None
        
        return last_activity
    
    def update_last_activity(self) -> None:
        """
        به‌روزرسانی زمان آخرین فعالیت کاربر به زمان فعلی.
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            self._is_new = True
            self._data['user_id'] = self.user_id
            
        self._data['last_activity'] = get_current_datetime()
    
    def register(self, full_name: str, email: str, phone: str) -> bool:
        """
        ثبت‌نام کاربر با اطلاعات کامل.
        
        Args:
            full_name: نام کامل
            email: آدرس ایمیل
            phone: شماره تلفن
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            self._is_new = True
            self._data['user_id'] = self.user_id
            self._data['joined_date'] = get_current_datetime()
        
        self._data['full_name'] = full_name
        self._data['email'] = email
        self._data['phone'] = phone
        self._data['is_registered'] = 1
        self._data['registration_date'] = get_current_datetime()
        
        return self.save()
    
    def deactivate(self) -> bool:
        """
        غیرفعال کردن کاربر.
        
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return False
        
        self._data['is_active'] = 0
        return self.save()
    
    def activate(self) -> bool:
        """
        فعال کردن کاربر.
        
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return False
        
        self._data['is_active'] = 1
        return self.save()
    
    def get_notification_settings(self) -> Dict[str, bool]:
        """
        دریافت تنظیمات اطلاع‌رسانی کاربر.
        
        Returns:
            Dict[str, bool]: تنظیمات اطلاع‌رسانی
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return {
            'notify_news': bool(self._data.get('notify_news', 1)),
            'notify_price_alerts': bool(self._data.get('notify_price_alerts', 1)),
            'notify_subscription': bool(self._data.get('notify_subscription', 1))
        }
    
    def update_notification_setting(self, notification_type: str, enabled: bool) -> bool:
        """
        به‌روزرسانی یک تنظیم اطلاع‌رسانی.
        
        Args:
            notification_type: نوع اطلاع‌رسانی
            enabled: فعال یا غیرفعال
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return False
        
        if notification_type not in ('notify_news', 'notify_price_alerts', 'notify_subscription'):
            return False
        
        self._data[notification_type] = 1 if enabled else 0
        return self.save()
    
    def get_active_subscription(self) -> Optional[Dict[str, Any]]:
        """
        دریافت اشتراک فعال کاربر.
        
        Returns:
            Dict[str, Any]: اطلاعات اشتراک فعال یا None در صورت عدم وجود
        """
        try:
            subscription_data = self.db.execute(
                "SELECT subscription_type, start_date, expiry_date "
                "FROM subscriptions WHERE user_id = ? AND expiry_date > CURRENT_TIMESTAMP "
                "ORDER BY expiry_date DESC LIMIT 1",
                (self.user_id,)
            )
            
            if not subscription_data:
                return None
            
            # تبدیل نتیجه کوئری به دیکشنری
            subscription_type, start_date, expiry_date = subscription_data[0]
            
            return {
                'subscription_type': subscription_type,
                'start_date': start_date,
                'expiry_date': expiry_date,
                'days_left': (expiry_date - get_current_datetime()).days
            }
            
        except Exception as e:
            logger.error(f"خطا در دریافت اشتراک فعال کاربر {self.user_id}: {e}")
            return None
    
    def get_payment_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        دریافت تاریخچه پرداخت‌های کاربر.
        
        Args:
            limit: تعداد محدودیت نتایج
            
        Returns:
            List[Dict[str, Any]]: لیست پرداخت‌ها
        """
        try:
            payment_data = self.db.execute(
                "SELECT payment_id, amount, currency, payment_method, status, created_at, description "
                "FROM payments WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (self.user_id, limit)
            )
            
            # تبدیل نتیجه کوئری به لیست دیکشنری
            columns = ['payment_id', 'amount', 'currency', 'payment_method', 'status', 'created_at', 'description']
            result = []
            
            for row in payment_data:
                payment_dict = dict(zip(columns, row))
                result.append(payment_dict)
            
            return result
            
        except Exception as e:
            logger.error(f"خطا در دریافت تاریخچه پرداخت کاربر {self.user_id}: {e}")
            return []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        تبدیل اطلاعات کاربر به دیکشنری.
        
        Returns:
            Dict[str, Any]: اطلاعات کاربر
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.copy()
    
    def export_user_data(self) -> str:
        """
        استخراج اطلاعات کاربر برای خروجی گرفتن.
        
        Returns:
            str: اطلاعات کاربر در قالب JSON
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return "{}"
        
        user_data = self.to_dict()
        
        # حذف فیلدهای حساس
        for field in ['password', 'token']:
            if field in user_data:
                del user_data[field]
        
        # اضافه کردن اطلاعات اشتراک فعال
        active_subscription = self.get_active_subscription()
        user_data['active_subscription'] = active_subscription
        
        # دریافت تاریخچه پرداخت
        payment_history = self.get_payment_history(limit=100)
        user_data['payment_history'] = payment_history
        
        return json.dumps(user_data, ensure_ascii=False, default=str, indent=2)
    
    @classmethod
    def create_from_telegram(cls, db, telegram_user, language_code: Optional[str] = None) -> 'User':
        """
        ایجاد کاربر جدید از اطلاعات کاربر تلگرام.
        
        Args:
            db: آبجکت دیتابیس
            telegram_user: آبجکت کاربر تلگرام
            language_code: کد زبان (اختیاری)
            
        Returns:
            User: آبجکت کاربر جدید
        """
        user = cls(db, telegram_user.id)
        
        if not user.load():
            # ایجاد کاربر جدید
            user._is_new = True
            user._data = {
                'user_id': telegram_user.id,
                'username': telegram_user.username,
                'first_name': telegram_user.first_name,
                'last_name': telegram_user.last_name,
                'language_code': language_code or telegram_user.language_code or 'fa',
                'joined_date': get_current_datetime(),
                'is_active': 1,
                'is_registered': 0,
                'is_admin': 0,
                'notify_news': 1,
                'notify_price_alerts': 1,
                'notify_subscription': 1
            }
            user.save()
        
        return user
    
    @classmethod
    def get_all_active_users(cls, db, limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """
        دریافت لیست کاربران فعال.
        
        Args:
            db: آبجکت دیتابیس
            limit: محدودیت تعداد
            offset: شروع از چندمین رکورد
            
        Returns:
            List[Dict[str, Any]]: لیست کاربران فعال
        """
        try:
            users_data = db.execute(
                "SELECT user_id, username, full_name, email, phone, language_code, joined_date, last_activity "
                "FROM users WHERE is_active = 1 ORDER BY joined_date DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            
            # تبدیل نتیجه کوئری به لیست دیکشنری
            columns = ['user_id', 'username', 'full_name', 'email', 'phone', 'language_code', 'joined_date', 'last_activity']
            result = []
            
            for row in users_data:
                user_dict = dict(zip(columns, row))
                result.append(user_dict)
            
            return result
            
        except Exception as e:
            logger.error(f"خطا در دریافت لیست کاربران فعال: {e}")
            return []
    
    def add_custom_setting(self, key: str, value: Any) -> bool:
        """
        اضافه کردن یک تنظیم سفارشی برای کاربر.
        
        Args:
            key: کلید تنظیم
            value: مقدار تنظیم
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        try:
            # تبدیل مقدار به JSON برای ذخیره در دیتابیس
            value_json = json.dumps(value, ensure_ascii=False, default=str)
            
            # بررسی آیا این تنظیم قبلاً وجود دارد
            existing = self.db.execute(
                "SELECT COUNT(*) FROM user_settings WHERE user_id = ? AND setting_key = ?",
                (self.user_id, key)
            )[0][0]
            
            if existing:
                # به‌روزرسانی تنظیم موجود
                self.db.execute(
                    "UPDATE user_settings SET setting_value = ?, updated_at = ? WHERE user_id = ? AND setting_key = ?",
                    (value_json, get_current_datetime(), self.user_id, key)
                )
            else:
                # ایجاد تنظیم جدید
                self.db.execute(
                    "INSERT INTO user_settings (user_id, setting_key, setting_value, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (self.user_id, key, value_json, get_current_datetime(), get_current_datetime())
                )
                
            return True
                
        except Exception as e:
            logger.error(f"خطا در افزودن تنظیم سفارشی برای کاربر {self.user_id}: {e}")
            return False
    
    def get_custom_setting(self, key: str, default: Any = None) -> Any:
        """
        دریافت یک تنظیم سفارشی کاربر.
        
        Args:
            key: کلید تنظیم
            default: مقدار پیش‌فرض در صورت عدم وجود
            
        Returns:
            Any: مقدار تنظیم یا مقدار پیش‌فرض
        """
        try:
            setting_data = self.db.execute(
                "SELECT setting_value FROM user_settings WHERE user_id = ? AND setting_key = ?",
                (self.user_id, key)
            )
            
            if not setting_data:
                return default
            
            value_json = setting_data[0][0]
            
            # تبدیل JSON به مقدار اصلی
            try:
                return json.loads(value_json)
            except:
                return value_json
                
        except Exception as e:
            logger.error(f"خطا در دریافت تنظیم سفارشی برای کاربر {self.user_id}: {e}")
            return default
    
    def get_all_custom_settings(self) -> Dict[str, Any]:
        """
        دریافت تمام تنظیمات سفارشی کاربر.
        
        Returns:
            Dict[str, Any]: دیکشنری تنظیمات
        """
        try:
            settings_data = self.db.execute(
                "SELECT setting_key, setting_value FROM user_settings WHERE user_id = ?",
                (self.user_id,)
            )
            
            result = {}
            
            for key, value_json in settings_data:
                try:
                    result[key] = json.loads(value_json)
                except:
                    result[key] = value_json
            
            return result
                
        except Exception as e:
            logger.error(f"خطا در دریافت تنظیمات سفارشی برای کاربر {self.user_id}: {e}")
            return {}
    
    def remove_custom_setting(self, key: str) -> bool:
        """
        حذف یک تنظیم سفارشی کاربر.
        
        Args:
            key: کلید تنظیم
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        try:
            self.db.execute(
                "DELETE FROM user_settings WHERE user_id = ? AND setting_key = ?",
                (self.user_id, key)
            )
            
            return True
                
        except Exception as e:
            logger.error(f"خطا در حذف تنظیم سفارشی برای کاربر {self.user_id}: {e}")
            return False
    
    def add_to_loyalty_points(self, points: int, reason: str = "") -> bool:
        """
        افزودن امتیاز وفاداری به کاربر.
        
        Args:
            points: تعداد امتیاز
            reason: دلیل افزودن امتیاز
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        try:
            # بررسی و ایجاد رکورد امتیاز وفاداری
            current_points = self.db.execute(
                "SELECT loyalty_points FROM users WHERE user_id = ?",
                (self.user_id,)
            )
            
            if not current_points:
                return False
            
            current_points = current_points[0][0] or 0
            new_points = current_points + points
            
            # به‌روزرسانی امتیاز در جدول کاربران
            self.db.execute(
                "UPDATE users SET loyalty_points = ? WHERE user_id = ?",
                (new_points, self.user_id)
            )
            
            # ثبت تراکنش امتیاز
            self.db.execute(
                "INSERT INTO loyalty_transactions (user_id, points, reason, transaction_date) "
                "VALUES (?, ?, ?, ?)",
                (self.user_id, points, reason, get_current_datetime())
            )
            
            # به‌روزرسانی کش داخلی
            if self._is_loaded:
                self._data['loyalty_points'] = new_points
            
            return True
                
        except Exception as e:
            logger.error(f"خطا در افزودن امتیاز وفاداری برای کاربر {self.user_id}: {e}")
            return False
    
    def get_loyalty_points(self) -> int:
        """
        دریافت امتیاز وفاداری کاربر.
        
        Returns:
            int: تعداد امتیاز وفاداری
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('loyalty_points', 0) or 0
    
    def get_loyalty_transactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        دریافت تراکنش‌های امتیاز وفاداری.
        
        Args:
            limit: محدودیت تعداد
            
        Returns:
            List[Dict[str, Any]]: لیست تراکنش‌ها
        """
        try:
            transactions = self.db.execute(
                "SELECT transaction_id, points, reason, transaction_date "
                "FROM loyalty_transactions WHERE user_id = ? "
                "ORDER BY transaction_date DESC LIMIT ?",
                (self.user_id, limit)
            )
            
            # تبدیل نتیجه کوئری به لیست دیکشنری
            columns = ['transaction_id', 'points', 'reason', 'transaction_date']
            result = []
            
            for row in transactions:
                transaction_dict = dict(zip(columns, row))
                result.append(transaction_dict)
            
            return result
                
        except Exception as e:
            logger.error(f"خطا در دریافت تراکنش‌های امتیاز وفاداری برای کاربر {self.user_id}: {e}")
            return []
    
    def delete_account(self, hard_delete: bool = False) -> bool:
        """
        حذف حساب کاربری.
        
        Args:
            hard_delete: اگر True باشد، حذف کامل انجام می‌شود، در غیر این صورت فقط غیرفعال می‌شود
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        try:
            if not self._is_loaded and not self._is_new:
                self.load()
                
            if not self._is_loaded:
                return False
            
            if hard_delete:
                # حذف کامل از دیتابیس (توجه: این کار معمولاً توصیه نمی‌شود)
                # ابتدا باید تمام داده‌های وابسته حذف شوند
                self.db.execute("DELETE FROM user_settings WHERE user_id = ?", (self.user_id,))
                self.db.execute("DELETE FROM loyalty_transactions WHERE user_id = ?", (self.user_id,))
                self.db.execute("DELETE FROM support_messages WHERE user_id = ?", (self.user_id,))
                self.db.execute("DELETE FROM subscriptions WHERE user_id = ?", (self.user_id,))
                self.db.execute("DELETE FROM payments WHERE user_id = ?", (self.user_id,))
                self.db.execute("DELETE FROM users WHERE user_id = ?", (self.user_id,))
                
                self._is_loaded = False
                self._is_new = False
                self._data = {}
            else:
                # غیرفعال کردن و ناشناس کردن داده‌ها (روش ایمن‌تر و پیشنهادی)
                anonymized_email = f"deleted_{self.user_id}@anonymous.com"
                anonymized_phone = f"deleted_{self.user_id}"
                
                self.db.execute(
                    "UPDATE users SET "
                    "is_active = 0, "
                    "is_deleted = 1, "
                    "deletion_date = ?, "
                    "email = ?, "
                    "phone = ?, "
                    "full_name = 'Deleted User' "
                    "WHERE user_id = ?",
                    (get_current_datetime(), anonymized_email, anonymized_phone, self.user_id)
                )
                
                # به‌روزرسانی کش داخلی
                if self._is_loaded:
                    self._data['is_active'] = 0
                    self._data['is_deleted'] = 1
                    self._data['deletion_date'] = get_current_datetime()
                    self._data['email'] = anonymized_email
                    self._data['phone'] = anonymized_phone
                    self._data['full_name'] = 'Deleted User'
            
            return True
                
        except Exception as e:
            logger.error(f"خطا در حذف حساب کاربر {self.user_id}: {e}")
            return False
    
    def add_support_message(self, message: str) -> int:
        """
        افزودن پیام پشتیبانی از کاربر.
        
        Args:
            message: متن پیام
            
        Returns:
            int: شناسه پیام ارسال شده یا 0 در صورت خطا
        """
        try:
            # درج پیام پشتیبانی
            message_id = self.db.execute_insert(
                "INSERT INTO support_messages (user_id, message, created_at, is_from_user) "
                "VALUES (?, ?, ?, 1)",
                (self.user_id, message, get_current_datetime())
            )
            
            return message_id
                
        except Exception as e:
            logger.error(f"خطا در افزودن پیام پشتیبانی برای کاربر {self.user_id}: {e}")
            return 0
    
    def get_support_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        دریافت تاریخچه پیام‌های پشتیبانی کاربر.
        
        Args:
            limit: محدودیت تعداد
            
        Returns:
            List[Dict[str, Any]]: لیست پیام‌ها
        """
        try:
            messages = self.db.execute(
                "SELECT message_id, message, created_at, is_from_user, is_read "
                "FROM support_messages WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (self.user_id, limit)
            )
            
            # تبدیل نتیجه کوئری به لیست دیکشنری
            columns = ['message_id', 'message', 'created_at', 'is_from_user', 'is_read']
            result = []
            
            for row in messages:
                message_dict = dict(zip(columns, row))
                result.append(message_dict)
            
            return result
                
        except Exception as e:
            logger.error(f"خطا در دریافت پیام‌های پشتیبانی کاربر {self.user_id}: {e}")
            return []
    
    def mark_messages_as_read(self) -> bool:
        """
        علامت‌گذاری تمام پیام‌های پشتیبانی کاربر به عنوان خوانده شده.
        
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        try:
            self.db.execute(
                "UPDATE support_messages SET is_read = 1 "
                "WHERE user_id = ? AND is_from_user = 0 AND is_read = 0",
                (self.user_id,)
            )
            
            return True
                
        except Exception as e:
            logger.error(f"خطا در علامت‌گذاری پیام‌های پشتیبانی کاربر {self.user_id}: {e}")
            return False
    
    def get_unread_messages_count(self) -> int:
        """
        دریافت تعداد پیام‌های خوانده نشده.
        
        Returns:
            int: تعداد پیام‌های خوانده نشده
        """
        try:
            count = self.db.execute(
                "SELECT COUNT(*) FROM support_messages "
                "WHERE user_id = ? AND is_from_user = 0 AND is_read = 0",
                (self.user_id,)
            )[0][0]
            
            return count
                
        except Exception as e:
            logger.error(f"خطا در شمارش پیام‌های خوانده نشده کاربر {self.user_id}: {e}")
            return 0
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """
        دریافت آمار استفاده کاربر از سیستم.
        
        Returns:
            Dict[str, Any]: آمار استفاده
        """
        try:
            # دریافت تعداد پیام‌های ارسال شده
            message_count = self.db.execute(
                "SELECT COUNT(*) FROM user_messages WHERE user_id = ?",
                (self.user_id,)
            )[0][0]
            
            # دریافت تعداد جلسات فعال
            session_count = self.db.execute(
                "SELECT COUNT(*) FROM user_sessions WHERE user_id = ?",
                (self.user_id,)
            )[0][0]
            
            # دریافت تعداد روزهای فعال
            active_days = self.db.execute(
                "SELECT COUNT(DISTINCT DATE(activity_date)) FROM user_activity "
                "WHERE user_id = ?",
                (self.user_id,)
            )[0][0]
            
            # دریافت زمان آخرین فعالیت
            last_activity = self.last_activity
            
            # دریافت تعداد کل پرداخت‌ها
            payment_count = self.db.execute(
                "SELECT COUNT(*) FROM payments WHERE user_id = ?",
                (self.user_id,)
            )[0][0]
            
            # دریافت مجموع مبلغ پرداختی
            total_payment = self.db.execute(
                "SELECT SUM(amount) FROM payments WHERE user_id = ? AND status = 'success'",
                (self.user_id,)
            )[0][0] or 0
            
            return {
                'message_count': message_count,
                'session_count': session_count,
                'active_days': active_days,
                'last_activity': last_activity,
                'payment_count': payment_count,
                'total_payment': total_payment,
                'loyalty_points': self.get_loyalty_points(),
                'days_since_join': (get_current_datetime() - self.joined_date).days if self.joined_date else 0
            }
                
        except Exception as e:
            logger.error(f"خطا در دریافت آمار استفاده کاربر {self.user_id}: {e}")
            return {
                'message_count': 0,
                'session_count': 0,
                'active_days': 0,
                'last_activity': None,
                'payment_count': 0,
                'total_payment': 0,
                'loyalty_points': 0,
                'days_since_join': 0
            }
    
    @property
    def has_active_subscription(self) -> bool:
        """
        بررسی آیا کاربر اشتراک فعال دارد.
        
        Returns:
            bool: True اگر اشتراک فعال دارد، False در غیر این صورت
        """
        return self.get_active_subscription() is not None
    
    def get_referral_code(self) -> str:
        """
        دریافت کد دعوت کاربر.
        
        Returns:
            str: کد دعوت
        """
        # بررسی آیا کد دعوت قبلاً ایجاد شده
        referral_code = self.get_custom_setting('referral_code')
        
        if referral_code:
            return referral_code
        
        # ایجاد کد دعوت جدید
        import string
        import random
        
        # ایجاد کد تصادفی 8 کاراکتری
        chars = string.ascii_uppercase + string.digits
        new_code = ''.join(random.choice(chars) for _ in range(8))
        
        # ذخیره کد دعوت
        self.add_custom_setting('referral_code', new_code)
        
        return new_code
    
    def get_referred_users(self) -> List[Dict[str, Any]]:
        """
        دریافت لیست کاربران دعوت شده توسط این کاربر.
        
        Returns:
            List[Dict[str, Any]]: لیست کاربران دعوت شده
        """
        try:
            referral_code = self.get_referral_code()
            
            # دریافت کاربرانی که با این کد دعوت ثبت‌نام کرده‌اند
            referred_users = self.db.execute(
                "SELECT user_id, full_name, joined_date, is_active "
                "FROM users WHERE referred_by = ?",
                (referral_code,)
            )
            
            # تبدیل نتیجه کوئری به لیست دیکشنری
            columns = ['user_id', 'full_name', 'joined_date', 'is_active']
            result = []
            
            for row in referred_users:
                user_dict = dict(zip(columns, row))
                result.append(user_dict)
            
            return result
                
        except Exception as e:
            logger.error(f"خطا در دریافت کاربران دعوت شده توسط کاربر {self.user_id}: {e}")
            return []
    
    @staticmethod
    def search_users(db, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        جستجوی کاربران براساس نام، ایمیل، تلفن یا نام کاربری.
        
        Args:
            db: آبجکت دیتابیس
            query: عبارت جستجو
            limit: محدودیت تعداد نتایج
            
        Returns:
            List[Dict[str, Any]]: لیست کاربران یافته شده
        """
        try:
            # اضافه کردن علامت % برای جستجوی فازی
            search_query = f"%{query}%"
            
            users_data = db.execute(
                "SELECT user_id, username, full_name, email, phone, is_active "
                "FROM users WHERE "
                "full_name LIKE ? OR "
                "email LIKE ? OR "
                "phone LIKE ? OR "
                "username LIKE ? "
                "LIMIT ?",
                (search_query, search_query, search_query, search_query, limit)
            )
            
            # تبدیل نتیجه کوئری به لیست دیکشنری
            columns = ['user_id', 'username', 'full_name', 'email', 'phone', 'is_active']
            result = []
            
            for row in users_data:
                user_dict = dict(zip(columns, row))
                result.append(user_dict)
            
            return result
                
        except Exception as e:
            logger.error(f"خطا در جستجوی کاربران با عبارت '{query}': {e}")
            return [] 