#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
مهاجرت پایگاه داده از نسخه 2 به نسخه 3

این اسکریپت تغییرات لازم را برای ارتقای ساختار پایگاه داده از نسخه 2 به نسخه 3 اعمال می‌کند.
تغییرات نسخه 3 شامل:
- اضافه کردن جدول جدید notification_settings
- اضافه کردن جدول جدید crypto_wallets
- اضافه کردن ستون‌های جدید به جدول users برای نگهداری اطلاعات بیشتر کاربر
- بهبود ساختار جدول transactions
- اضافه کردن جدول pricing_plans
"""

import os
import sys
import argparse
import logging
import json
import datetime
from utils.timezone_utils import get_current_datetime
import sqlite3
from typing import List, Dict, Any, Optional, Tuple

# افزودن مسیر ریشه پروژه به sys.path برای واردسازی ماژول‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.config import Config
from utils.timezone_utils import get_current_datetime

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """
    پردازش آرگومان‌های خط فرمان
    
    :return: شیء آرگومان‌ها
    """
    parser = argparse.ArgumentParser(
        description='مهاجرت پایگاه داده از نسخه 2 به نسخه 3'
    )
    
    parser.add_argument(
        '--db-path',
        default=None,
        help='مسیر فایل پایگاه داده (اختیاری، در صورت عدم ارائه از config استفاده می‌شود)'
    )
    
    parser.add_argument(
        '--backup',
        action='store_true',
        help='ساخت نسخه پشتیبان قبل از مهاجرت'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='نمایش تغییرات بدون اعمال آن‌ها'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='ادامه مهاجرت حتی در صورت وجود خطا'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='نمایش اطلاعات بیشتر در خروجی'
    )
    
    return parser.parse_args()


def get_db_path(args_db_path: Optional[str] = None) -> str:
    """
    دریافت مسیر فایل پایگاه داده
    
    :param args_db_path: مسیر ارائه شده در آرگومان‌ها (اختیاری)
    :return: مسیر فایل پایگاه داده
    """
    if args_db_path:
        return args_db_path
    
    # دریافت از Config
    config = Config()
    db_path = config.get('DB_PATH', 'data/db/bot.d')
    
    # Ø§Ø·ÙÛÙØ§Ù Ø§Ø² ÙØ¬ÙØ¯ ÙØ³ÛØ± Ù¾ÙØ´ÙâÙØ§
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    return db_path


def create_backup(db_path: str) -> str:
    """
    Ø§ÛØ¬Ø§Ø¯ ÙØ³Ø®Ù Ù¾Ø´ØªÛØ¨Ø§Ù Ø§Ø² Ù¾Ø§ÛÚ¯Ø§Ù Ø¯Ø§Ø¯Ù
    
    :param db_path: ÙØ³ÛØ± ÙØ§ÛÙ Ù¾Ø§ÛÚ¯Ø§Ù Ø¯Ø§Ø¯Ù
    :return: ÙØ³ÛØ± ÙØ§ÛÙ Ù¾Ø´ØªÛØ¨Ø§Ù
    """
    import shutil
    from datetime import datetime
    
    # Ø§ÛØ¬Ø§Ø¯ ÙØ§Ù ÙØ§ÛÙ Ø¨Ø§ ØªØ§Ø±ÛØ® Ù Ø²ÙØ§Ù
    timestamp = get_current_datetime().strftime('%Y%m%d%H%M%S')
    backup_path = f"{db_path}.v2.{timestamp}.bak"
    
    # کپی فایل
    shutil.copy2(db_path, backup_path)
    logger.info(f"نسخه پشتیبان در {backup_path} ایجاد شد")
    
    return backup_path


def check_db_version(conn: sqlite3.Connection) -> int:
    """
    بررسی نسخه فعلی پایگاه داده
    
    :param conn: اتصال به پایگاه داده
    :return: شماره نسخه
    """
    cursor = conn.cursor()
    
    try:
        # بررسی وجود جدول versions
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='versions'")
        if not cursor.fetchone():
            logger.error("جدول versions وجود ندارد. ابتدا باید مهاجرت به نسخه 2 انجام شود")
            return 1
        
        # دریافت آخرین نسخه
        cursor.execute("SELECT MAX(version) FROM versions")
        version = cursor.fetchone()[0]
        
        if version is None:
            logger.warning("جدول versions خالی است. نسخه پایگاه داده نامشخص")
            return 1
        
        logger.info(f"نسخه فعلی پایگاه داده: {version}")
        return version
    
    except sqlite3.Error as e:
        logger.error(f"خطا در بررسی نسخه پایگاه داده: {str(e)}")
        return 1


def update_db_version(conn: sqlite3.Connection, version: int, dry_run: bool = False) -> bool:
    """
    به‌روزرسانی نسخه پایگاه داده
    
    :param conn: اتصال به پایگاه داده
    :param version: شماره نسخه جدید
    :param dry_run: بدون اعمال تغییرات
    :return: موفقیت یا عدم موفقیت عملیات
    """
    cursor = conn.cursor()
    
    try:
        # ثبت نسخه جدید
        if not dry_run:
            applied_at = get_current_datetime().isoformat()
            description = "مهاجرت از نسخه 2 به نسخه 3"
            
            cursor.execute(
                "INSERT INTO versions (version, applied_at, description) VALUES (?, ?, ?)",
                (version, applied_at, description)
            )
        
        logger.info(f"نسخه پایگاه داده به {version} به‌روزرسانی شد")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"خطا در به‌روزرسانی نسخه پایگاه داده: {str(e)}")
        return False


def get_table_schema(conn: sqlite3.Connection, table_name: str) -> List[Dict[str, Any]]:
    """
    دریافت ساختار یک جدول
    
    :param conn: اتصال به پایگاه داده
    :param table_name: نام جدول
    :return: لیست اطلاعات ستون‌ها
    """
    cursor = conn.cursor()
    
    try:
        # دریافت اطلاعات ستون‌ها
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [
            {
                'cid': row[0],
                'name': row[1],
                'type': row[2],
                'notnull': row[3],
                'dflt_value': row[4],
                'pk': row[5]
            }
            for row in cursor.fetchall()
        ]
        
        return columns
    
    except sqlite3.Error as e:
        logger.error(f"خطا در دریافت ساختار جدول {table_name}: {str(e)}")
        return []


def update_users_table(conn: sqlite3.Connection, dry_run: bool = False) -> bool:
    """
    به‌روزرسانی جدول users
    
    :param conn: اتصال به پایگاه داده
    :param dry_run: بدون اعمال تغییرات
    :return: موفقیت یا عدم موفقیت عملیات
    """
    cursor = conn.cursor()
    
    # ستون‌های جدید برای اضافه کردن
    new_columns = [
        ('profile_photo', 'TEXT', 'NULL'),
        ('bio', 'TEXT', 'NULL'),
        ('website', 'TEXT', 'NULL'),
        ('referral_code', 'TEXT', 'NULL'),
        ('referred_by', 'INTEGER', 'NULL'),
        ('verification_level', 'INTEGER', '0'),
        ('is_blocked', 'INTEGER', '0'),
        ('block_reason', 'TEXT', 'NULL'),
        ('login_attempts', 'INTEGER', '0'),
        ('last_login', 'TEXT', 'NULL')
    ]
    
    try:
        # دریافت ساختار فعلی
        columns = get_table_schema(conn, 'users')
        existing_columns = [col['name'] for col in columns]
        
        # افزودن ستون‌های جدید
        for column_name, column_type, default_value in new_columns:
            if column_name not in existing_columns:
                logger.info(f"افزودن ستون {column_name} به جدول users")
                if not dry_run:
                    default_clause = f"DEFAULT {default_value}" if default_value != 'NULL' else ""
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type} {default_clause}")
        
        # ایجاد شاخص برای ستون referral_code
        if 'referral_code' not in existing_columns:
            logger.info("ایجاد شاخص idx_users_referral_code")
            if not dry_run:
                cursor.execute("CREATE INDEX idx_users_referral_code ON users(referral_code)")
        
        # ایجاد شاخص برای ستون referred_by
        if 'referred_by' not in existing_columns:
            logger.info("ایجاد شاخص idx_users_referred_by")
            if not dry_run:
                cursor.execute("CREATE INDEX idx_users_referred_by ON users(referred_by)")
        
        logger.info("به‌روزرسانی جدول users با موفقیت انجام شد")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"خطا در به‌روزرسانی جدول users: {str(e)}")
        return False


def create_notification_settings_table(conn: sqlite3.Connection, dry_run: bool = False) -> bool:
    """
    ایجاد جدول notification_settings
    
    :param conn: اتصال به پایگاه داده
    :param dry_run: بدون اعمال تغییرات
    :return: موفقیت یا عدم موفقیت عملیات
    """
    cursor = conn.cursor()
    
    try:
        # بررسی وجود جدول
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notification_settings'")
        if cursor.fetchone():
            logger.info("جدول notification_settings قبلاً ایجاد شده است")
            return True
        
        logger.info("ایجاد جدول notification_settings")
        if not dry_run:
            cursor.execute("""
            CREATE TABLE notification_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                news_announcements INTEGER DEFAULT 1,
                price_alerts INTEGER DEFAULT 1,
                subscription_status INTEGER DEFAULT 1,
                payment_notifications INTEGER DEFAULT 1,
                security_alerts INTEGER DEFAULT 1,
                marketing_emails INTEGER DEFAULT 0,
                telegram_notifications INTEGER DEFAULT 1,
                email_notifications INTEGER DEFAULT 0,
                push_notifications INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id)
            )
            """)
            
            # ایجاد شاخص
            cursor.execute("CREATE INDEX idx_notification_settings_user_id ON notification_settings(user_id)")
        
        logger.info("جدول notification_settings با موفقیت ایجاد شد")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"خطا در ایجاد جدول notification_settings: {str(e)}")
        return False


def create_crypto_wallets_table(conn: sqlite3.Connection, dry_run: bool = False) -> bool:
    """
    ایجاد جدول crypto_wallets
    
    :param conn: اتصال به پایگاه داده
    :param dry_run: بدون اعمال تغییرات
    :return: موفقیت یا عدم موفقیت عملیات
    """
    cursor = conn.cursor()
    
    try:
        # بررسی وجود جدول
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crypto_wallets'")
        if cursor.fetchone():
            logger.info("جدول crypto_wallets قبلاً ایجاد شده است")
            return True
        
        logger.info("ایجاد جدول crypto_wallets")
        if not dry_run:
            cursor.execute("""
            CREATE TABLE crypto_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                currency TEXT NOT NULL,
                address TEXT NOT NULL,
                label TEXT,
                is_default INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_used_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """)
            
            # ایجاد شاخص‌ها
            cursor.execute("CREATE INDEX idx_crypto_wallets_user_id ON crypto_wallets(user_id)")
            cursor.execute("CREATE INDEX idx_crypto_wallets_currency ON crypto_wallets(currency)")
            cursor.execute("CREATE UNIQUE INDEX idx_crypto_wallets_address ON crypto_wallets(address)")
        
        logger.info("جدول crypto_wallets با موفقیت ایجاد شد")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"خطا در ایجاد جدول crypto_wallets: {str(e)}")
        return False


def update_transactions_table(conn: sqlite3.Connection, dry_run: bool = False) -> bool:
    """
    به‌روزرسانی جدول transactions
    
    :param conn: اتصال به پایگاه داده
    :param dry_run: بدون اعمال تغییرات
    :return: موفقیت یا عدم موفقیت عملیات
    """
    cursor = conn.cursor()
    
    # ستون‌های جدید برای اضافه کردن
    new_columns = [
        ('fee_amount', 'REAL', '0.0'),
        ('fee_currency', 'TEXT', 'NULL'),
        ('crypto_address', 'TEXT', 'NULL'),
        ('crypto_transaction_id', 'TEXT', 'NULL'),
        ('payment_provider', 'TEXT', 'NULL'),
        ('payment_method_details', 'TEXT', 'NULL'),
        ('shipping_address', 'TEXT', 'NULL'),
        ('shipping_tracking', 'TEXT', 'NULL'),
        ('ip_address', 'TEXT', 'NULL'),
        ('user_agent', 'TEXT', 'NULL'),
        ('notes', 'TEXT', 'NULL')
    ]
    
    try:
        # دریافت ساختار فعلی
        columns = get_table_schema(conn, 'transactions')
        
        if not columns:
            logger.warning("جدول transactions وجود ندارد، نادیده گرفته می‌شود")
            return True
        
        existing_columns = [col['name'] for col in columns]
        
        # افزودن ستون‌های جدید
        for column_name, column_type, default_value in new_columns:
            if column_name not in existing_columns:
                logger.info(f"افزودن ستون {column_name} به جدول transactions")
                if not dry_run:
                    default_clause = f"DEFAULT {default_value}" if default_value != 'NULL' else ""
                    cursor.execute(f"ALTER TABLE transactions ADD COLUMN {column_name} {column_type} {default_clause}")
        
        # ایجاد شاخص‌های جدید
        if 'crypto_transaction_id' not in existing_columns:
            logger.info("ایجاد شاخص idx_transactions_crypto_id")
            if not dry_run:
                cursor.execute("CREATE INDEX idx_transactions_crypto_id ON transactions(crypto_transaction_id)")
        
        if 'payment_provider' not in existing_columns:
            logger.info("ایجاد شاخص idx_transactions_provider")
            if not dry_run:
                cursor.execute("CREATE INDEX idx_transactions_provider ON transactions(payment_provider)")
        
        logger.info("به‌روزرسانی جدول transactions با موفقیت انجام شد")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"خطا در به‌روزرسانی جدول transactions: {str(e)}")
        return False


def create_pricing_plans_table(conn: sqlite3.Connection, dry_run: bool = False) -> bool:
    """
    ایجاد جدول pricing_plans
    
    :param conn: اتصال به پایگاه داده
    :param dry_run: بدون اعمال تغییرات
    :return: موفقیت یا عدم موفقیت عملیات
    """
    cursor = conn.cursor()
    
    try:
        # بررسی وجود جدول
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pricing_plans'")
        if cursor.fetchone():
            logger.info("جدول pricing_plans قبلاً ایجاد شده است")
            return True
        
        logger.info("ایجاد جدول pricing_plans")
        if not dry_run:
            cursor.execute("""
            CREATE TABLE pricing_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                description TEXT,
                duration_days INTEGER NOT NULL,
                price REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                features TEXT,
                is_active INTEGER DEFAULT 1,
                is_featured INTEGER DEFAULT 0,
                max_users INTEGER DEFAULT 0,
                discount_percentage REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0
            )
            """)
            
            # ایجاد شاخص‌ها
            cursor.execute("CREATE INDEX idx_pricing_plans_code ON pricing_plans(code)")
            cursor.execute("CREATE INDEX idx_pricing_plans_is_active ON pricing_plans(is_active)")
            
            # وارد کردن داده‌های اولیه
            current_time = get_current_datetime().isoformat()
            initial_plans = [
                (
                    'Basic Plan', 'basic', 'Basic features for new users', 30, 9.99, 'USD',
                    json.dumps({
                        'market_data': True,
                        'price_alerts': 5,
                        'portfolio_tracking': True,
                        'technical_indicators': ['MA', 'RSI', 'MACD'],
                        'api_access': False
                    }),
                    1, 0, 0, 0, current_time, current_time, 10
                ),
                (
                    'Premium Plan', 'premium', 'Advanced features for serious traders', 30, 19.99, 'USD',
                    json.dumps({
                        'market_data': True,
                        'price_alerts': 20,
                        'portfolio_tracking': True,
                        'technical_indicators': ['MA', 'RSI', 'MACD', 'Bollinger', 'Fibonacci'],
                        'api_access': True,
                        'priority_support': True
                    }),
                    1, 1, 0, 0, current_time, current_time, 20
                ),
                (
                    'VIP Plan', 'vip', 'All features for professional users', 30, 49.99, 'USD',
                    json.dumps({
                        'market_data': True,
                        'price_alerts': 'unlimited',
                        'portfolio_tracking': True,
                        'technical_indicators': 'all',
                        'api_access': True,
                        'priority_support': True,
                        'strategy_builder': True,
                        'ai_predictions': True
                    }),
                    1, 0, 0, 0, current_time, current_time, 30
                )
            ]
            
            cursor.executemany(
                """
                INSERT INTO pricing_plans (
                    name, code, description, duration_days, price, currency, features,
                    is_active, is_featured, max_users, discount_percentage, created_at, updated_at, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                initial_plans
            )
        
        logger.info("جدول pricing_plans با موفقیت ایجاد شد")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"خطا در ایجاد جدول pricing_plans: {str(e)}")
        return False


def update_subscriptions_table(conn: sqlite3.Connection, dry_run: bool = False) -> bool:
    """
    به‌روزرسانی جدول subscriptions
    
    :param conn: اتصال به پایگاه داده
    :param dry_run: بدون اعمال تغییرات
    :return: موفقیت یا عدم موفقیت عملیات
    """
    cursor = conn.cursor()
    
    # ستون‌های جدید برای اضافه کردن
    new_columns = [
        ('plan_id', 'INTEGER', 'NULL'),
        ('original_price', 'REAL', 'NULL'),
        ('discount_amount', 'REAL', '0'),
        ('auto_renew', 'INTEGER', '0'),
        ('cancellation_reason', 'TEXT', 'NULL'),
        ('max_devices', 'INTEGER', '1'),
        ('features_used', 'TEXT', 'NULL'),
        ('payment_id', 'TEXT', 'NULL')
    ]
    
    try:
        # دریافت ساختار فعلی
        columns = get_table_schema(conn, 'subscriptions')
        
        if not columns:
            logger.warning("جدول subscriptions وجود ندارد، نادیده گرفته می‌شود")
            return True
        
        existing_columns = [col['name'] for col in columns]
        
        # افزودن ستون‌های جدید
        for column_name, column_type, default_value in new_columns:
            if column_name not in existing_columns:
                logger.info(f"افزودن ستون {column_name} به جدول subscriptions")
                if not dry_run:
                    default_clause = f"DEFAULT {default_value}" if default_value != 'NULL' else ""
                    cursor.execute(f"ALTER TABLE subscriptions ADD COLUMN {column_name} {column_type} {default_clause}")
        
        # ایجاد شاخص‌های جدید
        if 'plan_id' not in existing_columns:
            logger.info("ایجاد شاخص idx_subscriptions_plan_id")
            if not dry_run:
                cursor.execute("CREATE INDEX idx_subscriptions_plan_id ON subscriptions(plan_id)")
        
        if 'payment_id' not in existing_columns:
            logger.info("ایجاد شاخص idx_subscriptions_payment_id")
            if not dry_run:
                cursor.execute("CREATE INDEX idx_subscriptions_payment_id ON subscriptions(payment_id)")
        
        logger.info("به‌روزرسانی جدول subscriptions با موفقیت انجام شد")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"خطا در به‌روزرسانی جدول subscriptions: {str(e)}")
        return False


def run_migration(
    db_path: str,
    create_backup_file: bool = False,
    dry_run: bool = False,
    force: bool = False,
    verbose: bool = False
) -> bool:
    """
    اجرای مهاجرت پایگاه داده
    
    :param db_path: مسیر فایل پایگاه داده
    :param create_backup_file: ایجاد نسخه پشتیبان
    :param dry_run: بدون اعمال تغییرات
    :param force: ادامه مهاجرت حتی در صورت وجود خطا
    :param verbose: نمایش اطلاعات بیشتر
    :return: موفقیت یا عدم موفقیت عملیات
    """
    # بررسی وجود فایل پایگاه داده
    if not os.path.isfile(db_path):
        logger.error(f"فایل پایگاه داده {db_path} وجود ندارد")
        return False
    
    # ایجاد نسخه پشتیبان
    if create_backup_file:
        create_backup(db_path)
    
    # ایجاد اتصال به پایگاه داده
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        # شروع تراکنش
        if not dry_run:
            conn.execute("BEGIN TRANSACTION")
        
        # بررسی نسخه فعلی
        version = check_db_version(conn)
        if version < 2:
            logger.error("نسخه پایگاه داده کمتر از 2 است. ابتدا باید مهاجرت به نسخه 2 انجام شود")
            if not force:
                return False
        
        if version >= 3:
            logger.info("نسخه پایگاه داده قبلاً به 3 ارتقا یافته است")
            return True
        
        # اجرای مراحل مهاجرت
        steps = [
            (update_users_table, "به‌روزرسانی جدول users"),
            (create_notification_settings_table, "ایجاد جدول notification_settings"),
            (create_crypto_wallets_table, "ایجاد جدول crypto_wallets"),
            (update_transactions_table, "به‌روزرسانی جدول transactions"),
            (create_pricing_plans_table, "ایجاد جدول pricing_plans"),
            (update_subscriptions_table, "به‌روزرسانی جدول subscriptions")
        ]
        
        success = True
        for step_func, step_desc in steps:
            logger.info(f"اجرای مرحله: {step_desc}")
            result = step_func(conn, dry_run)
            
            if not result:
                success = False
                logger.error(f"خطا در اجرای مرحله: {step_desc}")
                if not force:
                    break
        
        # به‌روزرسانی نسخه پایگاه داده
        if success or force:
            update_db_version(conn, 3, dry_run)
        
        # پایان تراکنش
        if not dry_run:
            if success or force:
                conn.execute("COMMIT")
                logger.info("تراکنش با موفقیت اعمال شد")
            else:
                conn.execute("ROLLBACK")
                logger.warning("تراکنش بازگردانی شد")
        else:
            logger.info("حالت dry-run: تغییرات اعمال نشد")
        
        return success
    
    except sqlite3.Error as e:
        logger.error(f"خطا در مهاجرت پایگاه داده: {str(e)}")
        if not dry_run:
            conn.execute("ROLLBACK")
            logger.warning("تراکنش بازگردانی شد")
        return False
    
    finally:
        conn.close()


def main() -> None:
    """
    تابع اصلی
    """
    args = parse_arguments()
    
    # تنظیم سطح لاگینگ
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # دریافت مسیر فایل پایگاه داده
    db_path = get_db_path(args.db_path)
    
    logger.info(f"شروع مهاجرت پایگاه داده از نسخه 2 به نسخه 3: {db_path}")
    
    # اجرای مهاجرت
    success = run_migration(
        db_path,
        args.backup,
        args.dry_run,
        args.force,
        args.verbose
    )
    
    # نمایش نتیجه
    if success:
        logger.info("مهاجرت پایگاه داده با موفقیت انجام شد")
    else:
        logger.error("مهاجرت پایگاه داده با خطا مواجه شد")
        sys.exit(1)


if __name__ == '__main__':
    main() 