#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
اسکریپت بررسی وضعیت سیستم

این اسکریپت برای نظارت بر وضعیت سیستم ربات تلگرام و اجزای آن طراحی شده است.
قابلیت‌های اصلی:
- بررسی دسترس‌پذیری API‌های خارجی
- بررسی وضعیت پایگاه داده
- بررسی فضای دیسک
- بررسی وضعیت کش
- بررسی وضعیت سرویس‌های مرتبط
- گزارش مصرف منابع
- بررسی آخرین پشتیبان‌گیری
- ارسال هشدار در صورت وجود مشکل
"""


import glob
import os
import sys
import argparse
import logging
import time
import datetime
from src.utils.timezone_utils import get_current_datetime
import sqlite3
import json
import requests
import platform
import socket
import shutil
import psutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set

# افزودن مسیر ریشه پروژه به sys.path برای واردسازی ماژول‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.config import Config
from src.utils.timezone_utils import get_current_datetime
from src.utils.notification import Notifier

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
        description='بررسی وضعیت سیستم و اجزای آن'
    )
    
    parser.add_argument(
        '--config-path',
        default='.env',
        help='مسیر فایل تنظیمات (پیش‌فرض: .env)'
    )
    
    parser.add_argument(
        '--db-path',
        default=None,
        help='مسیر فایل پایگاه داده (اختیاری، در صورت عدم ارائه از config استفاده می‌شود)'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='بررسی همه موارد'
    )
    
    parser.add_argument(
        '--check-disk',
        action='store_true',
        help='بررسی فضای دیسک'
    )
    
    parser.add_argument(
        '--check-db',
        action='store_true',
        help='بررسی وضعیت پایگاه داده'
    )
    
    parser.add_argument(
        '--check-apis',
        action='store_true',
        help='بررسی دسترس‌پذیری API‌های خارجی'
    )
    
    parser.add_argument(
        '--check-services',
        action='store_true',
        help='بررسی وضعیت سرویس‌های مرتبط'
    )
    
    parser.add_argument(
        '--check-cache',
        action='store_true',
        help='بررسی وضعیت کش'
    )
    
    parser.add_argument(
        '--check-backups',
        action='store_true',
        help='بررسی آخرین پشتیبان‌گیری'
    )
    
    parser.add_argument(
        '--min-disk-percent',
        type=int,
        default=15,
        help='حداقل درصد فضای آزاد دیسک مورد نیاز (پیش‌فرض: 15)'
    )
    
    parser.add_argument(
        '--max-backup-age-hours',
        type=int,
        default=24,
        help='حداکثر سن مجاز آخرین پشتیبان‌گیری به ساعت (پیش‌فرض: 24)'
    )
    
    parser.add_argument(
        '--notify',
        action='store_true',
        help='ارسال هشدار در صورت وجود مشکل'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='خروجی به فرمت JSON'
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
    
    return db_path


def check_disk_space(min_free_percent: int, verbose: bool = False) -> Dict[str, Any]:
    """
    Ø¨Ø±Ø±Ø³Û ÙØ¶Ø§Û Ø¯ÛØ³Ú©
    
    :param min_free_percent: Ø­Ø¯Ø§ÙÙ Ø¯Ø±ØµØ¯ ÙØ¶Ø§Û Ø¢Ø²Ø§Ø¯ ÙÙØ±Ø¯ ÙÛØ§Ø²
    :param verbose: ÙÙØ§ÛØ´ Ø§Ø·ÙØ§Ø¹Ø§Øª Ø¨ÛØ´ØªØ±
    :return: ÙØªÛØ¬Ù Ø¨Ø±Ø±Ø³Û
    """
    try:
        disk_usage = shutil.disk_usage('/')
        
        total_gb = disk_usage.total / (1024 ** 3)
        used_gb = disk_usage.used / (1024 ** 3)
        free_gb = disk_usage.free / (1024 ** 3)
        
        percent_used = (disk_usage.used / disk_usage.total) * 100
        percent_free = 100 - percent_used
        
        status = "OK" if percent_free >= min_free_percent else "WARNING"
        
        if verbose:
            logger.info(f"بررسی فضای دیسک: {percent_free:.1f}% آزاد ({free_gb:.1f}GB از {total_gb:.1f}GB) - وضعیت: {status}")
        
        return {
            'status': status,
            'total_gb': round(total_gb, 2),
            'used_gb': round(used_gb, 2),
            'free_gb': round(free_gb, 2),
            'percent_used': round(percent_used, 2),
            'percent_free': round(percent_free, 2),
            'min_free_percent': min_free_percent
        }
    
    except Exception as e:
        logger.error(f"خطا در بررسی فضای دیسک: {str(e)}")
        return {
            'status': 'ERROR',
            'error': str(e)
        }


def check_database(db_path: str, verbose: bool = False) -> Dict[str, Any]:
    """
    بررسی وضعیت پایگاه داده
    
    :param db_path: مسیر فایل پایگاه داده
    :param verbose: نمایش اطلاعات بیشتر
    :return: نتیجه بررسی
    """
    # بررسی وجود فایل پایگاه داده
    if not os.path.exists(db_path):
        error_msg = f"فایل پایگاه داده {db_path} وجود ندارد"
        logger.error(error_msg)
        return {
            'status': 'ERROR',
            'error': error_msg
        }
    
    try:
        # آمار اولیه فایل
        db_size = os.path.getsize(db_path)
        db_size_mb = db_size / (1024 * 1024)
        
        # اتصال به پایگاه داده
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # بررسی سلامت پایگاه داده
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]
        is_healthy = integrity_result == 'ok'
        
        # بررسی تعداد رکوردها در جداول اصلی
        stats = {'tables': {}}
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            # نادیده گرفتن جداول سیستمی SQLite
            if table.startswith('sqlite_'):
                continue
            
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            
            stats['tables'][table] = count
        
        # بررسی آخرین تراکنش‌ها
        last_transactions = {}
        
        if 'transactions' in tables:
            cursor.execute(
                "SELECT id, user_id, amount, currency, timestamp, status "
                "FROM transactions "
                "ORDER BY timestamp DESC LIMIT 5"
            )
            
            last_transactions['transactions'] = [dict(row) for row in cursor.fetchall()]
        
        if 'user_activities' in tables:
            cursor.execute(
                "SELECT id, user_id, activity_type, timestamp "
                "FROM user_activities "
                "ORDER BY timestamp DESC LIMIT 5"
            )
            
            last_transactions['user_activities'] = [dict(row) for row in cursor.fetchall()]
        
        # بستن اتصال
        conn.close()
        
        status = "OK" if is_healthy else "WARNING"
        
        if verbose:
            logger.info(f"بررسی پایگاه داده: {status} - سایز: {db_size_mb:.2f}MB - سلامت: {integrity_result}")
        
        return {
            'status': status,
            'size_bytes': db_size,
            'size_mb': round(db_size_mb, 2),
            'integrity': integrity_result,
            'is_healthy': is_healthy,
            'record_counts': stats['tables'],
            'last_records': last_transactions
        }
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پایگاه داده: {str(e)}")
        return {
            'status': 'ERROR',
            'error': str(e)
        }
    
    except Exception as e:
        logger.error(f"خطا در بررسی پایگاه داده: {str(e)}")
        return {
            'status': 'ERROR',
            'error': str(e)
        }


def check_apis(verbose: bool = False) -> Dict[str, Any]:
    """
    بررسی دسترس‌پذیری API‌های خارجی
    
    :param verbose: نمایش اطلاعات بیشتر
    :return: نتیجه بررسی
    """
    try:
        # دریافت لیست API‌های خارجی از پیکربندی
        config = Config()
        timeout = config.get('API_TIMEOUT', 5)  # زمان انتظار به ثانیه
        
        # لیست API‌های مورد نیاز برای بررسی
        apis_to_check = [
            {
                'name': 'Telegram Bot API',
                'url': 'https://api.telegram.org/bot{token}/getMe',
                'token_key': 'TELEGRAM_BOT_TOKEN',
                'required': True
            },
            {
                'name': 'Binance API',
                'url': 'https://api.binance.com/api/v3/ping',
                'required': False
            },
            {
                'name': 'KuCoin API',
                'url': 'https://api.kucoin.com/api/v1/timestamp',
                'required': False
            },
            {
                'name': 'Currency Converter API',
                'url': 'https://api.exchangerate-api.com/v4/latest/USD',
                'token_key': 'EXCHANGE_RATE_API_KEY',
                'required': False
            }
        ]
        
        # نتایج بررسی
        results = {'apis': {}}
        
        # بررسی هر API
        for api in apis_to_check:
            api_name = api['name']
            api_url = api['url']
            
            # جایگزینی توکن در URL (اگر نیاز باشد)
            if '{token}' in api_url and 'token_key' in api:
                token = config.get(api['token_key'], '')
                # پنهان کردن قسمت‌های حساس توکن
                masked_token = 'MASKED'
                if token:
                    masked_token = token[:4] + '...' + token[-4:] if len(token) > 8 else '***'
                api_url = api_url.replace('{token}', token)
            
            try:
                # تلاش برای ارسال درخواست
                start_time = time.time()
                response = requests.get(api_url, timeout=timeout)
                response_time = time.time() - start_time
                
                # بررسی وضعیت پاسخ
                is_success = response.status_code >= 200 and response.status_code < 300
                status = "OK" if is_success else "ERROR"
                
                if verbose:
                    logger.info(f"بررسی API {api_name}: {status} - زمان پاسخ: {response_time:.2f}s - کد وضعیت: {response.status_code}")
                
                # ثبت نتیجه
                results['apis'][api_name] = {
                    'status': status,
                    'response_code': response.status_code,
                    'response_time': round(response_time, 3),
                    'required': api.get('required', False)
                }
            
            except requests.exceptions.Timeout:
                error_msg = "زمان انتظار به پایان رسید"
                logger.error(f"خطا در بررسی API {api_name}: {error_msg}")
                
                results['apis'][api_name] = {
                    'status': 'TIMEOUT',
                    'error': error_msg,
                    'required': api.get('required', False)
                }
            
            except requests.exceptions.RequestException as e:
                logger.error(f"خطا در بررسی API {api_name}: {str(e)}")
                
                results['apis'][api_name] = {
                    'status': 'ERROR',
                    'error': str(e),
                    'required': api.get('required', False)
                }
        
        # بررسی وضعیت کلی API‌ها
        required_apis = [name for name, details in results['apis'].items() if details.get('required', False)]
        required_apis_with_error = [
            name for name in required_apis 
            if results['apis'][name]['status'] != 'OK'
        ]
        
        if required_apis_with_error:
            overall_status = "ERROR"
        else:
            # بررسی تعداد API‌های دارای مشکل
            all_apis_with_error = [
                name for name, details in results['apis'].items() 
                if details['status'] != 'OK'
            ]
            
            if not all_apis_with_error:
                overall_status = "OK"
            elif len(all_apis_with_error) <= len(results['apis']) // 3:
                overall_status = "WARNING"
            else:
                overall_status = "ERROR"
        
        results['status'] = overall_status
        results['total_apis'] = len(results['apis'])
        results['error_count'] = len([name for name, details in results['apis'].items() if details['status'] != 'OK'])
        
        return results
    
    except Exception as e:
        logger.error(f"خطا در بررسی API‌ها: {str(e)}")
        return {
            'status': 'ERROR',
            'error': str(e)
        }


def check_services(verbose: bool = False) -> Dict[str, Any]:
    """
    بررسی وضعیت سرویس‌های مرتبط
    
    :param verbose: نمایش اطلاعات بیشتر
    :return: نتیجه بررسی
    """
    try:
        # دریافت لیست سرویس‌های مرتبط از پیکربندی
        config = Config()
        
        # لیست سرویس‌های مورد نیاز برای بررسی
        services_to_check = [
            {
                'name': 'Redis',
                'type': 'port',
                'host': config.get('REDIS_HOST', 'localhost'),
                'port': int(config.get('REDIS_PORT', 6379)),
                'required': False
            },
            {
                'name': 'PostgreSQL',
                'type': 'port',
                'host': config.get('POSTGRES_HOST', 'localhost'),
                'port': int(config.get('POSTGRES_PORT', 5432)),
                'required': False
            },
            {
                'name': 'Nginx',
                'type': 'process',
                'process_name': 'nginx',
                'required': False
            },
            {
                'name': 'TelegramBot',
                'type': 'process',
                'process_name': 'python',
                'args_contains': 'telegram_bot',
                'required': True
            }
        ]
        
        # نتایج بررسی
        results = {'services': {}}
        
        # بررسی هر سرویس
        for service in services_to_check:
            service_name = service['name']
            service_type = service['type']
            
            if service_type == 'port':
                # بررسی پورت
                host = service['host']
                port = service['port']
                
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex((host, port))
                    sock.close()
                    
                    is_running = result == 0
                    status = "OK" if is_running else "ERROR"
                    
                    if verbose:
                        logger.info(f"بررسی سرویس {service_name}: {status} - اتصال به {host}:{port}")
                    
                    results['services'][service_name] = {
                        'status': status,
                        'type': 'port',
                        'host': host,
                        'port': port,
                        'is_running': is_running,
                        'required': service.get('required', False)
                    }
                
                except Exception as e:
                    logger.error(f"خطا در بررسی سرویس {service_name}: {str(e)}")
                    
                    results['services'][service_name] = {
                        'status': 'ERROR',
                        'type': 'port',
                        'host': host,
                        'port': port,
                        'error': str(e),
                        'required': service.get('required', False)
                    }
            
            elif service_type == 'process':
                # بررسی فرآیند
                process_name = service['process_name']
                args_contains = service.get('args_contains', None)
                
                try:
                    processes = []
                    
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            proc_info = proc.info
                            if process_name.lower() in proc_info['name'].lower():
                                if args_contains is None:
                                    processes.append(proc_info)
                                else:
                                    # بررسی آرگومان‌ها
                                    cmdline = ' '.join(proc_info.get('cmdline', []))
                                    if args_contains.lower() in cmdline.lower():
                                        processes.append(proc_info)
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            pass
                    
                    is_running = len(processes) > 0
                    status = "OK" if is_running else "ERROR"
                    
                    if verbose:
                        msg = f"در حال اجرا ({len(processes)} نمونه)" if is_running else "متوقف شده"
                        logger.info(f"بررسی سرویس {service_name}: {status} - {msg}")
                    
                    results['services'][service_name] = {
                        'status': status,
                        'type': 'process',
                        'process_name': process_name,
                        'args_contains': args_contains,
                        'is_running': is_running,
                        'instance_count': len(processes),
                        'instances': [p['pid'] for p in processes[:5]],  # فقط 5 نمونه اول
                        'required': service.get('required', False)
                    }
                
                except Exception as e:
                    logger.error(f"خطا در بررسی سرویس {service_name}: {str(e)}")
                    
                    results['services'][service_name] = {
                        'status': 'ERROR',
                        'type': 'process',
                        'process_name': process_name,
                        'error': str(e),
                        'required': service.get('required', False)
                    }
        
        # بررسی وضعیت کلی سرویس‌ها
        required_services = [name for name, details in results['services'].items() if details.get('required', False)]
        required_services_with_error = [
            name for name in required_services 
            if results['services'][name]['status'] != 'OK'
        ]
        
        if required_services_with_error:
            overall_status = "ERROR"
        else:
            # بررسی تعداد سرویس‌های دارای مشکل
            all_services_with_error = [
                name for name, details in results['services'].items() 
                if details['status'] != 'OK'
            ]
            
            if not all_services_with_error:
                overall_status = "OK"
            elif len(all_services_with_error) <= len(results['services']) // 3:
                overall_status = "WARNING"
            else:
                overall_status = "ERROR"
        
        results['status'] = overall_status
        results['total_services'] = len(results['services'])
        results['error_count'] = len([name for name, details in results['services'].items() if details['status'] != 'OK'])
        
        return results
    
    except Exception as e:
        logger.error(f"خطا در بررسی سرویس‌ها: {str(e)}")
        return {
            'status': 'ERROR',
            'error': str(e)
        }


def check_cache(verbose: bool = False) -> Dict[str, Any]:
    """
    بررسی وضعیت کش
    
    :param verbose: نمایش اطلاعات بیشتر
    :return: نتیجه بررسی
    """
    try:
        # مسیر دایرکتوری کش
        cache_dirs = [
            'cache',
            'data/cache'
        ]
        
        # نتایج بررسی
        results = {'caches': {}}
        
        total_cache_files = 0
        total_cache_size = 0
        for cache_dir in cache_dirs:
            if not os.path.exists(cache_dir):
                if verbose:
                    logger.info(f"دایرکتوری کش {cache_dir} وجود ندارد")
                continue
            
            # شمارش تعداد و سایز فایل‌های کش
            file_count = 0
            total_size = 0
            
            for root, dirs, files in os.walk(cache_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    total_size += file_size
                    file_count += 1
            
            total_cache_files += file_count
            total_cache_size += total_size
            
            # بررسی کش‌های منقضی
            expired_files = 0
            cutoff_time = time.time() - (24 * 60 * 60)  # 24 ساعت قبل
            
            for root, dirs, files in os.walk(cache_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_mtime = os.path.getmtime(file_path)
                    if file_mtime < cutoff_time:
                        expired_files += 1
            
            if verbose:
                logger.info(f"بررسی کش {cache_dir}: {file_count} فایل، {total_size / (1024 * 1024):.2f}MB، {expired_files} فایل منقضی")
            
            results['caches'][cache_dir] = {
                'file_count': file_count,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'expired_files': expired_files
            }
        
        results['total_cache_files'] = total_cache_files
        results['total_cache_size_bytes'] = total_cache_size
        results['total_cache_size_m'] = round(total_cache_size / (1024 * 1024), 2)
        
        # Ø¨Ø±Ø±Ø³Û ÙØ¶Ø¹ÛØª Ú©ÙÛ Ú©Ø´
        # Ø§Ú¯Ø± Ø­Ø¬Ù Ú©Ø´ Ø¨ÛØ´ Ø§Ø² 1GB Ø¨Ø§Ø´Ø¯Ø ÙØ´Ø¯Ø§Ø±
        if total_cache_size > 1024 * 1024 * 1024:
            results['status'] = "WARNING"
        else:
            results['status'] = "OK"
        
        return results
    
    except Exception as e:
        logger.error(f"خطا در بررسی کش: {str(e)}")
        return {
            'status': 'ERROR',
            'error': str(e)
        }


def check_backups(max_age_hours: int, verbose: bool = False) -> Dict[str, Any]:
    """
    بررسی آخرین پشتیبان‌گیری
    
    :param max_age_hours: حداکثر سن مجاز پشتیبان به ساعت
    :param verbose: نمایش اطلاعات بیشتر
    :return: نتیجه بررسی
    """
    try:
        # مسیر دایرکتوری پشتیبان‌ها
        backup_dirs = [
            'data/backups/daily',
            'data/backups/weekly',
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
        
        # نتایج بررسی
        results = {'backups': []}
        
        # محاسبه زمان مرجع
        cutoff_time = time.time() - (max_age_hours * 60 * 60)
        
        # یافتن جدیدترین فایل پشتیبان
        newest_backup = None
        newest_backup_time = 0
        
        for backup_dir in backup_dirs:
            if not os.path.exists(backup_dir):
                if verbose:
                    logger.info(f"دایرکتوری پشتیبان {backup_dir} وجود ندارد")
                continue
            
            # جستجوی همه فایل‌های پشتیبان
            for pattern in backup_patterns:
                backup_files = glob.glob(os.path.join(backup_dir, pattern))
                backup_files.extend(glob.glob(os.path.join(backup_dir, '*', pattern)))
                
                for backup_file in backup_files:
                    file_mtime = os.path.getmtime(backup_file)
                    
                    # اضافه کردن به لیست پشتیبان‌ها
                    results['backups'].append({
                        'path': backup_file,
                        'timestamp': file_mtime,
                        'datetime': datetime.datetime.fromtimestamp(file_mtime).isoformat(),
                        'size_bytes': os.path.getsize(backup_file),
                        'size_mb': round(os.path.getsize(backup_file) / (1024 * 1024), 2),
                        'is_recent': file_mtime > cutoff_time
                    })
                    
                    # بررسی جدیدترین پشتیبان
                    if file_mtime > newest_backup_time:
                        newest_backup = backup_file
                        newest_backup_time = file_mtime
        
        # مرتب‌سازی پشتیبان‌ها بر اساس زمان (جدیدترین اول)
        results['backups'] = sorted(results['backups'], key=lambda x: x['timestamp'], reverse=True)
        
        # نتیجه نهایی
        if newest_backup:
            newest_backup_age = time.time() - newest_backup_time
            newest_backup_age_hours = newest_backup_age / (60 * 60)
            
            results['newest_backup'] = {
                'path': newest_backup,
                'timestamp': newest_backup_time,
                'datetime': datetime.datetime.fromtimestamp(newest_backup_time).isoformat(),
                'age_seconds': round(newest_backup_age, 2),
                'age_hours': round(newest_backup_age_hours, 2),
                'is_recent': newest_backup_time > cutoff_time
            }
            
            if newest_backup_time > cutoff_time:
                results['status'] = "OK"
                if verbose:
                    logger.info(f"آخرین پشتیبان‌گیری: {newest_backup} ({results['newest_backup']['age_hours']:.1f} ساعت قبل) - وضعیت: OK")
            else:
                results['status'] = "WARNING"
                if verbose:
                    logger.info(f"آخرین پشتیبان‌گیری: {newest_backup} ({results['newest_backup']['age_hours']:.1f} ساعت قبل) - وضعیت: WARNING")
        else:
            results['status'] = "ERROR"
            results['error'] = "هیچ فایل پشتیبانی یافت نشد"
            
            if verbose:
                logger.warning("هیچ فایل پشتیبانی یافت نشد")
        
        return results
    
    except Exception as e:
        logger.error(f"خطا در بررسی پشتیبان‌ها: {str(e)}")
        return {
            'status': 'ERROR',
            'error': str(e)
        }


def get_system_info() -> Dict[str, Any]:
    """
    دریافت اطلاعات سیستم
    
    :return: اطلاعات سیستم
    """
    try:
        # اطلاعات CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        # اطلاعات حافظه
        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024 ** 3)
        memory_used_gb = memory.used / (1024 ** 3)
        memory_percent = memory.percent
        
        # اطلاعات سیستم عامل
        system_info = {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'node': platform.node()
        }
        
        # زمان بالا بودن سیستم
        boot_time = psutil.boot_time()
        uptime = time.time() - boot_time
        uptime_days = uptime / (60 * 60 * 24)
        
        # برگرداندن اطلاعات
        return {
            'cpu': {
                'percent': cpu_percent,
                'count': cpu_count,
                'frequency_mhz': cpu_freq.current if cpu_freq else None
            },
            'memory': {
                'total_gb': round(memory_total_gb, 2),
                'used_gb': round(memory_used_gb, 2),
                'percent': memory_percent
            },
            'system': system_info,
            'boot_time': boot_time,
            'boot_datetime': datetime.datetime.fromtimestamp(boot_time).isoformat(),
            'uptime_seconds': round(uptime, 2),
            'uptime_days': round(uptime_days, 2)
        }
    
    except Exception as e:
        logger.error(f"خطا در دریافت اطلاعات سیستم: {str(e)}")
        return {
            'status': 'ERROR',
            'error': str(e)
        }


def run_status_check(args: argparse.Namespace) -> Dict[str, Any]:
    """
    اجرای بررسی وضعیت
    
    :param args: آرگومان‌های خط فرمان
    :return: نتایج بررسی
    """
    try:
        # تنظیم سطح لاگینگ
        if args.verbose:
            logger.setLevel(logging.DEBUG)
        
        logger.info("شروع بررسی وضعیت سیستم")
        
        # دریافت مسیر پایگاه داده
        db_path = get_db_path(args.db_path)
        
        # نتایج بررسی
        results = {
            'timestamp': time.time(),
            'datetime': datetime.get_current_datetime().isoformat(),
            'checks': {}
        }
        
        # دریافت اطلاعات سیستم
        system_info = get_system_info()
        results['system_info'] = system_info
        
        # بررسی فضای دیسک
        if args.all or args.check_disk:
            disk_results = check_disk_space(args.min_disk_percent, args.verbose)
            results['checks']['disk'] = disk_results
        
        # بررسی پایگاه داده
        if args.all or args.check_db:
            db_results = check_database(db_path, args.verbose)
            results['checks']['database'] = db_results
        
        # بررسی API‌های خارجی
        if args.all or args.check_apis:
            api_results = check_apis(args.verbose)
            results['checks']['apis'] = api_results
        
        # بررسی سرویس‌های مرتبط
        if args.all or args.check_services:
            service_results = check_services(args.verbose)
            results['checks']['services'] = service_results
        
        # بررسی کش
        if args.all or args.check_cache:
            cache_results = check_cache(args.verbose)
            results['checks']['cache'] = cache_results
        
        # بررسی پشتیبان‌گیری
        if args.all or args.check_backups:
            backup_results = check_backups(args.max_backup_age_hours, args.verbose)
            results['checks']['backups'] = backup_results
        
        # محاسبه وضعیت کلی
        error_checks = [check for check, result in results['checks'].items() if result.get('status') == 'ERROR']
        warning_checks = [check for check, result in results['checks'].items() if result.get('status') == 'WARNING']
        
        if error_checks:
            overall_status = "ERROR"
        elif warning_checks:
            overall_status = "WARNING"
        else:
            overall_status = "OK"
        
        results['status'] = overall_status
        results['error_checks'] = error_checks
        results['warning_checks'] = warning_checks
        
        # نمایش خلاصه نتایج
        logger.info("===== خلاصه نتایج بررسی وضعیت =====")
        logger.info(f"وضعیت کلی: {overall_status}")
        
        if error_checks:
            logger.error(f"خطاها: {', '.join(error_checks)}")
        
        if warning_checks:
            logger.warning(f"هشدارها: {', '.join(warning_checks)}")
        
        # ارسال هشدار در صورت وجود مشکل
        if args.notify and (error_checks or warning_checks):
            try:
                notifier = Notifier()
                
                if error_checks:
                    error_message = f"خطا در سیستم: {', '.join(error_checks)}"
                    notifier.send_alert("ERROR", error_message, results)
                
                if warning_checks and not error_checks:  # اگر خطا وجود داشته باشد، فقط هشدار خطا ارسال شود
                    warning_message = f"هشدار سیستم: {', '.join(warning_checks)}"
                    notifier.send_alert("WARNING", warning_message, results)
                
                logger.info("هشدار ارسال شد")
            
            except Exception as e:
                logger.error(f"خطا در ارسال هشدار: {str(e)}")
        
        # خروجی JSON
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        
        return results
    
    except Exception as e:
        logger.error(f"خطا در بررسی وضعیت: {str(e)}")
        return {
            'status': 'ERROR',
            'error': str(e)
        }


def save_report(results: Dict[str, Any]) -> None:
    """
    ذخیره گزارش وضعیت در فایل
    
    :param results: نتایج بررسی
    """
    try:
        # مسیر فایل گزارش
        timestamp = datetime.get_current_datetime().strftime('%Y%m%d_%H%M%S')
        report_dir = os.path.join('logs', 'status')
        os.makedirs(report_dir, exist_ok=True)
        
        report_path = os.path.join(report_dir, f"status_report_{timestamp}.json")
        
        # ذخیره گزارش به فرمت JSON
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"گزارش وضعیت در {report_path} ذخیره شد")
    
    except Exception as e:
        logger.error(f"خطا در ذخیره گزارش وضعیت: {str(e)}")


def main() -> None:
    """
    تابع اصلی
    """
    args = parse_arguments()
    results = run_status_check(args)
    
    # ذخیره گزارش
    save_report(results)
    
    # کد خروجی بر اساس وضعیت
    exit_code = 0
    if results.get('status') == "ERROR":
        exit_code = 2
    elif results.get('status') == "WARNING":
        exit_code = 1
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()