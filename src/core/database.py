#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول مدیریت پایگاه داده.

این ماژول مسئول ارتباط با پایگاه داده، اجرای کوئری‌ها و مدیریت تراکنش‌ها است.
فعلاً از SQLite استفاده می‌کند، اما قابلیت ارتقا به دیگر پایگاه‌های داده را دارد.

تاریخ ایجاد: ۱۴۰۴/۰۱/۰۷
"""


from datetime import timezone
import os
import logging
import sqlite3
import time
import json
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timezone
import threading

logger = logging.getLogger(__name__)

class Database:
    """
    کلاس مدیریت پایگاه داده با پشتیبانی از SQLite.
    در آینده می‌تواند به MySQL یا PostgreSQL ارتقا یابد.
    """
    
    def __init__(self, db_path: str):
        """
        مقداردهی اولیه کلاس پایگاه داده.
        
        پارامترها:
            db_path: مسیر فایل پایگاه داده SQLite
        """
        self.db_path = db_path
        self.initialized = False
        self.lock = threading.RLock()
        
        #   اطمینان از وجود دایرکتوری
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        logger.info(f"پایگاه داده در مسیر {db_path} آماده‌سازی شد.")
    
    def get_connection(self) -> sqlite3.Connection:
        """
        ایجاد و بازگرداندن یک اتصال به پایگاه داده.
        
        بازگشت:
            sqlite3.Connection: اتصال به پایگاه داده
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # برای دسترسی به ستون‌ها با نام
        
        # فعال‌سازی پشتیبانی از کلیدهای خارجی
        conn.execute("PRAGMA foreign_keys = ON")
        
        return conn
    
    def initialize(self) -> None:
        """
        ایجاد جداول پایگاه داده در صورت عدم وجود.
        """
        if self.initialized:
            return
            
        with self.lock:
            conn = self.get_connection()
            try:
                # جدول کاربران
                conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    username TEXT,
                    language TEXT DEFAULT 'fa',
                    is_admin INTEGER DEFAULT 0,
                    is_blocked INTEGER DEFAULT 0,
                    created_at TEXT,
                    last_activity TEXT,
                    subscription_plan TEXT DEFAULT NULL,
                    subscription_expiry TEXT DEFAULT NULL,
                    settings TEXT DEFAULT '{}'
                )
                """)
                
                # جدول پرداخت‌ها
                conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    currency TEXT,
                    gateway TEXT,
                    reference_id TEXT,
                    status TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    description TEXT,
                    plan_name TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """)
                
                # جدول گزارش‌ها
                conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT,
                    content TEXT,
                    created_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """)
                
                # جدول تنظیمات
                conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )
                """)
                
                # ایجاد ایندکس‌ها
                conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments (user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports (user_id)")
                
                conn.commit()
                self.initialized = True
                logger.info("جداول پایگاه داده با موفقیت ایجاد شدند.")
                
            except sqlite3.Error as e:
                logger.error(f"خطا در ایجاد جداول پایگاه داده: {str(e)}")
                raise
                
            finally:
                conn.close()
    
    def add_or_update_user(self, user_id: int, first_name: str, last_name: Optional[str] = None, 
                          username: Optional[str] = None) -> None:
        """
        افزودن یا به‌روزرسانی اطلاعات کاربر در پایگاه داده.
        
        پارامترها:
            user_id: شناسه کاربر تلگرام
            first_name: نام کاربر
            last_name: نام خانوادگی کاربر (اختیاری)
            username: نام کاربری تلگرام (اختیاری)
        """
        now = datetime.now(timezone.utc).isoformat()
        
        with self.lock:
            conn = self.get_connection()
            try:
                # بررسی وجود کاربر
                cursor = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                user_exists = cursor.fetchone() is not None
                
                if user_exists:
                    # به‌روزرسانی کاربر موجود
                    conn.execute("""
                    UPDATE users SET
                        first_name = ?,
                        last_name = ?,
                        username = ?,
                        last_activity = ?
                    WHERE user_id = ?
                    """, (first_name, last_name, username, now, user_id))
                    
                else:
                    # افزودن کاربر جدید
                    conn.execute("""
                    INSERT INTO users (
                        user_id, first_name, last_name, username, created_at, last_activity
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (user_id, first_name, last_name, username, now, now))
                
                conn.commit()
                
            except sqlite3.Error as e:
                logger.error(f"خطا در افزودن/به‌روزرسانی کاربر: {str(e)}")
                conn.rollback()
                raise
                
            finally:
                conn.close()
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        دریافت اطلاعات کاربر از پایگاه داده.
        
        پارامترها:
            user_id: شناسه کاربر تلگرام
            
        بازگشت:
            Dict[str, Any] یا None: اطلاعات کاربر یا None اگر کاربر یافت نشود
        """
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                
                if row:
                    user_data = dict(row)
                    
                    # تبدیل تنظیمات از JSON
                    if 'settings' in user_data and user_data['settings']:
                        try:
                            user_data['settings'] = json.loads(user_data['settings'])
                        except json.JSONDecodeError:
                            user_data['settings'] = {}
                    
                    return user_data
                return None
                
            except sqlite3.Error as e:
                logger.error(f"خطا در دریافت اطلاعات کاربر: {str(e)}")
                raise
                
            finally:
                conn.close()
    
    def get_user_language(self, user_id: int) -> Optional[str]:
        """
        دریافت زبان انتخابی کاربر.
        
        پارامترها:
            user_id: شناسه کاربر تلگرام
            
        بازگشت:
            str یا None: کد زبان کاربر یا None اگر کاربر یافت نشود
        """
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                
                if row:
                    return row['language']
                return None
                
            except sqlite3.Error as e:
                logger.error(f"خطا در دریافت زبان کاربر: {str(e)}")
                raise
                
            finally:
                conn.close()
    
    def update_user_language(self, user_id: int, language: str) -> None:
        """
        به‌روزرسانی زبان کاربر.
        
        پارامترها:
            user_id: شناسه کاربر تلگرام
            language: کد زبان
        """
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user_id))
                conn.commit()
                
            except sqlite3.Error as e:
                logger.error(f"خطا در به‌روزرسانی زبان کاربر: {str(e)}")
                conn.rollback()
                raise
                
            finally:
                conn.close()
    
    def add_payment(self, user_id: int, amount: float, currency: str, 
                  gateway: str, reference_id: str, plan_name: Optional[str] = None, 
                  description: Optional[str] = None) -> int:
        """
        افزودن رکورد پرداخت جدید.
        
        پارامترها:
            user_id: شناسه کاربر تلگرام
            amount: مبلغ پرداخت
            currency: واحد ارز
            gateway: درگاه پرداخت
            reference_id: شناسه مرجع تراکنش
            plan_name: نام طرح اشتراک (اختیاری)
            description: توضیحات پرداخت (اختیاری)
            
        بازگشت:
            int: شناسه رکورد ایجاد شده
        """
        now = datetime.now(timezone.utc).isoformat()
        
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.execute("""
                INSERT INTO payments (
                    user_id, amount, currency, gateway, reference_id, status, 
                    created_at, updated_at, description, plan_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, amount, currency, gateway, reference_id, 'pending', 
                     now, now, description, plan_name))
                
                conn.commit()
                return cursor.lastrowid
                
            except sqlite3.Error as e:
                logger.error(f"خطا در افزودن رکورد پرداخت: {str(e)}")
                conn.rollback()
                raise
                
            finally:
                conn.close()
    
    def update_payment_status(self, payment_id: int, status: str) -> None:
        """
        به‌روزرسانی وضعیت پرداخت.
        
        پارامترها:
            payment_id: شناسه پرداخت
            status: وضعیت جدید (pending, completed, failed, refunded)
        """
        now = datetime.now(timezone.utc).isoformat()
        
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                UPDATE payments SET
                    status = ?,
                    updated_at = ?
                WHERE id = ?
                """, (status, now, payment_id))
                
                conn.commit()
                
            except sqlite3.Error as e:
                logger.error(f"خطا در به‌روزرسانی وضعیت پرداخت: {str(e)}")
                conn.rollback()
                raise
                
            finally:
                conn.close()
    
    def get_payment(self, payment_id: int) -> Optional[Dict[str, Any]]:
        """
        دریافت اطلاعات یک پرداخت.
        
        پارامترها:
            payment_id: شناسه پرداخت
            
        بازگشت:
            Dict[str, Any] یا None: اطلاعات پرداخت یا None اگر یافت نشود
        """
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
            except sqlite3.Error as e:
                logger.error(f"خطا در دریافت اطلاعات پرداخت: {str(e)}")
                raise
                
            finally:
                conn.close()
    
    def get_user_payments(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        دریافت لیست پرداخت‌های یک کاربر.
        
        پارامترها:
            user_id: شناسه کاربر تلگرام
            limit: حداکثر تعداد رکوردها
            
        بازگشت:
            List[Dict[str, Any]]: لیست پرداخت‌ها
        """
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.execute("""
                SELECT * FROM payments 
                WHERE user_id = ? 
                ORDER BY created_at DESC
                LIMIT ?
                """, (user_id, limit))
                
                return [dict(row) for row in cursor.fetchall()]
                
            except sqlite3.Error as e:
                logger.error(f"خطا در دریافت لیست پرداخت‌های کاربر: {str(e)}")
                raise
                
            finally:
                conn.close()
    
    def add_report(self, user_id: int, report_type: str, content: str) -> int:
        """
        افزودن یک گزارش جدید.
        
        پارامترها:
            user_id: شناسه کاربر تلگرام
            report_type: نوع گزارش
            content: محتوای گزارش (ترجیحاً JSON)
            
        بازگشت:
            int: شناسه گزارش ایجاد شده
        """
        now = datetime.now(timezone.utc).isoformat()
        
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.execute("""
                INSERT INTO reports (user_id, type, content, created_at)
                VALUES (?, ?, ?, ?)
                """, (user_id, report_type, content, now))
                
                conn.commit()
                return cursor.lastrowid
                
            except sqlite3.Error as e:
                logger.error(f"خطا در افزودن گزارش: {str(e)}")
                conn.rollback()
                raise
                
            finally:
                conn.close()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        دریافت یک تنظیم از جدول تنظیمات.
        
        پارامترها:
            key: کلید تنظیم
            default: مقدار پیش‌فرض در صورت عدم وجود
            
        بازگشت:
            Any: مقدار تنظیم
        """
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                
                if row:
                    try:
                        return json.loads(row['value'])
                    except json.JSONDecodeError:
                        return row['value']
                return default
                
            except sqlite3.Error as e:
                logger.error(f"خطا در دریافت تنظیم: {str(e)}")
                raise
                
            finally:
                conn.close()
    
    def set_setting(self, key: str, value: Any) -> None:
        """
        تنظیم یک مقدار در جدول تنظیمات.
        
        پارامترها:
            key: کلید تنظیم
            value: مقدار تنظیم (می‌تواند هر نوع داده‌ای باشد که قابل تبدیل به JSON باشد)
        """
        now = datetime.now(timezone.utc).isoformat()
        
        # تبدیل مقدار به JSON اگر یک نوع پیچیده باشد
        if not isinstance(value, (str, int, float, bool)) or value is None:
            value_str = json.dumps(value)
        else:
            value_str = str(value)
        
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                """, (key, value_str, now))
                
                conn.commit()
                
            except sqlite3.Error as e:
                logger.error(f"خطا در تنظیم مقدار: {str(e)}")
                conn.rollback()
                raise
                
            finally:
                conn.close()
    
    def execute_query(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """
        اجرای یک کوئری دلخواه SQL.
        
        پارامترها:
            query: کوئری SQL
            params: پارامترهای کوئری
            
        بازگشت:
            List[Dict[str, Any]]: نتایج کوئری
            
        هشدار: این تابع باید با احتیاط استفاده شود تا از حملات SQL Injection جلوگیری شود.
        """
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.execute(query, params)
                
                # اگر DML است (INSERT, UPDATE, DELETE)
                if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                    conn.commit()
                    return []
                
                # اگر SELECT است
                return [dict(row) for row in cursor.fetchall()]
                
            except sqlite3.Error as e:
                if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                    conn.rollback()
                    
                logger.error(f"خطا در اجرای کوئری: {str(e)}")
                raise
                
            finally:
                conn.close()
    
    def backup_database(self, backup_path: str) -> bool:
        """
        تهیه پشتیبان از پایگاه داده.
        
        پارامترها:
            backup_path: مسیر فایل پشتیبان
            
        بازگشت:
            bool: True در صورت موفقیت، False در غیر این صورت
        """
        try:
            # اطمینان از وجود دایرکتوری
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            src_conn = self.get_connection()
            dst_conn = sqlite3.connect(backup_path)
            
            with self.lock:
                src_conn.backup(dst_conn)
            
            src_conn.close()
            dst_conn.close()
            
            logger.info(f"پشتیبان‌گیری از پایگاه داده در مسیر {backup_path} با موفقیت انجام شد.")
            return True
            
        except Exception as e:
            logger.error(f"خطا در پشتیبان‌گیری از پایگاه داده: {str(e)}")
            return False