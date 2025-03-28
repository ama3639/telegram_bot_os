#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
مهاجرت پایگاه داده از نسخه 1 به نسخه 2

این اسکریپت تغییرات لازم را برای ارتقای ساختار پایگاه داده از نسخه 1 به نسخه 2 اعمال می‌کند.
تغییرات نسخه 2 شامل:
- اضافه کردن فیلد منطقه زمانی به جدول users
- اصلاح ستون‌های timestamp برای نگهداری اطلاعات منطقه زمانی
- اضافه کردن جدول جدید user_preferences
- اضافه کردن شاخص‌های جدید برای بهبود کارایی
"""

import os
import sys
import argparse
import logging
import json
import datetime
from src.utils.timezone_utils import get_current_datetime
import sqlite3
from typing import List, Dict, Any, Optional, Tuple

# افزودن مسیر ریشه پروژه به sys.path برای واردسازی ماژول‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.config import Config
from src.utils.timezone_utils import get_current_datetime

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
        description='مهاجرت پایگاه داده از نسخه 1 به نسخه 2'
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
    db_path = config.get('DB_PATH', 'data/db/bot.db')
    
    # اطمینان از وجود مسیر پوشه‌ها
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    return db_path


def create_backup(db_path: str) -> str:
    """
    ایجاد نسخه پشتیبان از پایگاه داده
    
    :param db_path: مسیر فایل پایگاه داده
    :return: مسیر فایل پشتیبان
    """
    import shutil
    from datetime import datetime
    
    # ایجاد نام فایل با تاریخ و زمان
    timestamp = get_current_datetime().strftime('%Y%m%d%H%M%S')
    backup_path = f"{db_path}.v1.{timestamp}.bak"
    
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
            # اگر جدول وجود نداشته باشد، نسخه 1 است
            logger.info("جدول versions وجود ندارد. نسخه پایگاه داده: 1")
            return 1
        
        # دریافت آخرین نسخه
        cursor.execute("SELECT MAX(version) FROM versions")
        version = cursor.fetchone()[0]
        
        if version is None:
            logger.warning("جدول versions خالی است. نسخه پایگاه داده: 1")
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
        # بررسی وجود جدول versions
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='versions'")
        if not cursor.fetchone():
            # ایجاد جدول
            logger.info("ایجاد جدول versions")
            if not dry_run:
                cursor.execute("""
                CREATE TABLE versions (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL,
                    description TEXT
                )
                """)
        
        # ثبت نسخه جدید
        if not dry_run:
            applied_at = get_current_datetime().isoformat()
            description = "مهاجرت از نسخه 1 به نسخه 2"
            
            cursor.execute(
                "INSERT INTO versions (version, applied_at, description) VALUES (?, ?, ?)",
                (version, applied_at, description)
            )
        
        logger.info(f"نسخه پایگاه داده به {version} به‌روزرسانی شد")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"خطا در به‌روزرسانی نسخه پایگاه داده: {str(e)}")
        return False


def check_required_tables(conn: sqlite3.Connection) -> bool:
    """
    بررسی وجود جداول مورد نیاز
    
    :param conn: اتصال به پایگاه داده
    :return: آیا همه جداول مورد نیاز وجود دارند
    """
    required_tables = ['users', 'transactions', 'subscriptions']
    cursor = conn.cursor()
    
    try:
        # دریافت لیست جداول
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        # بررسی وجود جداول مورد نیاز
        missing_tables = [table for table in required_tables if table not in existing_tables]
        
        if missing_tables:
            logger.error(f"جداول مورد نیاز وجود ندارند: {', '.join(missing_tables)}")
            return False
        
        logger.info("همه جداول مورد نیاز وجود دارند")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"خطا در بررسی جداول: {str(e)}")
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


def get_table_indices(conn: sqlite3.Connection, table_name: str) -> List[Dict[str, Any]]:
    """
    دریافت شاخص‌های یک جدول
    
    :param conn: اتصال به پایگاه داده
    :param table_name: نام جدول
    :return: لیست اطلاعات شاخص‌ها
    """
    cursor = conn.cursor()
    
    try:
        # دریافت اطلاعات شاخص‌ها
        cursor.execute(f"PRAGMA index_list({table_name})")
        indices = [
            {
                'seq': row[0],
                'name': row[1],
                'unique': row[2],
                'origin': row[3],
                'partial': row[4]
            }
            for row in cursor.fetchall()
        ]
        
        # دریافت ستون‌های مربوط به هر شاخص
        for index in indices:
            cursor.execute(f"PRAGMA index_info({index['name']})")
            index['columns'] = [row[2] for row in cursor.fetchall()]
        
        return indices
    
    except sqlite3.Error as e:
        logger.error(f"خطا در دریافت شاخص‌های جدول {table_name}: {str(e)}")
        return []


def migrate_users_table(conn: sqlite3.Connection, dry_run: bool = False) -> bool:
    """
    مهاجرت جدول users
    
    :param conn: اتصال به پایگاه داده
    :param dry_run: بدون اعمال تغییرات
    :return: موفقیت یا عدم موفقیت عملیات
    """
    cursor = conn.cursor()
    
    try:
        # بررسی ساختار فعلی
        columns = get_table_schema(conn, 'users')
        column_names = [col['name'] for col in columns]
        
        # بررسی وجود ستون timezone
        if 'timezone' not in column_names:
            logger.info("افزودن ستون timezone به جدول users")
            if not dry_run:
                cursor.execute("ALTER TABLE users ADD COLUMN timezone TEXT DEFAULT 'UTC'")
        
        # بررسی وجود ستون‌های language و last_active
        if 'language' not in column_names:
            logger.info("افزودن ستون language به جدول users")
            if not dry_run:
                cursor.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'fa'")
        
        if 'last_active' not in column_names:
            logger.info("افزودن ستون last_active به جدول users")
            if not dry_run:
                current_time = get_current_datetime().isoformat()
                cursor.execute(f"ALTER TABLE users ADD COLUMN last_active TEXT DEFAULT '{current_time}'")
        
        # ایجاد شاخص‌های جدید
        indices = get_table_indices(conn, 'users')
        index_names = [idx['name'] for idx in indices]
        
        if 'idx_users_telegram_id' not in index_names:
            logger.info("ایجاد شاخص idx_users_telegram_id")
            if not dry_run:
                cursor.execute("CREATE INDEX idx_users_telegram_id ON users(telegram_id)")
        
        if 'idx_users_username' not in index_names:
            logger.info("ایجاد شاخص idx_users_username")
            if not dry_run:
                cursor.execute("CREATE INDEX idx_users_username ON users(username)")
        
        logger.info("مهاجرت جدول users با موفقیت انجام شد")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"خطا در مهاجرت جدول users: {str(e)}")
        return False


def create_user_preferences_table(conn: sqlite3.Connection, dry_run: bool = False) -> bool:
    """
    ایجاد جدول user_preferences
    
    :param conn: اتصال به پایگاه داده
    :param dry_run: بدون اعمال تغییرات
    :return: موفقیت یا عدم موفقیت عملیات
    """
    cursor = conn.cursor()
    
    try:
        # بررسی وجود جدول
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
        if cursor.fetchone():
            logger.info("جدول user_preferences قبلاً ایجاد شده است")
            return True
        
        logger.info("ایجاد جدول user_preferences")
        if not dry_run:
            cursor.execute("""
            CREATE TABLE user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, key)
            )
            """)
            
            # ایجاد شاخص‌ها
            cursor.execute("CREATE INDEX idx_user_preferences_user_id ON user_preferences(user_id)")
            cursor.execute("CREATE INDEX idx_user_preferences_key ON user_preferences(key)")
        
        logger.info("جدول user_preferences با موفقیت ایجاد شد")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"خطا در ایجاد جدول user_preferences: {str(e)}")
        return False


def update_timestamp_columns(conn: sqlite3.Connection, dry_run: bool = False) -> bool:
    """
    به‌روزرسانی ستون‌های timestamp برای پشتیبانی از منطقه زمانی
    
    :param conn: اتصال به پایگاه داده
    :param dry_run: بدون اعمال تغییرات
    :return: موفقیت یا عدم موفقیت عملیات
    """
    cursor = conn.cursor()
    timestamp_columns = [
        ('users', 'created_at'),
        ('users', 'updated_at'),
        ('transactions', 'timestamp'),
        ('transactions', 'created_at'),
        ('transactions', 'updated_at'),
        ('subscriptions', 'start_date'),
        ('subscriptions', 'end_date'),
        ('subscriptions', 'created_at'),
        ('subscriptions', 'updated_at')
    ]
    
    try:
        # بررسی وجود جداول و ستون‌ها
        for table, column in timestamp_columns:
            # بررسی وجود جدول
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                logger.warning(f"جدول {table} وجود ندارد، ستون {column} نادیده گرفته می‌شود")
                continue
            
            # بررسی وجود ستون
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]
            
            if column not in columns:
                logger.warning(f"ستون {column} در جدول {table} وجود ندارد، نادیده گرفته می‌شود")
                continue
            
            # استخراج و تبدیل داده‌ها
            if not dry_run:
                try:
                    # ابتدا داده‌های قبلی را استخراج می‌کنیم
                    cursor.execute(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL")
                    rows = cursor.fetchall()
                    
                    for row in rows:
                        row_id, timestamp = row
                        
                        # بررسی فرمت timestamp
                        try:
                            # اگر timestamp شامل اطلاعات منطقه زمانی نباشد، آن را به UTC تبدیل می‌کنیم
                            if timestamp and '+' not in timestamp and 'Z' not in timestamp and '-' not in timestamp[-6:]:
                                # زمان بدون منطقه زمانی را به UTC تبدیل می‌کنیم
                                new_timestamp = f"{timestamp}Z"
                                # به‌روزرسانی
                                cursor.execute(f"UPDATE {table} SET {column} = ? WHERE id = ?", (new_timestamp, row_id))
                        except Exception as e:
                            logger.warning(f"خطا در تبدیل timestamp {timestamp} در جدول {table}: {str(e)}")
                
                except sqlite3.Error as e:
                    logger.error(f"خطا در به‌روزرسانی ستون {column} در جدول {table}: {str(e)}")
        
        logger.info("به‌روزرسانی ستون‌های timestamp با موفقیت انجام شد")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"خطا در به‌روزرسانی ستون‌های timestamp: {str(e)}")
        return False


def add_missing_indices(conn: sqlite3.Connection, dry_run: bool = False) -> bool:
    """
    افزودن شاخص‌های گم شده
    
    :param conn: اتصال به پایگاه داده
    :param dry_run: بدون اعمال تغییرات
    :return: موفقیت یا عدم موفقیت عملیات
    """
    cursor = conn.cursor()
    
    # شاخص‌های مورد نیاز
    required_indices = [
        ('transactions', 'idx_transactions_user_id', 'user_id'),
        ('transactions', 'idx_transactions_status', 'status'),
        ('transactions', 'idx_transactions_type', 'transaction_type'),
        ('transactions', 'idx_transactions_created_at', 'created_at'),
        ('subscriptions', 'idx_subscriptions_user_id', 'user_id'),
        ('subscriptions', 'idx_subscriptions_status', 'status'),
        ('subscriptions', 'idx_subscriptions_end_date', 'end_date')
    ]
    
    try:
        for table, index_name, column in required_indices:
            # بررسی وجود جدول
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                logger.warning(f"جدول {table} وجود ندارد، شاخص {index_name} نادیده گرفته می‌شود")
                continue
            
            # بررسی وجود ستون
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]
            
            if column not in columns:
                logger.warning(f"ستون {column} در جدول {table} وجود ندارد، شاخص {index_name} نادیده گرفته می‌شود")
                continue
            
            # بررسی وجود شاخص
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index_name}'")
            if cursor.fetchone():
                logger.info(f"شاخص {index_name} قبلاً ایجاد شده است")
                continue
            
            # ایجاد شاخص
            logger.info(f"ایجاد شاخص {index_name}")
            if not dry_run:
                cursor.execute(f"CREATE INDEX {index_name} ON {table}({column})")
        
        logger.info("افزودن شاخص‌های گم شده با موفقیت انجام شد")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"خطا در افزودن شاخص‌های گم شده: {str(e)}")
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
        if version >= 2:
            logger.info("نسخه پایگاه داده قبلاً به 2 ارتقا یافته است")
            return True
        
        # بررسی جداول مورد نیاز
        if not check_required_tables(conn) and not force:
            logger.error("جداول مورد نیاز وجود ندارند. مهاجرت لغو شد")
            return False
        
        # اجرای مراحل مهاجرت
        steps = [
            (migrate_users_table, "به‌روزرسانی جدول users"),
            (create_user_preferences_table, "ایجاد جدول user_preferences"),
            (update_timestamp_columns, "به‌روزرسانی ستون‌های timestamp"),
            (add_missing_indices, "افزودن شاخص‌های گم شده")
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
            update_db_version(conn, 2, dry_run)
        
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
    
    logger.info(f"شروع مهاجرت پایگاه داده از نسخه 1 به نسخه 2: {db_path}")
    
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