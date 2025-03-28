#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
اسکریپت پاکسازی داده‌های قدیمی

این اسکریپت برای حفظ کارایی و کاهش حجم پایگاه داده، داده‌های قدیمی و غیرضروری را پاکسازی می‌کند.
قابلیت‌های اصلی:
- حذف رکوردهای قدیمی از جداول
- پاکسازی فایل‌های لاگ قدیمی
- حذف فایل‌های پشتیبان زائد
- حذف فایل‌های موقت
- بهینه‌سازی پایگاه داده
- فشرده‌سازی پایگاه داده
"""

import os
import sys
import argparse
import logging
import time
import datetime
import sqlite3
import json
import glob
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

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
        description='پاکسازی داده‌های قدیمی و غیرضروری'
    )
    
    parser.add_argument(
        '--db-path',
        default=None,
        help='مسیر فایل پایگاه داده (اختیاری، در صورت عدم ارائه از config استفاده می‌شود)'
    )
    
    parser.add_argument(
        '--config-path',
        default='.env',
        help='مسیر فایل تنظیمات (پیش‌فرض: .env)'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='اجرای تمام عملیات پاکسازی'
    )
    
    parser.add_argument(
        '--cleanup-db',
        action='store_true',
        help='پاکسازی رکوردهای قدیمی در پایگاه داده'
    )
    
    parser.add_argument(
        '--optimize-db',
        action='store_true',
        help='بهینه‌سازی پایگاه داده'
    )
    
    parser.add_argument(
        '--cleanup-logs',
        action='store_true',
        help='پاکسازی فایل‌های لاگ قدیمی'
    )
    
    parser.add_argument(
        '--cleanup-backups',
        action='store_true',
        help='پاکسازی فایل‌های پشتیبان قدیمی'
    )
    
    parser.add_argument(
        '--cleanup-temp',
        action='store_true',
        help='پاکسازی فایل‌های موقت'
    )
    
    parser.add_argument(
        '--age-days',
        type=int,
        default=30,
        help='حداقل سن به روز برای پاکسازی داده‌ها (پیش‌فرض: 30)'
    )
    
    parser.add_argument(
        '--max-log-size-mb',
        type=int,
        default=100,
        help='حداکثر اندازه مجاز برای فایل‌های لاگ به مگابایت (پیش‌فرض: 100)'
    )
    
    parser.add_argument(
        '--keep-backups',
        type=int,
        default=5,
        help='تعداد فایل‌های پشتیبان برای نگهداری (پیش‌فرض: 5)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='نمایش تغییرات بدون اعمال آن‌ها'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='اجرای عملیات بدون درخواست تأیید'
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
    
    return db_path


def cleanup_database(
    db_path: str, 
    age_days: int,
    dry_run: bool = False,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    پاکسازی رکوردهای قدیمی از پایگاه داده
    
    :param db_path: مسیر فایل پایگاه داده
    :param age_days: حداقل سن به روز برای پاکسازی
    :param dry_run: بدون اعمال تغییرات
    :param verbose: نمایش اطلاعات بیشتر
    :return: آمار پاکسازی
    """
    # بررسی وجود فایل پایگاه داده
    if not os.path.exists(db_path):
        logger.error(f"فایل پایگاه داده {db_path} وجود ندارد")
        return {'status': 'error', 'message': 'فایل پایگاه داده وجود ندارد'}
    
    try:
        # محاسبه تاریخ مرجع برای پاکسازی
        cutoff_date = (get_current_datetime() - datetime.timedelta(days=age_days)).isoformat()
        
        # اتصال به پایگاه داده
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # جداول و ستون‌های تاریخ برای پاکسازی
        tables_to_clean = [
            {'table': 'transactions', 'date_column': 'timestamp', 'conditions': "status IN ('completed', 'failed', 'expired')"},
            {'table': 'logs', 'date_column': 'created_at', 'conditions': "level NOT IN ('ERROR', 'CRITICAL')"},
            {'table': 'notifications', 'date_column': 'created_at', 'conditions': "status IN ('sent', 'failed')"},
            {'table': 'user_activities', 'date_column': 'timestamp', 'conditions': None},
        ]
        
        # آمار پاکسازی
        stats = {'tables': {}}
        
        for table_info in tables_to_clean:
            table = table_info['table']
            date_column = table_info['date_column']
            conditions = table_info['conditions']
            
            # بررسی وجود جدول
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                if verbose:
                    logger.info(f"جدول {table} وجود ندارد، نادیده گرفته می‌شود")
                continue
            
            # بررسی وجود ستون تاریخ
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row['name'] for row in cursor.fetchall()]
            
            if date_column not in columns:
                if verbose:
                    logger.info(f"ستون {date_column} در جدول {table} وجود ندارد، نادیده گرفته می‌شود")
                continue
            
            # شمارش رکوردهای قبل از پاکسازی
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            before_count = cursor.fetchone()[0]
            
            # ساخت شرط پاکسازی
            where_clause = f"{date_column} < '{cutoff_date}'"
            if conditions:
                where_clause += f" AND ({conditions})"
            
            # شمارش رکوردهای قابل پاکسازی
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {where_clause}")
            to_delete_count = cursor.fetchone()[0]
            
            # انجام پاکسازی
            if not dry_run and to_delete_count > 0:
                cursor.execute(f"DELETE FROM {table} WHERE {where_clause}")
                
                # بررسی تعداد رکوردهای حذف شده
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                after_count = cursor.fetchone()[0]
                deleted_count = before_count - after_count
                
                logger.info(f"پاکسازی جدول {table}: {deleted_count} رکورد حذف شد")
            else:
                deleted_count = to_delete_count
                if verbose:
                    action = "خواهد شد" if to_delete_count > 0 else "وجود ندارد"
                    logger.info(f"جدول {table}: {to_delete_count} رکورد پاکسازی {action}")
            
            # ذخیره آمار
            stats['tables'][table] = {
                'before_count': before_count,
                'deleted_count': deleted_count,
                'after_count': before_count - deleted_count
            }
        
        # حذف تراکنش‌های منقضی شده
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subscriptions'")
        if cursor.fetchone():
            # بررسی وجود ستون end_date
            cursor.execute("PRAGMA table_info(subscriptions)")
            columns = [row['name'] for row in cursor.fetchall()]
            
            if 'end_date' in columns:
                # شمارش اشتراک‌های منقضی شده
                cursor.execute(f"SELECT COUNT(*) FROM subscriptions WHERE end_date < '{cutoff_date}' AND status != 'expired'")
                expired_count = cursor.fetchone()[0]
                
                # به‌روزرسانی وضعیت اشتراک‌های منقضی شده
                if not dry_run and expired_count > 0:
                    cursor.execute(f"UPDATE subscriptions SET status = 'expired' WHERE end_date < '{cutoff_date}' AND status != 'expired'")
                    logger.info(f"به‌روزرسانی وضعیت اشتراک‌ها: {expired_count} اشتراک منقضی شده، به‌روزرسانی شد")
                elif verbose:
                    action = "به‌روزرسانی خواهد شد" if expired_count > 0 else "وجود ندارد"
                    logger.info(f"اشتراک‌های منقضی شده: {expired_count} اشتراک {action}")
                
                stats['expired_subscriptions'] = expired_count
        
        # اعمال تغییرات
        if not dry_run:
            conn.commit()
        
        # بستن اتصال
        conn.close()
        
        stats['status'] = 'success'
        stats['db_path'] = db_path
        stats['cutoff_date'] = cutoff_date
        stats['age_days'] = age_days
        
        return stats
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پاکسازی پایگاه داده: {str(e)}")
        return {'status': 'error', 'message': str(e)}
    
    except Exception as e:
        logger.error(f"خطا در پاکسازی پایگاه داده: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def optimize_database(
    db_path: str,
    dry_run: bool = False,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    بهینه‌سازی پایگاه داده
    
    :param db_path: مسیر فایل پایگاه داده
    :param dry_run: بدون اعمال تغییرات
    :param verbose: نمایش اطلاعات بیشتر
    :return: آمار بهینه‌سازی
    """
    # بررسی وجود فایل پایگاه داده
    if not os.path.exists(db_path):
        logger.error(f"فایل پایگاه داده {db_path} وجود ندارد")
        return {'status': 'error', 'message': 'فایل پایگاه داده وجود ندارد'}
    
    try:
        # اندازه قبل از بهینه‌سازی
        before_size = os.path.getsize(db_path)
        
        if not dry_run:
            # اتصال به پایگاه داده
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # اجرای VACUUM برای فشرده‌سازی پایگاه داده
            cursor.execute("VACUUM")
            
            # اجرای ANALYZE برای به‌روزرسانی آمار
            cursor.execute("ANALYZE")
            
            # بستن اتصال
            conn.close()
            
            # اندازه بعد از بهینه‌سازی
            after_size = os.path.getsize(db_path)
            
            # محاسبه میزان کاهش حجم
            size_diff = before_size - after_size
            size_diff_mb = round(size_diff / (1024 * 1024), 2)
            size_diff_percent = round((size_diff / before_size) * 100, 2) if before_size > 0 else 0
            
            logger.info(f"بهینه‌سازی پایگاه داده انجام شد. کاهش حجم: {size_diff_mb} مگابایت ({size_diff_percent}%)")
        else:
            logger.info(f"بهینه‌سازی پایگاه داده (حالت dry-run): اندازه فعلی {round(before_size / (1024 * 1024), 2)} مگابایت")
            after_size = before_size
            size_diff = 0
            size_diff_percent = 0
        
        return {
            'status': 'success',
            'db_path': db_path,
            'before_size_bytes': before_size,
            'after_size_bytes': after_size,
            'size_diff_bytes': size_diff,
            'size_diff_mb': round(size_diff / (1024 * 1024), 2),
            'size_diff_percent': size_diff_percent
        }
    
    except sqlite3.Error as e:
        logger.error(f"خطا در بهینه‌سازی پایگاه داده: {str(e)}")
        return {'status': 'error', 'message': str(e)}
    
    except Exception as e:
        logger.error(f"خطا در بهینه‌سازی پایگاه داده: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def cleanup_logs(
    age_days: int,
    max_size_mb: int,
    dry_run: bool = False,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    پاکسازی فایل‌های لاگ قدیمی
    
    :param age_days: حداقل سن به روز برای پاکسازی
    :param max_size_mb: حداکثر اندازه مجاز برای فایل‌های لاگ به مگابایت
    :param dry_run: بدون اعمال تغییرات
    :param verbose: نمایش اطلاعات بیشتر
    :return: آمار پاکسازی
    """
    try:
        # مسیر دایرکتوری لاگ‌ها
        logs_dir = 'logs'
        if not os.path.exists(logs_dir):
            logger.warning(f"دایرکتوری لاگ {logs_dir} وجود ندارد")
            return {'status': 'warning', 'message': 'دایرکتوری لاگ وجود ندارد'}
        
        # محاسبه تاریخ مرجع برای پاکسازی
        cutoff_date = get_current_datetime() - datetime.timedelta(days=age_days)
        
        # لیست همه فایل‌های لاگ
        all_log_files = glob.glob(os.path.join(logs_dir, '*.log*'))
        all_log_files.extend(glob.glob(os.path.join(logs_dir, '*/*.log*')))
        
        # آمار پاکسازی
        stats = {
            'total_files': len(all_log_files),
            'deleted_files': 0,
            'deleted_bytes': 0,
            'truncated_files': 0,
            'truncated_bytes': 0,
            'files': []
        }
        
        # پاکسازی فایل‌های لاگ قدیمی
        for log_file in all_log_files:
            file_stats = os.stat(log_file)
            file_modified_time = datetime.datetime.fromtimestamp(file_stats.st_mtime)
            file_size = file_stats.st_size
            file_size_mb = file_size / (1024 * 1024)
            
            # فرمت نام فایل برای بررسی tarball های روتیشن شده
            is_rotated = re.search(r'\.log\.\d+(?:\.gz)?$', log_file) is not None
            
            file_info = {
                'path': log_file,
                'size_bytes': file_size,
                'size_mb': round(file_size_mb, 2),
                'modified': file_modified_time.isoformat(),
                'is_rotated': is_rotated,
                'action': 'keep'
            }
            
            # بررسی شرایط پاکسازی
            if is_rotated and file_modified_time < cutoff_date:
                # فایل‌های روتیشن شده قدیمی حذف می‌شوند
                if not dry_run:
                    os.remove(log_file)
                
                file_info['action'] = 'delete'
                stats['deleted_files'] += 1
                stats['deleted_bytes'] += file_size
                
                if verbose:
                    logger.info(f"فایل لاگ قدیمی حذف شد: {log_file} ({round(file_size_mb, 2)} مگابایت)")
            
            elif not is_rotated and file_size_mb > max_size_mb:
                # فایل‌های لاگ فعلی بزرگ‌تر از حد مجاز، کوتاه می‌شوند
                if not dry_run:
                    # نگهداری 10% ابتدای فایل (معمولاً لاگ‌های مهم‌تر)
                    keep_size = int(max_size_mb * 1024 * 1024 * 0.1)
                    
                    with open(log_file, 'rb') as f:
                        content = f.read(keep_size)
                    
                    with open(log_file, 'w') as f:
                        f.write(content.decode('utf-8', errors='ignore'))
                        f.write("\n\n... بخشی از لاگ‌ها به دلیل حجم زیاد حذف شدند ...\n\n")
                
                file_info['action'] = 'truncate'
                stats['truncated_files'] += 1
                stats['truncated_bytes'] += (file_size - keep_size)
                
                if verbose:
                    logger.info(f"فایل لاگ بزرگ کوتاه شد: {log_file} ({round(file_size_mb, 2)} مگابایت)")
            
            elif verbose:
                logger.info(f"فایل لاگ نگهداری شد: {log_file} ({round(file_size_mb, 2)} مگابایت)")
            
            stats['files'].append(file_info)
        
        # خلاصه نتایج
        total_freed = stats['deleted_bytes'] + stats['truncated_bytes']
        logger.info(f"پاکسازی لاگ‌ها: {stats['deleted_files']} فایل حذف، {stats['truncated_files']} فایل کوتاه، {round(total_freed / (1024 * 1024), 2)} مگابایت آزاد شد")
        
        stats['status'] = 'success'
        stats['total_freed_mb'] = round(total_freed / (1024 * 1024), 2)
        
        return stats
    
    except Exception as e:
        logger.error(f"خطا در پاکسازی فایل‌های لاگ: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def cleanup_backups(
    keep_count: int,
    dry_run: bool = False, 
    verbose: bool = False
) -> Dict[str, Any]:
    """
    پاکسازی فایل‌های پشتیبان قدیمی
    
    :param keep_count: تعداد فایل‌های پشتیبان برای نگهداری
    :param dry_run: بدون اعمال تغییرات
    :param verbose: نمایش اطلاعات بیشتر
    :return: آمار پاکسازی
    """
    try:
        # مسیر دایرکتوری پشتیبان‌ها
        backup_dirs = [
            'data/backups',
            'backups'
        ]
        
        # فرمت‌های فایل پشتیبان
        backup_patterns = [
            'backup_*',
            '*.bak',
            '*.backup',
            '*.sql',
            '*.tar.gz',
            '*.tar.bz2',
            '*.zip'
        ]
        
        # آمار پاکسازی
        stats = {
            'total_files': 0,
            'deleted_files': 0,
            'deleted_bytes': 0,
            'files': []
        }
        
        for backup_dir in backup_dirs:
            if not os.path.exists(backup_dir):
                if verbose:
                    logger.info(f"دایرکتوری پشتیبان {backup_dir} وجود ندارد")
                continue
            
            # لیست همه فایل‌های پشتیبان در این دایرکتوری
            backup_files = []
            for pattern in backup_patterns:
                backup_files.extend(glob.glob(os.path.join(backup_dir, pattern)))
                backup_files.extend(glob.glob(os.path.join(backup_dir, '*', pattern)))
            
            stats['total_files'] += len(backup_files)
            
            # گروه‌بندی فایل‌ها بر اساس نوع
            # تاریخ ایجاد و اندازه هر فایل را بررسی می‌کنیم
            file_groups = {}
            
            for backup_file in backup_files:
                # استخراج نوع فایل
                file_type = None
                
                if 'backup_' in os.path.basename(backup_file):
                    file_type = 'full_backup'
                elif backup_file.endswith('.sql'):
                    file_type = 'sql_backup'
                elif backup_file.endswith('.bak') or backup_file.endswith('.backup'):
                    file_type = 'db_backup'
                else:
                    # پسوند فایل
                    ext = os.path.splitext(backup_file)[1]
                    if ext:
                        file_type = f"{ext[1:]}_backup"
                    else:
                        file_type = 'other_backup'
                
                # اگر این نوع قبلاً در دیکشنری نباشد، آن را اضافه می‌کنیم
                if file_type not in file_groups:
                    file_groups[file_type] = []
                
                # اطلاعات فایل
                file_stats = os.stat(backup_file)
                file_modified_time = datetime.datetime.fromtimestamp(file_stats.st_mtime)
                file_size = file_stats.st_size
                
                file_groups[file_type].append({
                    'path': backup_file,
                    'size': file_size,
                    'modified': file_modified_time,
                    'modified_timestamp': file_stats.st_mtime
                })
            
            # مرتب‌سازی فایل‌ها در هر گروه بر اساس تاریخ تغییر (جدیدترین ابتدا)
            for file_type, files in file_groups.items():
                file_groups[file_type] = sorted(files, key=lambda x: x['modified_timestamp'], reverse=True)
                
                # حفظ فایل‌های جدیدتر و حذف قدیمی‌تر
                if len(files) > keep_count:
                    files_to_delete = files[keep_count:]
                    
                    for file_info in files_to_delete:
                        file_path = file_info['path']
                        file_size = file_info['size']
                        file_size_mb = round(file_size / (1024 * 1024), 2)
                        
                        if not dry_run:
                            os.remove(file_path)
                        
                        stats['deleted_files'] += 1
                        stats['deleted_bytes'] += file_size
                        
                        stats['files'].append({
                            'path': file_path,
                            'size_bytes': file_size,
                            'size_mb': file_size_mb,
                            'modified': file_info['modified'].isoformat(),
                            'type': file_type,
                            'action': 'delete'
                        })
                        
                        if verbose:
                            logger.info(f"فایل پشتیبان حذف شد: {file_path} ({file_size_mb} مگابایت)")
                
                # اضافه کردن فایل‌های حفظ شده به آمار
                for file_info in files[:keep_count]:
                    file_path = file_info['path']
                    file_size = file_info['size']
                    file_size_mb = round(file_size / (1024 * 1024), 2)
                    
                    stats['files'].append({
                        'path': file_path,
                        'size_bytes': file_size,
                        'size_mb': file_size_mb,
                        'modified': file_info['modified'].isoformat(),
                        'type': file_type,
                        'action': 'keep'
                    })
                    
                    if verbose:
                        logger.info(f"فایل پشتیبان نگهداری شد: {file_path} ({file_size_mb} مگابایت)")
        
        # خلاصه نتایج
        total_freed_mb = round(stats['deleted_bytes'] / (1024 * 1024), 2)
        logger.info(f"پاکسازی پشتیبان‌ها: {stats['deleted_files']} فایل حذف، {total_freed_mb} مگابایت آزاد شد")
        
        stats['status'] = 'success'
        stats['total_freed_mb'] = total_freed_mb
        
        return stats
    
    except Exception as e:
        logger.error(f"خطا در پاکسازی فایل‌های پشتیبان: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def cleanup_temp_files(
    dry_run: bool = False,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    پاکسازی فایل‌های موقت
    
    :param dry_run: بدون اعمال تغییرات
    :param verbose: نمایش اطلاعات بیشتر
    :return: آمار پاکسازی
    """
    try:
        # الگوهای فایل‌های موقت
        temp_patterns = [
            'cache/**/*',
            'data/cache/**/*',
            'data/temp/**/*',
            'tmp/**/*',
            '**/*.tmp',
            '**/*~',
            '**/__pycache__/**/*',
            '**/*.pyc',
            '**/*.pyo'
        ]
        
        # آمار پاکسازی
        stats = {
            'total_files': 0,
            'deleted_files': 0,
            'deleted_bytes': 0,
            'files': []
        }
        
        # جستجو و حذف فایل‌های موقت
        for pattern in temp_patterns:
            for path in glob.glob(pattern, recursive=True):
                if os.path.isfile(path):
                    file_stats = os.stat(path)
                    file_size = file_stats.st_size
                    file_size_mb = round(file_size / (1024 * 1024), 2)
                    
                    stats['total_files'] += 1
                    
                    if not dry_run:
                        os.remove(path)
                    
                    stats['deleted_files'] += 1
                    stats['deleted_bytes'] += file_size
                    
                    stats['files'].append({
                        'path': path,
                        'size_bytes': file_size,
                        'size_mb': file_size_mb,
                        'action': 'delete'
                    })
                    
                    if verbose:
                        logger.info(f"فایل موقت حذف شد: {path} ({file_size_mb} مگابایت)")
        
        # پاکسازی دایرکتوری‌های خالی
        empty_dirs = [
            'cache',
            'data/cache',
            'data/temp',
            'tmp'
        ]
        
        for dir_path in empty_dirs:
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                # حذف همه فایل‌ها و پوشه‌های خالی زیرمجموعه
                for root, dirs, files in os.walk(dir_path, topdown=False):
                    # حذف همه فایل‌ها در دایرکتوری
                    for file in files:
                        file_path = os.path.join(root, file)
                        
                        # بررسی اینکه آیا قبلاً حذف شده یا نه
                        if os.path.exists(file_path):
                            file_size = os.path.getsize(file_path)
                            
                            if not dry_run:
                                os.remove(file_path)
                            
                            stats['deleted_files'] += 1
                            stats['deleted_bytes'] += file_size
                            
                            if verbose:
                                logger.info(f"فایل موقت حذف شد: {file_path}")
                    
                    # حذف دایرکتوری‌های خالی
                    for dir_name in dirs:
                        dir_full_path = os.path.join(root, dir_name)
                        
                        if os.path.exists(dir_full_path) and not os.listdir(dir_full_path):
                            if not dry_run:
                                os.rmdir(dir_full_path)
                            
                            if verbose:
                                logger.info(f"دایرکتوری خالی حذف شد: {dir_full_path}")
        
        # خلاصه نتایج
        total_freed_mb = round(stats['deleted_bytes'] / (1024 * 1024), 2)
        logger.info(f"پاکسازی فایل‌های موقت: {stats['deleted_files']} فایل حذف، {total_freed_mb} مگابایت آزاد شد")
        
        stats['status'] = 'success'
        stats['total_freed_mb'] = total_freed_mb
        
        return stats
    
    except Exception as e:
        logger.error(f"خطا در پاکسازی فایل‌های موقت: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def save_report(stats: Dict[str, Any]) -> None:
    """
    ذخیره گزارش پاکسازی در فایل
    
    :param stats: آمار پاکسازی
    """
    try:
        # مسیر فایل گزارش
        timestamp = get_current_datetime().strftime('%Y%m%d_%H%M%S')
        report_dir = os.path.join('logs', 'cleanup')
        os.makedirs(report_dir, exist_ok=True)
        
        report_path = os.path.join(report_dir, f"cleanup_report_{timestamp}.json")
        
        # افزودن زمان به آمار
        stats['timestamp'] = timestamp
        stats['datetime'] = get_current_datetime().isoformat()
        
        # ذخیره گزارش به فرمت JSON
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"گزارش پاکسازی در {report_path} ذخیره شد")
    
    except Exception as e:
        logger.error(f"خطا در ذخیره گزارش پاکسازی: {str(e)}")


def confirm_action(message: str) -> bool:
    """
    دریافت تأیید کاربر برای انجام عملیات
    
    :param message: پیام برای نمایش
    :return: True اگر کاربر تأیید کند، False در غیر این صورت
    """
    response = input(f"{message} (بله/خیر): ").strip().lower()
    return response in ['y', 'yes', 'بله', 'بلی', 'آره']


def run_cleanup(args: argparse.Namespace) -> int:
    """
    اجرای فرآیند پاکسازی
    
    :param args: آرگومان‌های خط فرمان
    :return: کد خروجی (0 موفق، 1 ناموفق)
    """
    try:
        # تنظیم سطح لاگینگ
        if args.verbose:
            logger.setLevel(logging.DEBUG)
        
        logger.info("شروع فرآیند پاکسازی")
        
        # بررسی وضعیت dry-run
        if args.dry_run:
            logger.info("حالت dry-run: تغییرات نمایش داده می‌شوند اما اعمال نمی‌شوند")
        
        # آمار کلی
        total_stats = {
            'timestamp': get_current_datetime().isoformat(),
            'operations': {}
        }
        
        # دریافت مسیر پایگاه داده
        db_path = get_db_path(args.db_path)
        
        # تأیید پاکسازی
        if not args.force and not args.dry_run:
            message = (
                "این عملیات ممکن است داده‌های قدیمی را حذف کند. "
                "آیا مطمئن هستید که می‌خواهید ادامه دهید؟"
            )
            if not confirm_action(message):
                logger.info("عملیات پاکسازی توسط کاربر لغو شد")
                return 0
        
        # پاکسازی پایگاه داده
        if args.all or args.cleanup_db:
            db_stats = cleanup_database(db_path, args.age_days, args.dry_run, args.verbose)
            total_stats['operations']['database_cleanup'] = db_stats
        
        # بهینه‌سازی پایگاه داده
        if args.all or args.optimize_db:
            optimize_stats = optimize_database(db_path, args.dry_run, args.verbose)
            total_stats['operations']['database_optimization'] = optimize_stats
        
        # پاکسازی فایل‌های لاگ
        if args.all or args.cleanup_logs:
            logs_stats = cleanup_logs(args.age_days, args.max_log_size_mb, args.dry_run, args.verbose)
            total_stats['operations']['logs_cleanup'] = logs_stats
        
        # پاکسازی فایل‌های پشتیبان
        if args.all or args.cleanup_backups:
            backups_stats = cleanup_backups(args.keep_backups, args.dry_run, args.verbose)
            total_stats['operations']['backups_cleanup'] = backups_stats
        
        # پاکسازی فایل‌های موقت
        if args.all or args.cleanup_temp:
            temp_stats = cleanup_temp_files(args.dry_run, args.verbose)
            total_stats['operations']['temp_cleanup'] = temp_stats
        
        # محاسبه آمار کلی
        total_deleted_bytes = 0
        operation_count = 0
        
        for op_name, op_stats in total_stats['operations'].items():
            if op_stats.get('status') == 'success':
                operation_count += 1
                
                if 'deleted_bytes' in op_stats:
                    total_deleted_bytes += op_stats['deleted_bytes']
                elif 'size_diff_bytes' in op_stats:
                    total_deleted_bytes += op_stats['size_diff_bytes']
        
        total_stats['total_operations'] = operation_count
        total_stats['total_deleted_bytes'] = total_deleted_bytes
        total_stats['total_deleted_mb'] = round(total_deleted_bytes / (1024 * 1024), 2)
        
        # خلاصه نتایج
        logger.info("===== خلاصه عملیات پاکسازی =====")
        logger.info(f"تعداد عملیات: {operation_count}")
        logger.info(f"حجم آزاد شده: {total_stats['total_deleted_mb']} مگابایت")
        
        if not args.dry_run:
            logger.info("عملیات پاکسازی با موفقیت انجام شد")
            # ذخیره گزارش
            save_report(total_stats)
        else:
            logger.info("عملیات پاکسازی در حالت dry-run انجام شد، هیچ تغییری اعمال نشد")
        
        return 0
    
    except Exception as e:
        logger.error(f"خطا در اجرای فرآیند پاکسازی: {str(e)}")
        return 1


def main() -> None:
    """
    تابع اصلی
    """
    args = parse_arguments()
    exit_code = run_cleanup(args)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()