#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
این ماژول شامل کلاس مدل Payment برای مدیریت پرداخت‌های کاربران است.
"""


from datetime import timezone
import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from utils.timezone_utils import get_current_datetime, timezone
import json
import uuid

from utils.security import encrypt_sensitive_data, decrypt_sensitive_data
from utils.timezone_utils import get_user_timezone, convert_to_user_timezone

logger = logging.getLogger('models.payment')

class Payment:
    """
    مدل پرداخت برای ذخیره و مدیریت اطلاعات پرداخت‌های کاربران.
    """
    
    # انواع روش‌های پرداخت پشتیبانی شده
    PAYMENT_METHODS = {
        'crypto': 'رمزارز',
        'card': 'کارت بانکی',
        'bank_transfer': 'انتقال بانکی',
        'zarinpal': 'زرین‌پال',
        'paypal': 'پی‌پال',
        'admin': 'توسط ادمین'
    }
    
    # وضعیت‌های مختلف پرداخت
    PAYMENT_STATUSES = {
        'pending': 'در انتظار',
        'processing': 'در حال پردازش',
        'completed': 'تکمیل شده',
        'failed': 'ناموفق',
        'refunded': 'مسترد شده',
        'cancelled': 'لغو شده'
    }
    
    def __init__(self, db, payment_id: Optional[str] = None):
        """
        مقداردهی اولیه مدل پرداخت.
        
        Args:
            db: آبجکت دیتابیس
            payment_id: شناسه پرداخت (اختیاری)
        """
        self.db = db
        self.payment_id = payment_id
        self._data = {}
        self._is_loaded = False
        self._is_new = False
    
    def load(self) -> bool:
        """
        بارگذاری اطلاعات پرداخت از دیتابیس.
        
        Returns:
            bool: True در صورت موفقیت، False در صورت عدم وجود پرداخت
        """
        try:
            if not self.payment_id:
                self._is_loaded = False
                return False
                
            payment_data = self.db.execute(
                "SELECT * FROM payments WHERE payment_id = ?",
                (self.payment_id,)
            )
            
            if not payment_data:
                self._is_new = True
                self._is_loaded = False
                return False
            
            # تبدیل نتیجه کوئری به دیکشنری
            columns = [column[0] for column in self.db.cursor.description]
            self._data = dict(zip(columns, payment_data[0]))
            
            self._is_loaded = True
            return True
            
        except Exception as e:
            logger.error(f"خطا در بارگذاری اطلاعات پرداخت {self.payment_id}: {e}")
            self._is_loaded = False
            return False
    
    def save(self) -> bool:
        """
        ذخیره تغییرات پرداخت در دیتابیس.
        
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        try:
            if not self._is_loaded and not self._is_new:
                logger.error(f"تلاش برای ذخیره پرداخت {self.payment_id} بدون بارگذاری قبلی")
                return False
            
            # اگر پرداخت جدید است و شناسه نداشته باشد، یک شناسه جدید ایجاد می‌کنیم
            if self._is_new and not self.payment_id:
                self.payment_id = str(uuid.uuid4())
                self._data['payment_id'] = self.payment_id
            
            if self._is_new:
                # درج رکورد جدید
                # تاریخ ایجاد پرداخت را تنظیم می‌کنیم اگر وجود نداشته باشد
                if 'created_at' not in self._data:
                    self._data['created_at'] = get_current_datetime()
                
                columns = list(self._data.keys())
                placeholders = ["?"] * len(columns)
                values = [self._data.get(column) for column in columns]
                
                query = f"INSERT INTO payments ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                self.db.execute(query, values)
                
                self._is_new = False
                self._is_loaded = True
                return True
            else:
                # به‌روزرسانی رکورد موجود
                # تاریخ به‌روزرسانی پرداخت را به روز می‌کنیم
                self._data['updated_at'] = get_current_datetime()
                
                set_clause = ", ".join([f"{column} = ?" for column in self._data.keys() if column != "payment_id"])
                values = [self._data.get(column) for column in self._data.keys() if column != "payment_id"]
                values.append(self.payment_id)  # برای شرط WHERE
                
                query = f"UPDATE payments SET {set_clause} WHERE payment_id = ?"
                self.db.execute(query, values)
                return True
                
        except Exception as e:
            logger.error(f"خطا در ذخیره اطلاعات پرداخت {self.payment_id}: {e}")
            return False
    
    @classmethod
    def create(cls, db, user_id: int, amount: float, currency: str, payment_method: str,
               description: str = "", metadata: Dict[str, Any] = None) -> Optional['Payment']:
        """
        ایجاد پرداخت جدید.
        
        Args:
            db: آبجکت دیتابیس
            user_id: شناسه کاربر
            amount: مبلغ پرداخت
            currency: ارز پرداخت
            payment_method: روش پرداخت
            description: توضیحات
            metadata: اطلاعات اضافی
            
        Returns:
            Payment: آبجکت پرداخت ایجاد شده یا None در صورت خطا
        """
        try:
            # بررسی اعتبار مقادیر ورودی
            if amount <= 0:
                logger.error(f"مبلغ پرداخت نامعتبر: {amount}")
                return None
                
            if payment_method not in cls.PAYMENT_METHODS:
                logger.error(f"روش پرداخت نامعتبر: {payment_method}")
                return None
            
            # ایجاد آبجکت پرداخت جدید
            payment = cls(db)
            payment._is_new = True
            payment.payment_id = str(uuid.uuid4())
            
            # تنظیم داده‌های پرداخت
            payment._data = {
                'payment_id': payment.payment_id,
                'user_id': user_id,
                'amount': amount,
                'currency': currency,
                'payment_method': payment_method,
                'status': 'pending',
                'description': description,
                'metadata': json.dumps(metadata or {}, ensure_ascii=False),
                'created_at': get_current_datetime(),
                'updated_at': get_current_datetime()
            }
            
            # ذخیره پرداخت در دیتابیس
            if not payment.save():
                return None
                
            return payment
            
        except Exception as e:
            logger.error(f"خطا در ایجاد پرداخت جدید برای کاربر {user_id}: {e}")
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
    def amount(self) -> float:
        """
        دریافت مبلغ پرداخت.
        
        Returns:
            float: مبلغ پرداخت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('amount', 0.0)
    
    @property
    def currency(self) -> str:
        """
        دریافت ارز پرداخت.
        
        Returns:
            str: ارز پرداخت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('currency', '')
    
    @property
    def payment_method(self) -> str:
        """
        دریافت روش پرداخت.
        
        Returns:
            str: روش پرداخت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('payment_method', '')
    
    @property
    def payment_method_display(self) -> str:
        """
        دریافت نام نمایشی روش پرداخت.
        
        Returns:
            str: نام نمایشی روش پرداخت
        """
        method = self.payment_method
        return self.PAYMENT_METHODS.get(method, method)
    
    @property
    def status(self) -> str:
        """
        دریافت وضعیت پرداخت.
        
        Returns:
            str: وضعیت پرداخت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('status', 'pending')
    
    @status.setter
    def status(self, value: str) -> None:
        """
        تنظیم وضعیت پرداخت.
        
        Args:
            value: وضعیت جدید
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if value not in self.PAYMENT_STATUSES:
            raise ValueError(f"وضعیت پرداخت نامعتبر: {value}")
            
        self._data['status'] = value
        self._data['updated_at'] = get_current_datetime()
    
    @property
    def status_display(self) -> str:
        """
        دریافت نام نمایشی وضعیت پرداخت.
        
        Returns:
            str: نام نمایشی وضعیت
        """
        status = self.status
        return self.PAYMENT_STATUSES.get(status, status)
    
    @property
    def description(self) -> str:
        """
        دریافت توضیحات پرداخت.
        
        Returns:
            str: توضیحات پرداخت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        return self._data.get('description', '')
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """
        دریافت متادیتای پرداخت.
        
        Returns:
            Dict[str, Any]: متادیتای پرداخت
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
        تنظیم متادیتای پرداخت.
        
        Args:
            value: متادیتای جدید
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        self._data['metadata'] = json.dumps(value, ensure_ascii=False)
        self._data['updated_at'] = get_current_datetime()
    
    @property
    def created_at(self) -> Optional[datetime]:
        """
        دریافت تاریخ ایجاد پرداخت.
        
        Returns:
            datetime: تاریخ ایجاد پرداخت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        created_at = self._data.get('created_at')
        if created_at is None:
            return None
        
        # تبدیل به آبجکت datetime اگر رشته باشد
        if isinstance(created_at, str):
            try:
                return datetime.fromisoformat(created_at)
            except ValueError:
                return None
        
        return created_at
    
    @property
    def updated_at(self) -> Optional[datetime]:
        """
        دریافت تاریخ به‌روزرسانی پرداخت.
        
        Returns:
            datetime: تاریخ به‌روزرسانی پرداخت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        updated_at = self._data.get('updated_at')
        if updated_at is None:
            return None
        
        # تبدیل به آبجکت datetime اگر رشته باشد
        if isinstance(updated_at, str):
            try:
                return datetime.fromisoformat(updated_at)
            except ValueError:
                return None
        
        return updated_at
    
    @property
    def completed_at(self) -> Optional[datetime]:
        """
        دریافت تاریخ تکمیل پرداخت.
        
        Returns:
            datetime: تاریخ تکمیل پرداخت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        completed_at = self._data.get('completed_at')
        if completed_at is None:
            return None
        
        # تبدیل به آبجکت datetime اگر رشته باشد
        if isinstance(completed_at, str):
            try:
                return datetime.fromisoformat(completed_at)
            except ValueError:
                return None
        
        return completed_at
    
    def update_status(self, status: str, transaction_id: str = None, details: Dict[str, Any] = None) -> bool:
        """
        به‌روزرسانی وضعیت پرداخت.
        
        Args:
            status: وضعیت جدید
            transaction_id: شناسه تراکنش خارجی (درگاه پرداخت)
            details: جزئیات اضافی
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        try:
            if not self._is_loaded and not self._is_new:
                self.load()
                
            if not self._is_loaded:
                return False
                
            if status not in self.PAYMENT_STATUSES:
                logger.error(f"وضعیت پرداخت نامعتبر: {status}")
                return False
                
            self._data['status'] = status
            self._data['updated_at'] = get_current_datetime()
            
            # اگر تراکنش موفق باشد، تاریخ تکمیل را ثبت می‌کنیم
            if status == 'completed' and not self._data.get('completed_at'):
                self._data['completed_at'] = get_current_datetime()
            
            # اگر شناسه تراکنش خارجی ارائه شده باشد، آن را ذخیره می‌کنیم
            if transaction_id:
                self._data['transaction_id'] = transaction_id
            
            # اگر جزئیات اضافی ارائه شده باشد، آن‌ها را به متادیتا اضافه می‌کنیم
            if details:
                current_metadata = self.metadata
                status_history = current_metadata.get('status_history', [])
                status_history.append({
                    'status': status,
                    'timestamp': get_current_datetime().isoformat(),
                    'details': details
                })
                current_metadata['status_history'] = status_history
                
                if transaction_id:
                    current_metadata['transaction_id'] = transaction_id
                
                self.metadata = current_metadata
            
            return self.save()
                
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی وضعیت پرداخت {self.payment_id}: {e}")
            return False
    
    def mark_as_completed(self, transaction_id: str = None, details: Dict[str, Any] = None) -> bool:
        """
        علامت‌گذاری پرداخت به عنوان تکمیل شده.
        
        Args:
            transaction_id: شناسه تراکنش خارجی
            details: جزئیات تکمیل
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        return self.update_status('completed', transaction_id, details)
    
    def mark_as_failed(self, reason: str = None, details: Dict[str, Any] = None) -> bool:
        """
        علامت‌گذاری پرداخت به عنوان ناموفق.
        
        Args:
            reason: دلیل شکست
            details: جزئیات شکست
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        details_dict = details or {}
        if reason:
            details_dict['reason'] = reason
            
        return self.update_status('failed', None, details_dict)
    
    def mark_as_refunded(self, reason: str = None, details: Dict[str, Any] = None) -> bool:
        """
        علامت‌گذاری پرداخت به عنوان مسترد شده.
        
        Args:
            reason: دلیل استرداد
            details: جزئیات استرداد
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        details_dict = details or {}
        if reason:
            details_dict['reason'] = reason
            
        return self.update_status('refunded', None, details_dict)
    
    def generate_payment_link(self) -> str:
        """
        ایجاد لینک پرداخت.
        
        Returns:
            str: لینک پرداخت
        """
        # این متد باید برای هر روش پرداخت به صورت اختصاصی پیاده‌سازی شود
        # در اینجا یک نمونه ساده ارائه می‌شود
        
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded:
            return ""
        
        # بر اساس روش پرداخت، لینک مناسب را ایجاد می‌کنیم
        payment_method = self.payment_method
        
        if payment_method == 'crypto':
            return f"https://pay.example.com/crypto/{self.payment_id}"
        elif payment_method == 'card':
            return f"https://pay.example.com/card/{self.payment_id}"
        elif payment_method == 'zarinpal':
            return f"https://pay.example.com/zarinpal/{self.payment_id}"
        else:
            return f"https://pay.example.com/checkout/{self.payment_id}"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        تبدیل اطلاعات پرداخت به دیکشنری.
        
        Returns:
            Dict[str, Any]: اطلاعات پرداخت
        """
        if not self._is_loaded and not self._is_new:
            self.load()
            
        if not self._is_loaded and not self._is_new:
            return {}
            
        result = self._data.copy()
        
        # تبدیل برخی فیلدها به مقادیر نمایشی
        result['payment_method_display'] = self.payment_method_display
        result['status_display'] = self.status_display
        
        # اطمینان از داشتن متادیتا به صورت دیکشنری
        if 'metadata' in result:
            try:
                result['metadata'] = json.loads(result['metadata'])
            except:
                result['metadata'] = {}
        
        return result
    
    @classmethod
    def get_user_payments(cls, db, user_id: int, status: Optional[str] = None, 
                          limit: int = 20, offset: int = 0) -> List['Payment']:
        """
        دریافت پرداخت‌های یک کاربر.
        
        Args:
            db: آبجکت دیتابیس
            user_id: شناسه کاربر
            status: فیلتر براساس وضعیت (اختیاری)
            limit: محدودیت تعداد
            offset: شروع از چندمین رکورد
            
        Returns:
            List[Payment]: لیست پرداخت‌ها
        """
        try:
            # ساخت شرط SQL بر اساس فیلترها
            conditions = ["user_id = ?"]
            params = [user_id]
            
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            # اجرای کوئری
            query = f"SELECT payment_id FROM payments WHERE {' AND '.join(conditions)} " \
                   f"ORDER BY created_at DESC LIMIT ? OFFSET ?"
            
            params.extend([limit, offset])
            
            payment_ids = db.execute(query, params)
            
            # ساخت آبجکت‌های پرداخت
            payments = []
            for (payment_id,) in payment_ids:
                payment = cls(db, payment_id)
                if payment.load():
                    payments.append(payment)
            
            return payments
                
        except Exception as e:
            logger.error(f"خطا در دریافت پرداخت‌های کاربر {user_id}: {e}")
            return []
    
    @classmethod
    def get_pending_payments(cls, db, limit: int = 100) -> List['Payment']:
        """
        دریافت پرداخت‌های در انتظار.
        
        Args:
            db: آبجکت دیتابیس
            limit: محدودیت تعداد
            
        Returns:
            List[Payment]: لیست پرداخت‌های در انتظار
        """
        try:
            # اجرای کوئری
            payment_ids = db.execute(
                "SELECT payment_id FROM payments WHERE status = 'pending' "
                "ORDER BY created_at ASC LIMIT ?",
                (limit,)
            )
            
            # ساخت آبجکت‌های پرداخت
            payments = []
            for (payment_id,) in payment_ids:
                payment = cls(db, payment_id)
                if payment.load():
                    payments.append(payment)
            
            return payments
                
        except Exception as e:
            logger.error(f"خطا در دریافت پرداخت‌های در انتظار: {e}")
            return []
    
    @classmethod
    def get_payment_stats(cls, db, start_date: Optional[datetime] = None, 
                          end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        دریافت آمار پرداخت‌ها.
        
        Args:
            db: آبجکت دیتابیس
            start_date: تاریخ شروع (اختیاری)
            end_date: تاریخ پایان (اختیاری)
            
        Returns:
            Dict[str, Any]: آمار پرداخت‌ها
        """
        try:
            # ساخت شرط تاریخ
            conditions = []
            params = []
            
            if start_date:
                conditions.append("created_at >= ?")
                params.append(start_date)
                
            if end_date:
                conditions.append("created_at <= ?")
                params.append(end_date)
                
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            
            # تعداد کل پرداخت‌ها
            total_count = db.execute(
                f"SELECT COUNT(*) FROM payments {where_clause}",
                params
            )[0][0]
            
            # تعداد پرداخت‌ها به تفکیک وضعیت
            status_counts = {}
            for status in cls.PAYMENT_STATUSES:
                status_count = db.execute(
                    f"SELECT COUNT(*) FROM payments {where_clause} "
                    f"{'AND' if conditions else 'WHERE'} status = ?",
                    params + [status]
                )[0][0]
                status_counts[status] = status_count
            
            # مجموع مبالغ موفق
            completed_amount = db.execute(
                f"SELECT SUM(amount) FROM payments {where_clause} "
                f"{'AND' if conditions else 'WHERE'} status = 'completed'",
                params
            )[0][0] or 0
            
            # تعداد کاربران یکتا
            unique_users = db.execute(
                f"SELECT COUNT(DISTINCT user_id) FROM payments {where_clause}",
                params
            )[0][0]
            
            # میانگین مبلغ پرداختی
            avg_amount = db.execute(
                f"SELECT AVG(amount) FROM payments {where_clause} "
                f"{'AND' if conditions else 'WHERE'} status = 'completed'",
                params
            )[0][0] or 0
            
            return {
                'total_count': total_count,
                'status_counts': status_counts,
                'completed_amount': completed_amount,
                'unique_users': unique_users,
                'avg_amount': avg_amount
            }
                
        except Exception as e:
            logger.error(f"خطا در دریافت آمار پرداخت‌ها: {e}")
            return {
                'total_count': 0,
                'status_counts': {status: 0 for status in cls.PAYMENT_STATUSES},
                'completed_amount': 0,
                'unique_users': 0,
                'avg_amount': 0
            } 