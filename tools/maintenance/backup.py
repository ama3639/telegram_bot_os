#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
اسکریپت پشتیبان‌گیری از داده‌های ربات تلگرام

این اسکریپت از پایگاه داده و سایر فایل‌های مهم پروژه نسخه پشتیبان تهیه می‌کند.
قابلیت‌های اصلی:
- پشتیبان‌گیری از پایگاه داده SQLite
- پشتیبان‌گیری از فایل‌های پیکربندی
- پشتیبان‌گیری از فایل‌های داده در پوشه data
- فشرده‌سازی فایل‌های پشتیبان
- آپلود خودکار فایل‌های پشتیبان به فضای ذخیره‌سازی ابری (اختیاری)
- ارسال ایمیل گزارش پشتیبان‌گیری (اختیاری)
"""


import fnmatch
import os
import sys
import argparse
import logging
import time
import datetime
from utils.timezone_utils import get_current_datetime
import shutil
import sqlite3
import configparser
import json
import zipfile
import tarfile
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set

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
        description='پشتیبان‌گیری از داده‌های ربات تلگرام'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        default='data/backups',
        help='مسیر ذخیره فایل‌های پشتیبان (پیش‌فرض: data/backups)'
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
        '--backup-type',
        choices=['full', 'db-only', 'config-only', 'data-only'],
        default='full',
        help='نوع پشتیبان‌گیری (پیش‌فرض: full)'
    )
    
    parser.add_argument(
        '--format',
        choices=['zip', 'tar', 'tar.gz', 'tar.bz2', 'none'],
        default='tar.gz',
        help='فرمت فشرده‌سازی فایل پشتیبان (پیش‌فرض: tar.gz)'
    )
    
    parser.add_argument(
        '--upload',
        action='store_true',
        help='آپلود فایل پشتیبان به فضای ذخیره‌سازی ابری'
    )
    
    parser.add_argument(
        '--send-email',
        action='store_true',
        help='ارسال ایمیل گزارش پشتیبان‌گیری'
    )
    
    parser.add_argument(
        '--email-recipients',
        default=None,
        help='آدرس‌های ایمیل دریافت‌کنندگان گزارش (با کاما جدا شوند)'
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


def create_backup_directory(output_dir: str) -> str:
    """
    Ø§ÛØ¬Ø§Ø¯ Ø³Ø§Ø®ØªØ§Ø± Ø¯Ø§ÛØ±Ú©ØªÙØ±Û Ø¨Ø±Ø§Û ÙØ§ÛÙâÙØ§Û Ù¾Ø´ØªÛØ¨Ø§Ù
    
    :param output_dir: ÙØ³ÛØ± Ù¾Ø§ÛÙ Ø¨Ø±Ø§Û ÙØ§ÛÙâÙØ§Û Ù¾Ø´ØªÛØ¨Ø§Ù
    :return: ÙØ³ÛØ± Ú©Ø§ÙÙ Ø¯Ø§ÛØ±Ú©ØªÙØ±Û Ù¾Ø´ØªÛØ¨Ø§Ù
    """
    timestamp = datetime.get_current_datetime().strftime('%Y%m%d_%H%M%S')
    backup_dir = os.path.join(output_dir, f"backup_{timestamp}")
    
    # ایجاد دایرکتوری‌های لازم
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(os.path.join(backup_dir, 'db'), exist_ok=True)
    os.makedirs(os.path.join(backup_dir, 'config'), exist_ok=True)
    os.makedirs(os.path.join(backup_dir, 'data'), exist_ok=True)
    
    logger.info(f"دایرکتوری پشتیبان در {backup_dir} ایجاد شد")
    return backup_dir


def backup_database(db_path: str, backup_dir: str) -> Tuple[bool, str]:
    """
    پشتیبان‌گیری از پایگاه داده
    
    :param db_path: مسیر فایل پایگاه داده
    :param backup_dir: مسیر دایرکتوری پشتیبان
    :return: نتیجه عملیات و مسیر فایل پشتیبان
    """
    try:
        if not os.path.exists(db_path):
            logger.warning(f"فایل پایگاه داده {db_path} وجود ندارد")
            return False, ""
        
        # مسیر فایل پشتیبان
        db_backup_path = os.path.join(backup_dir, 'd', os.path.basename(db_path))
        
        # Ø±ÙØ´ 1: Ú©Ù¾Û ÙØ³ØªÙÛÙ ÙØ§ÛÙ
        shutil.copy2(db_path, db_backup_path)
        
        # Ø±ÙØ´ 2: Ø§Ø³ØªÙØ§Ø¯Ù Ø§Ø² Ø¯Ø³ØªÙØ± backup Ø¯Ø§Ø®ÙÛ SQLite
        # Ø§ÛÙ Ø±ÙØ´ Ø§ÙÙâØªØ± Ø§Ø³Øª Ø²ÛØ±Ø§ Ø§Ø² Ù¾Ø§ÛÚ¯Ø§Ù Ø¯Ø§Ø¯Ù Ø¯Ø± Ø­Ø§Ù Ø§Ø³ØªÙØ§Ø¯Ù ÙÙ ÙÛâØªÙØ§ÙØ¯ Ù¾Ø´ØªÛØ¨Ø§Ù Ø¨Ú¯ÛØ±Ø¯
        try:
            conn = sqlite3.connect(db_path)
            backup_conn = sqlite3.connect(f"{db_backup_path}.bak")
            
            with backup_conn:
                conn.backup(backup_conn)
                
            conn.close()
            backup_conn.close()
            logger.info(f"ÙØ³Ø®Ù Ù¾Ø´ØªÛØ¨Ø§Ù SQLite Ø¯Ø± {db_backup_path}.bak Ø§ÛØ¬Ø§Ø¯ Ø´Ø¯")
        except Exception as e:
            logger.warning(f"Ø®Ø·Ø§ Ø¯Ø± Ù¾Ø´ØªÛØ¨Ø§ÙâÚ¯ÛØ±Û Ø¯Ø§Ø®ÙÛ SQLite: {str(e)}")
        
        logger.info(f"Ù¾Ø´ØªÛØ¨Ø§ÙâÚ¯ÛØ±Û Ø§Ø² Ù¾Ø§ÛÚ¯Ø§Ù Ø¯Ø§Ø¯Ù Ø¯Ø± {db_backup_path} Ø§ÙØ¬Ø§Ù Ø´Ø¯")
        return True, db_backup_path
    
    except Exception as e:
        logger.error(f"Ø®Ø·Ø§ Ø¯Ø± Ù¾Ø´ØªÛØ¨Ø§ÙâÚ¯ÛØ±Û Ø§Ø² Ù¾Ø§ÛÚ¯Ø§Ù Ø¯Ø§Ø¯Ù: {str(e)}")
        return False, ""


def backup_config_files(config_path: str, backup_dir: str) -> Tuple[bool, List[str]]:
    """
    Ù¾Ø´ØªÛØ¨Ø§ÙâÚ¯ÛØ±Û Ø§Ø² ÙØ§ÛÙâÙØ§Û Ù¾ÛÚ©Ø±Ø¨ÙØ¯Û
    
    :param config_path: ÙØ³ÛØ± ÙØ§ÛÙ Ù¾ÛÚ©Ø±Ø¨ÙØ¯Û Ø§ØµÙÛ
    :param backup_dir: ÙØ³ÛØ± Ø¯Ø§ÛØ±Ú©ØªÙØ±Û Ù¾Ø´ØªÛØ¨Ø§Ù
    :return: ÙØªÛØ¬Ù Ø¹ÙÙÛØ§Øª Ù ÙÛØ³Øª ÙØ³ÛØ± ÙØ§ÛÙâÙØ§Û Ù¾Ø´ØªÛØ¨Ø§Ù
    """
    try:
        backup_files = []
        
        # Ù¾Ø´ØªÛØ¨Ø§ÙâÚ¯ÛØ±Û Ø§Ø² ÙØ§ÛÙ Ù¾ÛÚ©Ø±Ø¨ÙØ¯Û Ø§ØµÙÛ (.env)
        if os.path.exists(config_path):
            config_backup_path = os.path.join(backup_dir, 'config', os.path.basename(config_path))
            shutil.copy2(config_path, config_backup_path)
            backup_files.append(config_backup_path)
            logger.info(f"پشتیبان‌گیری از فایل پیکربندی {config_path} انجام شد")
        else:
            logger.warning(f"فایل پیکربندی {config_path} وجود ندارد")
        
        # پشتیبان‌گیری از سایر فایل‌های پیکربندی
        additional_configs = [
            '.env.example',
            'requirements.txt',
            'docker-compose.yml',
            'Dockerfile',
            'config.json'
        ]
        
        for config_file in additional_configs:
            if os.path.exists(config_file):
                config_backup_path = os.path.join(backup_dir, 'config', os.path.basename(config_file))
                shutil.copy2(config_file, config_backup_path)
                backup_files.append(config_backup_path)
                logger.info(f"پشتیبان‌گیری از فایل پیکربندی {config_file} انجام شد")
        
        return len(backup_files) > 0, backup_files
    
    except Exception as e:
        logger.error(f"خطا در پشتیبان‌گیری از فایل‌های پیکربندی: {str(e)}")
        return False, []


def backup_data_files(backup_dir: str) -> Tuple[bool, List[str]]:
    """
    پشتیبان‌گیری از فایل‌های داده
    
    :param backup_dir: مسیر دایرکتوری پشتیبان
    :return: نتیجه عملیات و لیست مسیر فایل‌های پشتیبان
    """
    try:
        backup_files = []
        data_dir = 'data'
        
        if not os.path.exists(data_dir):
            logger.warning(f"دایرکتوری داده {data_dir} وجود ندارد")
            return False, []
        
        # پوشه‌هایی که باید پشتیبان‌گیری شوند
        data_folders = [
            'csv',
            'reports',
            'logs'
        ]
        
        # فایل‌ها و پوشه‌هایی که باید نادیده گرفته شوند
        exclude_patterns = [
            'backups',
            '*.bak',
            '*.tmp',
            '*.temp',
            'logs/*.log.*',
            '__pycache__'
        ]
        
        for folder in data_folders:
            folder_path = os.path.join(data_dir, folder)
            
            if not os.path.exists(folder_path):
                logger.warning(f"پوشه داده {folder_path} وجود ندارد")
                continue
            
            # کپی پوشه به دایرکتوری پشتیبان
            dest_folder = os.path.join(backup_dir, 'data', folder)
            
            # ایجاد دایرکتوری مقصد
            os.makedirs(dest_folder, exist_ok=True)
            
            # کپی فایل‌ها با استفاده از shutil.copytree
            for root, dirs, files in os.walk(folder_path):
                # بررسی الگوهای نادیده گرفتن برای دایرکتوری‌ها
                dirs[:] = [d for d in dirs if not any(
                    fnmatch.fnmatch(os.path.join(root, d), pattern) for pattern in exclude_patterns
                )]
                
                # ایجاد ساختار پوشه در مقصد
                rel_path = os.path.relpath(root, folder_path)
                dest_path = os.path.join(dest_folder, rel_path)
                os.makedirs(dest_path, exist_ok=True)
                
                # کپی فایل‌ها
                for file in files:
                    # بررسی الگوهای نادیده گرفتن برای فایل‌ها
                    file_path = os.path.join(root, file)
                    if any(fnmatch.fnmatch(file_path, pattern) for pattern in exclude_patterns):
                        continue
                    
                    # کپی فایل به مقصد
                    shutil.copy2(file_path, os.path.join(dest_path, file))
                    backup_files.append(os.path.join(dest_path, file))
            
            logger.info(f"پشتیبان‌گیری از پوشه {folder_path} انجام شد")
        
        return len(backup_files) > 0, backup_files
    
    except Exception as e:
        logger.error(f"خطا در پشتیبان‌گیری از فایل‌های داده: {str(e)}")
        return False, []


def compress_backup(backup_dir: str, format: str = 'tar.gz') -> Tuple[bool, str]:
    """
    فشرده‌سازی پوشه پشتیبان
    
    :param backup_dir: مسیر دایرکتوری پشتیبان
    :param format: فرمت فشرده‌سازی
    :return: نتیجه عملیات و مسیر فایل فشرده
    """
    if format == 'none':
        logger.info("فشرده‌سازی انجام نشد")
        return True, backup_dir
    
    try:
        # تعیین نام فایل خروجی
        parent_dir = os.path.dirname(backup_dir)
        backup_name = os.path.basename(backup_dir)
        
        if format == 'zip':
            # فشرده‌سازی با فرمت ZIP
            output_path = os.path.join(parent_dir, f"{backup_name}.zip")
            
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(backup_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, backup_dir)
                        zipf.write(file_path, os.path.join(backup_name, rel_path))
        
        elif format.startswith('tar'):
            # تعیین نوع فشرده‌سازی برای tar
            if format == 'tar':
                output_path = os.path.join(parent_dir, f"{backup_name}.tar")
                mode = 'w'
            elif format == 'tar.gz':
                output_path = os.path.join(parent_dir, f"{backup_name}.tar.gz")
                mode = 'w:gz'
            elif format == 'tar.bz2':
                output_path = os.path.join(parent_dir, f"{backup_name}.tar.bz2")
                mode = 'w:bz2'
            
            # فشرده‌سازی با فرمت TAR
            with tarfile.open(output_path, mode) as tar:
                tar.add(backup_dir, arcname=backup_name)
        
        logger.info(f"فشرده‌سازی پشتیبان با فرمت {format} در {output_path} انجام شد")
        
        # حذف پوشه اصلی پشتیبان
        shutil.rmtree(backup_dir)
        
        return True, output_path
    
    except Exception as e:
        logger.error(f"خطا در فشرده‌سازی پشتیبان: {str(e)}")
        return False, ""


def upload_backup(backup_path: str, config: Config) -> bool:
    """
    آپلود فایل پشتیبان به فضای ذخیره‌سازی ابری
    
    :param backup_path: مسیر فایل پشتیبان
    :param config: شیء تنظیمات
    :return: نتیجه عملیات
    """
    # این تابع می‌تواند بر اساس نیاز پروژه تکمیل شود
    # در اینجا یک نمونه پیاده‌سازی ارائه شده است
    
    storage_type = config.get('BACKUP_STORAGE_TYPE', 'local')
    
    if storage_type == 'local':
        logger.info("آپلود به حالت محلی انتخاب شده است. نیازی به آپلود نیست")
        return True
    
    elif storage_type == 's3':
        try:
            # واردسازی کتابخانه boto3 برای ارتباط با AWS S3
            import boto3
            
            s3_bucket = config.get('S3_BACKUP_BUCKET', '')
            s3_region = config.get('S3_REGION', 'us-east-1')
            s3_key = config.get('S3_ACCESS_KEY', '')
            s3_secret = config.get('S3_SECRET_KEY', '')
            
            if not s3_bucket:
                logger.error("نام باکت S3 مشخص نشده است")
                return False
            
            # ایجاد نشست boto3
            s3_client = boto3.client(
                's3',
                region_name=s3_region,
                aws_access_key_id=s3_key,
                aws_secret_access_key=s3_secret
            )
            
            # آپلود فایل
            file_name = os.path.basename(backup_path)
            s3_client.upload_file(
                backup_path,
                s3_bucket,
                f"backups/{file_name}"
            )
            
            logger.info(f"فایل پشتیبان با موفقیت به S3 آپلود شد: s3://{s3_bucket}/backups/{file_name}")
            return True
            
        except ImportError:
            logger.error("کتابخانه boto3 نصب نشده است. برای آپلود به S3 باید boto3 را نصب کنید")
            return False
            
        except Exception as e:
            logger.error(f"خطا در آپلود به S3: {str(e)}")
            return False
    
    elif storage_type == 'ftp':
        try:
            # واردسازی کتابخانه ftplib برای ارتباط با FTP
            import ftplib
            
            ftp_host = config.get('FTP_HOST', '')
            ftp_user = config.get('FTP_USER', '')
            ftp_pass = config.get('FTP_PASS', '')
            ftp_dir = config.get('FTP_BACKUP_DIR', '/backups')
            
            if not ftp_host:
                logger.error("آدرس سرور FTP مشخص نشده است")
                return False
            
            # اتصال به سرور FTP
            ftp = ftplib.FTP(ftp_host)
            ftp.login(ftp_user, ftp_pass)
            
            # تغییر به دایرکتوری مورد نظر
            try:
                ftp.cwd(ftp_dir)
            except:
                # ایجاد دایرکتوری اگر وجود نداشته باشد
                ftp.mkd(ftp_dir)
                ftp.cwd(ftp_dir)
            
            # آپلود فایل
            file_name = os.path.basename(backup_path)
            with open(backup_path, 'rb') as file:
                ftp.storbinary(f'STOR {file_name}', file)
            
            ftp.quit()
            
            logger.info(f"فایل پشتیبان با موفقیت به FTP آپلود شد: {ftp_host}/{ftp_dir}/{file_name}")
            return True
            
        except ImportError:
            logger.error("کتابخانه ftplib نصب نشده است. برای آپلود به FTP باید ftplib را نصب کنید")
            return False
            
        except Exception as e:
            logger.error(f"خطا در آپلود به FTP: {str(e)}")
            return False
    
    else:
        logger.error(f"نوع ذخیره‌سازی {storage_type} پشتیبانی نمی‌شود")
        return False


def send_email_report(
    backup_path: str,
    config: Config,
    backup_info: Dict[str, Any],
    recipients: Optional[List[str]] = None
) -> bool:
    """
    ارسال ایمیل گزارش پشتیبان‌گیری
    
    :param backup_path: مسیر فایل پشتیبان
    :param config: شیء تنظیمات
    :param backup_info: اطلاعات پشتیبان‌گیری
    :param recipients: لیست آدرس‌های ایمیل دریافت‌کنندگان
    :return: نتیجه عملیات
    """
    try:
        smtp_host = config.get('SMTP_HOST', '')
        smtp_port = config.get('SMTP_PORT', 587)
        smtp_user = config.get('SMTP_USER', '')
        smtp_pass = config.get('SMTP_PASS', '')
        sender_email = config.get('SENDER_EMAIL', smtp_user)
        
        if not smtp_host or not smtp_user:
            logger.error("تنظیمات SMTP کامل نیست")
            return False
        
        # تنظیم دریافت‌کنندگان
        if not recipients:
            default_recipients = config.get('BACKUP_REPORT_RECIPIENTS', '')
            if default_recipients:
                recipients = [email.strip() for email in default_recipients.split(',')]
            else:
                logger.error("هیچ دریافت‌کننده‌ای مشخص نشده است")
                return False
        
        # ایجاد پیام ایمیل
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"گزارش پشتیبان‌گیری ربات تلگرام - {datetime.get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # ایجاد متن ایمیل
        body = f"""
        <html>
        <body>
            <h2>گزارش پشتیبان‌گیری ربات تلگرام</h2>
            <p>زمان پشتیبان‌گیری: {backup_info.get('timestamp', '-')}</p>
            <p>نوع پشتیبان‌گیری: {backup_info.get('backup_type', '-')}</p>
            <p>اندازه فایل پشتیبان: {backup_info.get('backup_size', '-')} مگابایت</p>
            <p>مسیر فایل پشتیبان: {backup_path}</p>
            
            <h3>جزئیات:</h3>
            <ul>
                <li>پایگاه داده: {'✅ انجام شد' if backup_info.get('db_backup', False) else '❌ انجام نشد'}</li>
                <li>فایل‌های پیکربندی: {'✅ انجام شد' if backup_info.get('config_backup', False) else '❌ انجام نشد'}</li>
                <li>فایل‌های داده: {'✅ انجام شد' if backup_info.get('data_backup', False) else '❌ انجام نشد'}</li>
                <li>فشرده‌سازی: {'✅ انجام شد' if backup_info.get('compression', False) else '❌ انجام نشد'}</li>
                <li>آپلود: {'✅ انجام شد' if backup_info.get('upload', False) else '❌ انجام نشد یا درخواست نشده'}</li>
            </ul>
            
            <p>این ایمیل به صورت خودکار ارسال شده است.</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # پیوست کردن فایل پشتیبان (اختیاری، بسته به اندازه فایل)
        attach_file = False  # تغییر به True برای پیوست کردن فایل
        if attach_file and os.path.exists(backup_path) and os.path.getsize(backup_path) < 10 * 1024 * 1024:  # کمتر از 10 مگابایت
            with open(backup_path, 'rb') as file:
                attachment = MIMEApplication(file.read(), _subtype=os.path.splitext(backup_path)[1][1:])
                attachment.add_header('Content-Disposition', f'attachment; filename={os.path.basename(backup_path)}')
                msg.attach(attachment)
        
        # اتصال به سرور SMTP و ارسال ایمیل
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        logger.info(f"ایمیل گزارش پشتیبان‌گیری به {len(recipients)} گیرنده ارسال شد")
        return True
    
    except Exception as e:
        logger.error(f"خطا در ارسال ایمیل گزارش پشتیبان‌گیری: {str(e)}")
        return False


def run_backup(args: argparse.Namespace) -> int:
    """
    اجرای فرآیند پشتیبان‌گیری
    
    :param args: آرگومان‌های خط فرمان
    :return: کد خروجی (0 موفق، 1 ناموفق)
    """
    try:
        # تنظیم سطح لاگینگ
        if args.verbose:
            logger.setLevel(logging.DEBUG)
        
        logger.info("شروع فرآیند پشتیبان‌گیری")
        
        # دریافت تنظیمات
        config = Config(args.config_path)
        
        # دریافت مسیر پایگاه داده
        db_path = get_db_path(args.db_path)
        
        # ایجاد دایرکتوری پشتیبان
        backup_dir = create_backup_directory(args.output_dir)
        
        # اطلاعات پشتیبان‌گیری
        backup_info = {
            'timestamp': get_current_datetime().isoformat(),
            'backup_type': args.backup_type,
            'db_backup': False,
            'config_backup': False,
            'data_backup': False,
            'compression': False,
            'upload': False,
            'backup_path': backup_dir
        }
        
        # پشتیبان‌گیری از پایگاه داده
        if args.backup_type in ['full', 'db-only']:
            db_success, db_path = backup_database(db_path, backup_dir)
            backup_info['db_backup'] = db_success
        
        # پشتیبان‌گیری از فایل‌های پیکربندی
        if args.backup_type in ['full', 'config-only']:
            config_success, config_files = backup_config_files(args.config_path, backup_dir)
            backup_info['config_backup'] = config_success
        
        # پشتیبان‌گیری از فایل‌های داده
        if args.backup_type in ['full', 'data-only']:
            data_success, data_files = backup_data_files(backup_dir)
            backup_info['data_backup'] = data_success
        
        # فشرده‌سازی پشتیبان
        compress_success, compressed_path = compress_backup(backup_dir, args.format)
        backup_info['compression'] = compress_success
        backup_info['backup_path'] = compressed_path
        
        # محاسبه اندازه فایل پشتیبان
        if os.path.exists(compressed_path):
            size_bytes = os.path.getsize(compressed_path)
            size_mb = round(size_bytes / (1024 * 1024), 2)
            backup_info['backup_size'] = size_mb
        
        # آپلود پشتیبان
        if args.upload and compress_success:
            upload_success = upload_backup(compressed_path, config)
            backup_info['upload'] = upload_success
        
        # ارسال ایمیل گزارش
        if args.send_email:
            email_recipients = None
            if args.email_recipients:
                email_recipients = [email.strip() for email in args.email_recipients.split(',')]
            
            send_email_report(compressed_path, config, backup_info, email_recipients)
        
        logger.info("فرآیند پشتیبان‌گیری با موفقیت به پایان رسید")
        return 0
    
    except Exception as e:
        logger.error(f"خطا در اجرای فرآیند پشتیبان‌گیری: {str(e)}")
        return 1


def main() -> None:
    """
    تابع اصلی
    """
    args = parse_arguments()
    exit_code = run_backup(args)
    sys.exit(exit_code)


if __name__ == '__main__':
    main() 