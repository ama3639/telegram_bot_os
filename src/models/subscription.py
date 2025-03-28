#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
این ماژول شامل کلاس مدل Subscription برای مدیریت اشتراک‌های کاربران است.
"""


from datetime import timezone
import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from src.utils.timezone_utils import get_current_datetime, timezone, timedelta
import json
import uuid

from src.utils.timezone_utils import get_user_timezone, convert_to_user_timezone

logger = logging.getLogger('models.subscription')

class Subscription:
    """
    مدل اشتراک برای ذخیره و مدیریت اطلاعات اشتراک‌های کاربران.
    """
    
    # انواع اشتراک‌های پشتیبانی شده
    SUBSCRIPTION_TYPES = {
        'basic': {
            'name': 'پایه',
            'duration_days': 30,
            'price': 150000,
            'currency': 'IRR',
            'features': ['دسترسی به امکانات پایه', 'پشتیبانی ایمیل']
        },
        'premium': {
            'name': 'پیشرفته',
            'duration_days': 30,
            'price': 350000,
            'currency': 'IRR',
            'features': ['تمام امکانات پایه', 'دسترسی به تحلیل‌های تکنیکال', 'پشتیبانی تلگرام']
        },
        'vip': {
            'name': 'ویژه',
            'duration_days': 30,
            'price': 750000,
            'currency': 'IRR',
            'features': ['تمام امکانات پیشرفته', 'سیگنال‌های ویژه', 'مشاوره اختصاصی', 'پشتیبانی تلفنی']
        },
        'quarterly_premium': {
            'name': 'پیشرفته (سه ماهه)',
            'duration_days': 90,
            'price': 900000,
            'currency': 'IRR',
            'features': ['تمام امکانات پیشرفته', 'تخفیف 15 درصدی']
        },
        'annual_premium': {
            'name': 'پیشرفته (سالانه)',
            'duration_days': 365,
            'price': 3000000,
            'currency': 'IRR',
            'features': ['تمام امکانات پیشرفته', 'تخفیف 30 درصدی']
        }
    }
    
    def __init__(self, db, subscription_id: Optional[str] = None):
        """
        مقداردهی اولیه مدل اشتراک.
        
        Args:
            db: آبجکت دیتابیس
            subscription_id: شناسه اشتراک (اختیاری)
        """
        self.db = db
        self.subscription_id = subscription_id
        self._data = {}
        self._is_loaded = False
        self._is_new = False
    
    def load(self) -> bool:
        """
        بارگذاری اطلاعات اشتراک از دیتابیس.
        
        Returns:
            bool: True در صورت موفقیت، False در صورت عدم وجود اشتراک
        """
        try:
            if not self.subscription_id:
                self._is_loaded = False
                return False
                
            subscription_data = self.db.execute(
                "SELECT * FROM subscriptions WHERE subscription_id = ?",
                (self.subscription_id,)
            )
            
            if not subscription_data:
                self._is_new = True
                self._is_loaded = False
                return False
            
            # تبدیل نتیجه کوئری به دیکشنری
            columns = [column[0] for column in self.db.cursor.description]
            self._data = dict(zip(columns, subscription_data[0]))
            
            self._is_loaded = True
            return True
            
        except Exception as e:
            logger.error(f"خطا در بارگذاری اطلاعات اشتراک {self.subscription_id}: {e}")
            self._is_loaded = False
            return False
    
    def save(self) -> bool:
        """
        ذخیره تغییرات اشتراک در دیتابیس.
        
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        try:
            if not self._is_loaded and not self._is_new:
                logger.error(f"تلاش برای ذخیره اشتراک {self.subscription_id} بدون بارگذاری قبلی")
                return False
            
            # اگر اشتراک جدید است و شناسه نداشته باشد، یک شناسه جدید ایجاد می‌کنیم
            if self._is_new and not self.subscription_id:
                self.subscription_id = str(uuid.uuid4())
                self._data['subscription_id'] = self.subscription_id
            
            if self._is_new:
                # درج رکورد جدید
                # تاریخ ایجاد اشتراک را تنظیم می‌کنیم اگر وجود نداشته باشد
                if 'created_at' not in self._data:
                    self._data['created_at'] = get_current_datetime()
                
                columns = list(self._data.keys())
                placeholders = ["?"] * len(columns)
                values = [self._data.get(column) for column in columns]
                
                query = f"INSERT INTO subscriptions ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                self.db.execute(query, values)
                
                self._is_new = False
                self._is_loaded = True
                return True
            else:
                # به‌روزرسانی رکورد موجود
                # تاریخ به‌روزرسانی اشتراک را به روز می‌کنیم
                self._data['updated_at'] = get_current_datetime()
                
                set_clause = ", ".join([f"{column} = ?" for column in self._data.keys() if column != "subscription_id"])
                values = [self._data.get(column) for column in self._data.keys() if column != "subscription_id"]
                values.append(self.subscription_id)  # برای شرط WHERE
                
                query = f"UPDATE subscriptions SET {set_clause} WHERE subscription_id = ?"
                self.db.execute(query, values)
                return True
                
        except Exception as e:
            logger.error(f"خطا در ذخیره اطلاعات اشتراک {self.subscription_id}: {e}")
            return False
    
    @classmethod
    def create(cls, db, user_id: int, subscription_type: str, start_date: Optional[datetime] = None,
               payment_id: Optional[str] = None, metadata: Dict[str, Any] = None) -> Optional['Subscription']:
        """
        ایجاد اشتراک جدید.
        
        Args:
            db: آبجکت دیتابیس
            user_id: شناسه کاربر
            subscription_type: نوع اشتراک
            start_date: تاریخ شروع (اختیاری)
            payment_id: شناسه پرداخت (اختیاری)
            metadata: اطلاعات اضافی
            
        Returns:
            Subscription: آبجکت اشتراک ایجاد شده یا None در صورت خطا
        """
        try:
            # بررسی اعتبار نوع اشتراک
            if subscription_type not in cls.SUBSCRIPTION_TYPES:
                logger.error(f"نوع اشتراک نامعتبر: {subscription_type}")
                return None
            
            # تنظیم تاریخ شروع اگر ارائه نشده باشد
            if start_date is None:
                start_date = get_current_datetime()
            
            # محاسبه تاریخ پایان بر اساس نوع اشتراک
            duration_days = cls.SUBSCRIPTION_TYPES[subscription_type]['duration_days']
            end_date = start_date + timedelta(days=duration_days)
            
            # ایجاد آبجکت اشتراک جدید
            subscription = cls(db)
            subscription._is_new = True
            subscription.subscription_id = str(uuid.uuid4())
            
            # تنظیم داده‌های اشتراک
            subscription._data = {
                'subscription_id': subscription.subscription_id,
                'user_id': user_id,
                'subscription_type': subscription_type,
                'start_date': start_date,
                'end_date': end_date,
                'is_active': 1,
                'is_auto_renew': 0,
                'payment_id': payment_id,
                'metadata': json.dumps(metadata or {}, ensure_ascii=False),
                'created_at': get_current_datetime(),
                'updated_at': get_current_datetime()
            }
            
            # ذخیره اشتراک در دیتابیس
            if not subscription.save():
                return None
                
            return subscription
            
        except Exception as e:
            logger.error(f"خطا در ایجاد اشتراک جدید برای کاربر {user_id}: {e}")
            return None
    
    @classmethod
    def get_active_subscription(cls, db, user_id: int) -> Optional['Subscription']:
        """
        دریافت اشتراک فعال کاربر.
        
        Args:
            db: آبجکت دیتابیس
            user_id: شناسه کاربر
            
        Returns:
            Subscription: آبجکت اشتراک فعال یا None در صورت عدم وجود
        """
        try:
            subscription_id = db.execute(
                "SELECT subscription_id FROM subscriptions "
                "WHERE user_id = ? AND end_date > ? AND is_active = 1 "
                "ORDER BY end_date DESC LIMIT 1",
                (user_id, get_current_datetime())
            )
            
            if not subscription_id:
                return None
                
            subscription = cls(db, subscription_id[0][0])
            if subscription.load():
                return subscription
                
            return None
            
        except Exception as e:
            logger.error(f"خطا در دریافت اشتراک فعال کاربر {user_id}: {e}")
            return None
    
    @property
    def user_id(self) -> int:
        """
        دریافت شناسه کاربر.
        
        Returns:
            int: شناسه کاربر
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('user_id', 0)
    
    @property
    def subscription_type(self) -> str:
        """
        دریافت نوع اشتراک.
        
        Returns:
            str: نوع اشتراک
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('subscription_type', '')
    
    @property
    def subscription_display_name(self) -> str:
        """
        دریافت نام نمایشی نوع اشتراک.
        
        Returns:
            str: نام نمایشی نوع اشتراک
        """
        sub_type = self.subscription_type
        if sub_type in self.SUBSCRIPTION_TYPES:
            return self.SUBSCRIPTION_TYPES[sub_type]['name']
        return sub_type
    
    @property
    def start_date(self) -> Optional[datetime]:
        """
        دریافت تاریخ شروع اشتراک.
        
        Returns:
            datetime: تاریخ شروع اشتراک
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        start_date = self._data.get('start_date')
        if start_date is None:
            return None
        
        # تبدیل به آبجکت datetime اگر رشته باشد
        if isinstance(start_date, str):
            try:
                return datetime.fromisoformat(start_date)
            except ValueError:
                return None
        
        return start_date
    
    @property
    def end_date(self) -> Optional[datetime]:
        """
        دریافت تاریخ پایان اشتراک.
        
        Returns:
            datetime: تاریخ پایان اشتراک
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        end_date = self._data.get('end_date')
        if end_date is None:
            return None
        
        # تبدیل به آبجکت datetime اگر رشته باشد
        if isinstance(end_date, str):
            try:
                return datetime.fromisoformat(end_date)
            except ValueError:
                return None
        
        return end_date
    
    @property
    def is_active(self) -> bool:
        """
        بررسی فعال بودن اشتراک.
        
        Returns:
            bool: True اگر اشتراک فعال باشد، False در غیر این صورت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return bool(self._data.get('is_active', 0))
    
    @property
    def is_auto_renew(self) -> bool:
        """
        بررسی تمدید خودکار اشتراک.
        
        Returns:
            bool: True اگر اشتراک تمدید خودکار داشته باشد، False در غیر این صورت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return bool(self._data.get('is_auto_renew', 0))
    
    @is_auto_renew.setter
    def is_auto_renew(self, value: bool) -> None:
        """
        تنظیم تمدید خودکار اشتراک.
        
        Args:
            value: وضعیت تمدید خودکار
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        self._data['is_auto_renew'] = 1 if value else 0
    
    @property
    def payment_id(self) -> Optional[str]:
        """
        دریافت شناسه پرداخت مرتبط با اشتراک.
        
        Returns:
            str: شناسه پرداخت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('payment_id')
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """
        دریافت متادیتای اشتراک.
        
        Returns:
            Dict[str, Any]: متادیتای اشتراک
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        metadata_json = self._data.get('metadata', '{}')
        
        try:
            return json.loads(metadata_json)
        except:
            return {}
    
    @metadata.setter
    def metadata(self, value: Dict[str, Any]) -> None:
        """
        تنظیم متادیتای اشتراک.
        
        Args:
            value: متادیتای جدید
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        self._data['metadata'] = json.dumps(value, ensure_ascii=False)
    
    @property
    def days_left(self) -> int:
        """
        محاسبه تعداد روزهای باقیمانده از اشتراک.
        
        Returns:
            int: تعداد روزهای باقیمانده
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self.end_date or not self.is_active:
            return 0
        
        remaining = (self.end_date - get_current_datetime()).days
        return max(0, remaining)
    
    @property
    def is_expired(self) -> bool:
        """
        بررسی منقضی شدن اشتراک.
        
        Returns:
            bool: True اگر اشتراک منقضی شده باشد، False در غیر این صورت
        """
        return self.days_left <= 0
    
    def deactivate(self) -> bool:
        """
        غیرفعال کردن اشتراک.
        
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return False
            
        self._data['is_active'] = 0
        self._data['updated_at'] = get_current_datetime()
        
        return self.save()
    
    def extend(self, days: int) -> bool:
        """
        تمدید اشتراک برای تعداد روز مشخص.
        
        Args:
            days: تعداد روزهای تمدید
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return False
            
        # محاسبه تاریخ پایان جدید
        current_end = self.end_date
        if current_end is None:
            current_end = get_current_datetime()
            
        new_end = current_end + timedelta(days=days)
        
        # به‌روزرسانی اطلاعات
        self._data['end_date'] = new_end
        self._data['is_active'] = 1
        self._data['updated_at'] = get_current_datetime()
        
        # اضافه کردن اطلاعات تمدید به متادیتا
        current_metadata = self.metadata
        extensions = current_metadata.get('extensions', [])
        extensions.append({
            'days': days,
            'timestamp': get_current_datetime().isoformat(),
            'previous_end_date': current_end.isoformat(),
            'new_end_date': new_end.isoformat()
        })
        current_metadata['extensions'] = extensions
        self.metadata = current_metadata
        
        return self.save()
    
    def renew(self) -> bool:
        """
        تمدید اشتراک برای یک دوره کامل.
        
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return False
            
        # دریافت مدت زمان اشتراک بر اساس نوع آن
        sub_type = self.subscription_type
        if sub_type not in self.SUBSCRIPTION_TYPES:
            return False
            
        duration_days = self.SUBSCRIPTION_TYPES[sub_type]['duration_days']
        
        # تمدید اشتراک
        return self.extend(duration_days)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        تبدیل اطلاعات اشتراک به دیکشنری.
        
        Returns:
            Dict[str, Any]: اطلاعات اشتراک
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded and not self._is_new:
            return {}
            
        result = self._data.copy()
        
        # اضافه کردن اطلاعات محاسبه شده
        result['days_left'] = self.days_left
        result['is_expired'] = self.is_expired
        result['subscription_display_name'] = self.subscription_display_name
        
        # اطمینان از داشتن متادیتا به صورت دیکشنری
        if 'metadata' in result:
            try:
                result['metadata'] = json.loads(result['metadata'])
            except:
                result['metadata'] = {}
        
        return result
    
    @classmethod
    def get_expiring_subscriptions(cls, db, days_threshold: int = 3) -> List['Subscription']:
        """
        دریافت اشتراک‌هایی که در آستانه انقضا هستند.
        
        Args:
            db: آبجکت دیتابیس
            days_threshold: آستانه روزهای باقیمانده
            
        Returns:
            List[Subscription]: لیست اشتراک‌های در آستانه انقضا
        """
        try:
            # محاسبه تاریخ آستانه
            threshold_date = get_current_datetime() + timedelta(days=days_threshold)
            
            # اجرای کوئری
            subscription_ids = db.execute(
                "SELECT subscription_id FROM subscriptions "
                "WHERE is_active = 1 AND end_date BETWEEN ? AND ? AND notification_sent = 0",
                (get_current_datetime(), threshold_date)
            )
            
            # ساخت آبجکت‌های اشتراک
            subscriptions = []
            for (subscription_id,) in subscription_ids:
                subscription = cls(db, subscription_id)
                if subscription.load():
                    subscriptions.append(subscription)
            
            return subscriptions
                
        except Exception as e:
            logger.error(f"خطا در دریافت اشتراک‌های در آستانه انقضا: {e}")
            return []
    
    def mark_notification_sent(self) -> bool:
        """
        علامت‌گذاری اطلاع‌رسانی انقضا به عنوان ارسال شده.
        
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return False
            
        self._data['notification_sent'] = 1
        self._data['updated_at'] = get_current_datetime()
        
        return self.save()
    
    @classmethod
    def get_subscription_stats(cls, db) -> Dict[str, Any]:
        """
        دریافت آمار اشتراک‌ها.
        
        Args:
            db: آبجکت دیتابیس
            
        Returns:
            Dict[str, Any]: آمار اشتراک‌ها
        """
        try:
            # تعداد کل اشتراک‌های فعال
            active_count = db.execute(
                "SELECT COUNT(*) FROM subscriptions WHERE is_active = 1 AND end_date > ?",
                (get_current_datetime(),)
            )[0][0]
            
            # تعداد اشتراک به تفکیک نوع
            type_counts = {}
            for sub_type in cls.SUBSCRIPTION_TYPES:
                type_count = db.execute(
                    "SELECT COUNT(*) FROM subscriptions "
                    "WHERE subscription_type = ? AND is_active = 1 AND end_date > ?",
                    (sub_type, get_current_datetime())
                )[0][0]
                type_counts[sub_type] = type_count
            
            # تعداد کاربران دارای اشتراک
            subscriber_count = db.execute(
                "SELECT COUNT(DISTINCT user_id) FROM subscriptions "
                "WHERE is_active = 1 AND end_date > ?",
                (get_current_datetime(),)
            )[0][0]
            
            # تعداد تمدیدهای ماه جاری
            current_month_start = get_current_datetime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            renewal_count = db.execute(
                "SELECT COUNT(*) FROM subscriptions "
                "WHERE created_at >= ? AND metadata LIKE '%extensions%'",
                (current_month_start,)
            )[0][0]
            
            return {
                'active_count': active_count,
                'type_counts': type_counts,
                'subscriber_count': subscriber_count,
                'renewal_count': renewal_count
            }
                
        except Exception as e:
            logger.error(f"خطا در دریافت آمار اشتراک‌ها: {e}")
            return {
                'active_count': 0,
                'type_counts': {sub_type: 0 for sub_type in cls.SUBSCRIPTION_TYPES},
                'subscriber_count': 0,
                'renewal_count': 0
            }
    
    @classmethod
    def get_user_subscription_history(cls, db, user_id: int) -> List['Subscription']:
        """
        دریافت تاریخچه اشتراک‌های یک کاربر.
        
        Args:
            db: آبجکت دیتابیس
            user_id: شناسه کاربر
            
        Returns:
            List[Subscription]: لیست اشتراک‌های کاربر
        """
        try:
            # اجرای کوئری
            subscription_ids = db.execute(
                "SELECT subscription_id FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            
            # ساخت آبجکت‌های اشتراک
            subscriptions = []
            for (subscription_id,) in subscription_ids:
                subscription = cls(db, subscription_id)
                if subscription.load():
                    subscriptions.append(subscription)
            
            return subscriptions
                
        except Exception as e:
            logger.error(f"خطا در دریافت تاریخچه اشتراک‌های کاربر {user_id}: {e}")
            return []
    
    def apply_discount_code(self, discount_code: str) -> bool:
        """
        اعمال کد تخفیف روی اشتراک.
        
        Args:
            discount_code: کد تخفیف
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return False
            
        try:
            # بررسی اعتبار کد تخفیف
            discount_data = self.db.execute(
                "SELECT discount_amount, discount_type, expiry_date, is_active "
                "FROM discount_codes WHERE code = ?",
                (discount_code,)
            )
            
            if not discount_data:
                logger.error(f"کد تخفیف یافت نشد: {discount_code}")
                return False
                
            discount_amount, discount_type, expiry_date, is_active = discount_data[0]
            
            # بررسی فعال بودن کد تخفیف
            if not is_active:
                logger.error(f"کد تخفیف غیرفعال است: {discount_code}")
                return False
                
            # بررسی تاریخ انقضای کد تخفیف
            if expiry_date and expiry_date < get_current_datetime():
                logger.error(f"کد تخفیف منقضی شده است: {discount_code}")
                return False
            
            # ذخیره اطلاعات کد تخفیف در متادیتا
            current_metadata = self.metadata
            discount_info = {
                'code': discount_code,
                'amount': discount_amount,
                'type': discount_type,
                'applied_at': get_current_datetime().isoformat()
            }
            current_metadata['discount'] = discount_info
            self.metadata = current_metadata
            
            # ثبت استفاده از کد تخفیف
            self.db.execute(
                "INSERT INTO discount_usage (discount_code, user_id, subscription_id, used_at) "
                "VALUES (?, ?, ?, ?)",
                (discount_code, self.user_id, self.subscription_id, get_current_datetime())
            )
            
            return self.save()
                
        except Exception as e:
            logger.error(f"خطا در اعمال کد تخفیف {discount_code} روی اشتراک {self.subscription_id}: {e}")
            return False
    
    def calculate_price_with_discount(self) -> Dict[str, Any]:
        """
        محاسبه قیمت اشتراک با در نظر گرفتن تخفیف‌ها.
        
        Returns:
            Dict[str, Any]: اطلاعات قیمت شامل قیمت اصلی، تخفیف و قیمت نهایی
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        # دریافت قیمت پایه اشتراک
        subscription_info = self.SUBSCRIPTION_TYPES.get(self.subscription_type, {})
        base_price = subscription_info.get('price', 0)
        currency = subscription_info.get('currency', 'IRR')
        
        # مقدار تخفیف و درصد تخفیف پیش‌فرض
        discount_amount = 0
        discount_percent = 0
        
        # بررسی وجود تخفیف در متادیتا
        current_metadata = self.metadata
        discount_info = current_metadata.get('discount', {})
        
        if discount_info:
            discount_value = discount_info.get('amount', 0)
            discount_type = discount_info.get('type', 'percent')
            
            if discount_type == 'percent':
                # تخفیف درصدی
                discount_percent = discount_value
                discount_amount = (base_price * discount_value) / 100
            elif discount_type == 'fixed':
                # تخفیف مقداری
                discount_amount = discount_value
                if base_price > 0:
                    discount_percent = (discount_value / base_price) * 100
        
        # محاسبه قیمت نهایی
        final_price = max(0, base_price - discount_amount)
        
        return {
            'base_price': base_price,
            'discount_amount': discount_amount,
            'discount_percent': discount_percent,
            'final_price': final_price,
            'currency': currency,
            'discount_code': discount_info.get('code', '')
        }
    
    def upgrade_subscription(self, new_subscription_type: str) -> bool:
        """
        ارتقای اشتراک به نوع بالاتر.
        
        Args:
            new_subscription_type: نوع جدید اشتراک
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return False
            
        # بررسی اعتبار نوع اشتراک جدید
        if new_subscription_type not in self.SUBSCRIPTION_TYPES:
            logger.error(f"نوع اشتراک نامعتبر: {new_subscription_type}")
            return False
            
        # بررسی اینکه آیا ارتقا است یا تنزل
        current_price = self.SUBSCRIPTION_TYPES.get(self.subscription_type, {}).get('price', 0)
        new_price = self.SUBSCRIPTION_TYPES.get(new_subscription_type, {}).get('price', 0)
        
        if new_price <= current_price:
            logger.error(f"نوع اشتراک جدید ({new_subscription_type}) ارتقا نیست")
            return False
        
        # تغییر نوع اشتراک
        self._data['subscription_type'] = new_subscription_type
        self._data['updated_at'] = get_current_datetime()
        
        # محاسبه مدت جدید براساس تفاوت قیمت
        days_left = self.days_left
        old_daily_price = current_price / self.SUBSCRIPTION_TYPES.get(self.subscription_type, {}).get('duration_days', 30)
        new_daily_price = new_price / self.SUBSCRIPTION_TYPES.get(new_subscription_type, {}).get('duration_days', 30)
        
        if old_daily_price > 0 and new_daily_price > 0:
            remaining_value = days_left * old_daily_price
            new_days = int(remaining_value / new_daily_price)
        else:
            new_days = days_left
        
        # تنظیم تاریخ پایان جدید
        if new_days > 0:
            new_end_date = get_current_datetime() + timedelta(days=new_days)
            self._data['end_date'] = new_end_date
        
        # اضافه کردن اطلاعات ارتقا به متادیتا
        current_metadata = self.metadata
        upgrade_info = {
            'previous_type': self.subscription_type,
            'new_type': new_subscription_type,
            'upgraded_at': get_current_datetime().isoformat(),
            'previous_end_date': self.end_date.isoformat() if self.end_date else None,
            'new_end_date': self._data['end_date'].isoformat() if self._data.get('end_date') else None,
            'previous_days_left': days_left,
            'new_days': new_days
        }
        
        upgrades = current_metadata.get('upgrades', [])
        upgrades.append(upgrade_info)
        current_metadata['upgrades'] = upgrades
        self.metadata = current_metadata
        
        return self.save()
    
    def cancel_subscription(self, reason: str = "") -> bool:
        """
        لغو اشتراک.
        
        Args:
            reason: دلیل لغو
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return False
            
        # غیرفعال کردن اشتراک
        self._data['is_active'] = 0
        self._data['is_auto_renew'] = 0
        self._data['updated_at'] = get_current_datetime()
        self._data['cancelled_at'] = get_current_datetime()
        
        # اضافه کردن اطلاعات لغو به متادیتا
        current_metadata = self.metadata
        cancel_info = {
            'cancelled_at': get_current_datetime().isoformat(),
            'reason': reason,
            'days_left': self.days_left
        }
        current_metadata['cancellation'] = cancel_info
        self.metadata = current_metadata
        
        return self.save()
    
    def pause_subscription(self, days: int = 0) -> bool:
        """
        توقف موقت اشتراک.
        
        Args:
            days: تعداد روزهای توقف (0 برای نامحدود)
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return False
            
        # تنظیم وضعیت اشتراک به حالت توقف
        self._data['is_paused'] = 1
        self._data['updated_at'] = get_current_datetime()
        self._data['paused_at'] = get_current_datetime()
        
        # تنظیم تاریخ پایان توقف اگر مشخص شده باشد
        if days > 0:
            self._data['pause_end_date'] = get_current_datetime() + timedelta(days=days)
        else:
            self._data['pause_end_date'] = None
        
        # اضافه کردن اطلاعات توقف به متادیتا
        current_metadata = self.metadata
        pause_info = {
            'paused_at': get_current_datetime().isoformat(),
            'days': days,
            'pause_end_date': self._data['pause_end_date'].isoformat() if self._data.get('pause_end_date') else None
        }
        
        pauses = current_metadata.get('pauses', [])
        pauses.append(pause_info)
        current_metadata['pauses'] = pauses
        self.metadata = current_metadata
        
        return self.save()
    
    def resume_subscription(self) -> bool:
        """
        ادامه اشتراک پس از توقف موقت.
        
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return False
            
        # بررسی آیا اشتراک در حالت توقف است
        if not self._data.get('is_paused', 0):
            return False
            
        # محاسبه مدت زمان توقف
        paused_at = self._data.get('paused_at')
        if paused_at:
            # اضافه کردن مدت زمان توقف به تاریخ پایان اشتراک
            pause_duration = (get_current_datetime() - paused_at).days
            if self.end_date:
                self._data['end_date'] = self.end_date + timedelta(days=pause_duration)
        
        # فعال کردن مجدد اشتراک
        self._data['is_paused'] = 0
        self._data['updated_at'] = get_current_datetime()
        self._data['resumed_at'] = get_current_datetime()
        self._data['paused_at'] = None
        self._data['pause_end_date'] = None
        
        # اضافه کردن اطلاعات ادامه به متادیتا
        current_metadata = self.metadata
        if 'pauses' in current_metadata and current_metadata['pauses']:
            last_pause = current_metadata['pauses'][-1]
            last_pause['resumed_at'] = get_current_datetime().isoformat()
            last_pause['actual_duration_days'] = pause_duration if paused_at else 0
            current_metadata['pauses'][-1] = last_pause
            
        self.metadata = current_metadata
        
        return self.save()
    
    @classmethod
    def validate_coupon_code(cls, db, code: str, user_id: int = None) -> Dict[str, Any]:
        """
        اعتبارسنجی کد کوپن تخفیف.
        
        Args:
            db: آبجکت دیتابیس
            code: کد کوپن
            user_id: شناسه کاربر (اختیاری)
            
        Returns:
            Dict[str, Any]: اطلاعات کوپن یا خطا
        """
        try:
            # بررسی وجود کوپن
            coupon_data = db.execute(
                "SELECT id, code, discount_amount, discount_type, max_uses, expiry_date, is_active, "
                "min_purchase_amount, allowed_subscription_types "
                "FROM discount_codes WHERE code = ?",
                (code,)
            )
            
            if not coupon_data:
                return {
                    'valid': False,
                    'error': 'coupon_not_found',
                    'message': 'کد تخفیف معتبر نیست'
                }
                
            coupon_id, code, discount_amount, discount_type, max_uses, expiry_date, is_active, \
            min_purchase_amount, allowed_subscription_types = coupon_data[0]
            
            # بررسی فعال بودن کوپن
            if not is_active:
                return {
                    'valid': False,
                    'error': 'coupon_inactive',
                    'message': 'کد تخفیف غیرفعال است'
                }
                
            # بررسی تاریخ انقضا
            if expiry_date and expiry_date < get_current_datetime():
                return {
                    'valid': False,
                    'error': 'coupon_expired',
                    'message': 'کد تخفیف منقضی شده است'
                }
                
            # بررسی تعداد استفاده
            if max_uses > 0:
                usage_count = db.execute(
                    "SELECT COUNT(*) FROM discount_usage WHERE discount_code = ?",
                    (code,)
                )[0][0]
                
                if usage_count >= max_uses:
                    return {
                        'valid': False,
                        'error': 'coupon_max_uses_reached',
                        'message': 'کد تخفیف به حداکثر تعداد استفاده رسیده است'
                    }
            
            # بررسی استفاده قبلی توسط کاربر (اگر کاربر مشخص شده باشد)
            if user_id:
                user_usage = db.execute(
                    "SELECT COUNT(*) FROM discount_usage WHERE discount_code = ? AND user_id = ?",
                    (code, user_id)
                )[0][0]
                
                if user_usage > 0:
                    return {
                        'valid': False,
                        'error': 'coupon_already_used',
                        'message': 'شما قبلاً از این کد تخفیف استفاده کرده‌اید'
                    }
            
            # کوپن معتبر است
            return {
                'valid': True,
                'discount_amount': discount_amount,
                'discount_type': discount_type,
                'min_purchase_amount': min_purchase_amount,
                'allowed_subscription_types': json.loads(allowed_subscription_types) if allowed_subscription_types else None
            }
                
        except Exception as e:
            logger.error(f"خطا در اعتبارسنجی کد کوپن {code}: {e}")
            return {
                'valid': False,
                'error': 'system_error',
                'message': 'خطا در بررسی کد تخفیف'
            }
    
    @classmethod
    def create_gift_subscription(cls, db, giver_user_id: int, receiver_user_id: int, 
                              subscription_type: str, message: str = "") -> Optional['Subscription']:
        """
        ایجاد اشتراک هدیه.
        
        Args:
            db: آبجکت دیتابیس
            giver_user_id: شناسه کاربر اهدا کننده
            receiver_user_id: شناسه کاربر دریافت کننده
            subscription_type: نوع اشتراک
            message: پیام شخصی
            
        Returns:
            Subscription: آبجکت اشتراک ایجاد شده یا None در صورت خطا
        """
        try:
            # بررسی اعتبار نوع اشتراک
            if subscription_type not in cls.SUBSCRIPTION_TYPES:
                logger.error(f"نوع اشتراک نامعتبر: {subscription_type}")
                return None
            
            # ایجاد اشتراک هدیه
            subscription = cls.create(db, receiver_user_id, subscription_type)
            
            if not subscription:
                return None
                
            # اضافه کردن اطلاعات هدیه به متادیتا
            gift_info = {
                'is_gift': True,
                'giver_user_id': giver_user_id,
                'message': message,
                'gifted_at': get_current_datetime().isoformat()
            }
            
            metadata = subscription.metadata
            metadata['gift'] = gift_info
            subscription.metadata = metadata
            
            # ذخیره اشتراک
            if not subscription.save():
                return None
                
            # ثبت لاگ هدیه
            db.execute(
                "INSERT INTO gift_logs (giver_user_id, receiver_user_id, subscription_id, gift_date, message) "
                "VALUES (?, ?, ?, ?, ?)",
                (giver_user_id, receiver_user_id, subscription.subscription_id, get_current_datetime(), message)
            )
            
            return subscription
                
        except Exception as e:
            logger.error(f"خطا در ایجاد اشتراک هدیه از کاربر {giver_user_id} به کاربر {receiver_user_id}: {e}")
            return None
    
    @classmethod
    def compare_subscription_types(cls, type1: str, type2: str) -> int:
        """
        مقایسه دو نوع اشتراک از نظر سطح.
        
        Args:
            type1: نوع اول اشتراک
            type2: نوع دوم اشتراک
            
        Returns:
            int: 1 اگر نوع اول بالاتر باشد، -1 اگر نوع دوم بالاتر باشد، 0 اگر برابر باشند
        """
        # بررسی اعتبار انواع اشتراک
        if type1 not in cls.SUBSCRIPTION_TYPES or type2 not in cls.SUBSCRIPTION_TYPES:
            return 0
            
        # مقایسه بر اساس قیمت
        price1 = cls.SUBSCRIPTION_TYPES[type1]['price']
        price2 = cls.SUBSCRIPTION_TYPES[type2]['price']
        
        if price1 > price2:
            return 1
        elif price1 < price2:
            return -1
        else:
            return 0 