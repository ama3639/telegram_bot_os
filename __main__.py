#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
اسکریپت اصلاح خودکار کد.

این اسکریپت مشکلات زیر را برطرف می‌کند:
1. جایگزینی datetime.now() با get_current_datetime()
2. اصلاح مسیرهای import
3. رفع کاراکترهای غیر ASCII در رشته‌های بایت
4. اضافه کردن import برای متغیرهای تعریف‌نشده

تاریخ ایجاد: ۱۴۰۴/۰۱/۲۰
آخرین ویرایش: ۱۴۰۴/۰۷/۲۰
"""

import os
import re
import argparse
import shutil
from datetime import datetime
from src.utils.timezone_utils import get_current_datetime
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def make_backup(file_path, backup_dir):
    """ایجاد نسخه پشتیبان از فایل قبل از تغییر."""
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    file_name = os.path.basename(file_path)
    timestamp = get_current_datetime().strftime("%Y%m%d%H%M%S")
    backup_path = os.path.join(backup_dir, f"{file_name}.{timestamp}.bak")
    
    shutil.copy2(file_path, backup_path)
    return backup_path

def fix_datetime_now(content):
    """جایگزینی datetime.now() با get_current_datetime()."""
    has_datetime_import = re.search(r'(from\s+datetime\s+import\s+datetime|import\s+datetime(\s+as\s+\w+)?)', content)
    has_datetime_now = re.search(r'datetime\.now\(\)', content)
    
    if not has_datetime_now:
        return content, 0
    
    if 'from utils.timezone_utils import get_current_datetime' not in content:
        if has_datetime_import:
            content = re.sub(
                r'(from\s+datetime\s+import\s+datetime|import\s+datetime(\s+as\s+\w+)?)',
                r'\1\nfrom utils.timezone_utils import get_current_datetime',
                content,
                count=1
            )
        else:
            docstring_pattern = r'(""".*?"""|\'\'\'.*?\'\'\')\s*'
            docstring_match = re.search(docstring_pattern, content, re.DOTALL)
            if docstring_match:
                docstring_end = docstring_match.end()
                content = (
                    content[:docstring_end] + 
                    '\nfrom utils.timezone_utils import get_current_datetime\n' + 
                    content[docstring_end:]
                )
            else:
                content = 'from utils.timezone_utils import get_current_datetime\n\n' + content
    
    content_new, replacements = re.subn(r'datetime\.now\(\)', 'get_current_datetime()', content)
    return content_new, replacements

def fix_imports(content):
    """اصلاح مسیرهای import بر اساس ساختار پروژه."""
    replacements = 0
    content_new, count = re.subn(r'from\s+src\.', 'from ', content)
    replacements += count
    content_new, count = re.subn(r'from\s+\.\.(\w+)', r'from \1', content_new)
    replacements += count
    return content_new, replacements

def fix_non_ascii(content):
    """رفع کاراکترهای غیر ASCII در رشته‌های بایت."""
    byte_string_pattern = r"b(['\"])(.*?)\1"
    matches = re.findall(byte_string_pattern, content, re.DOTALL)
    for quote, match in matches:
        if any(ord(char) > 127 for char in match):
            unicode_string = match.encode().decode('unicode_escape', errors='replace')
            old_string = f"b{quote}{match}{quote}"
            new_string = f"{quote}{unicode_string}{quote}"
            content = content.replace(old_string, new_string)
    return content

def fix_undefined_variables(content):
    """اضافه کردن import‌های لازم برای متغیرهای تعریف‌نشده."""
    undefined_vars = {
        'AsyncGenerator': 'from typing import AsyncGenerator',
        'BotCommandScopeChat': 'from telegram import BotCommandScopeChat',
        'fnmatch': 'import fnmatch',
        'glob': 'import glob',
        'coverage': 'import coverage',
        'xmlrunner': 'import xmlrunner',
        'timezone': 'from datetime import timezone',
        'get_current_datetime': 'from utils.timezone_utils import get_current_datetime'
    }
    
    for var, import_statement in undefined_vars.items():
        if re.search(rf'\b{var}\b', content) and import_statement not in content:
            docstring_pattern = r'(""".*?"""|\'\'\'.*?\'\'\')\s*'
            docstring_match = re.search(docstring_pattern, content, re.DOTALL)
            docstring_end = 0  # مقدار پیش‌فرض برای جلوگیری از خطا
            if docstring_match:
                docstring_end = docstring_match.end()
                content = (
                    content[:docstring_end] + 
                    f'\n{import_statement}\n' + 
                    content[docstring_end:]
                )
            else:
                content = f'{import_statement}\n' + content
    return content

def process_file(file_path, backup_dir=None, dry_run=False):
    """پردازش یک فایل Python و اعمال اصلاحات."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content_new, datetime_fixes = fix_datetime_now(content)
        content_new, import_fixes = fix_imports(content_new)
        content_new = fix_non_ascii(content_new)
        content_new = fix_undefined_variables(content_new)
        
        if content_new != content and not dry_run:
            if backup_dir:
                make_backup(file_path, backup_dir)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content_new)
        
        return datetime_fixes, import_fixes
    
    except Exception as e:
        print(f"خطا در پردازش فایل {file_path}: {str(e)}")
        return 0, 0

def main():
    """تابع اصلی برنامه."""
    parser = argparse.ArgumentParser(description='اصلاح خودکار کد پروژه')
    parser.add_argument('--dir', type=str, default='.', help='مسیر دایرکتوری ریشه پروژه')
    parser.add_argument('--backup', action='store_true', help='ایجاد نسخه پشتیبان از فایل‌ها')
    parser.add_argument('--backup-dir', type=str, default='backups', help='مسیر دایرکتوری نسخه‌های پشتیبان')
    parser.add_argument('--dry-run', action='store_true', help='اجرای آزمایشی بدون تغییر فایل‌ها')
    parser.add_argument('--verbose', action='store_true', help='نمایش جزئیات بیشتر')
    args = parser.parse_args()
    
    root_dir = args.dir
    backup_dir = args.backup_dir if args.backup else None
    
    total_files = 0
    fixed_datetime_files = 0
    fixed_import_files = 0
    total_datetime_fixes = 0
    total_import_fixes = 0
    
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                total_files += 1
                
                datetime_fixes, import_fixes = process_file(file_path, backup_dir, args.dry_run)
                
                if datetime_fixes > 0:
                    fixed_datetime_files += 1
                    total_datetime_fixes += datetime_fixes
                if import_fixes > 0:
                    fixed_import_files += 1
                    total_import_fixes += import_fixes
                
                if args.verbose and (datetime_fixes > 0 or import_fixes > 0):
                    print(f"{file_path}:")
                    if datetime_fixes > 0:
                        print(f"  - {datetime_fixes} مورد datetime.now() اصلاح شد")
                    if import_fixes > 0:
                        print(f"  - {import_fixes} مورد مسیر import اصلاح شد")
    
    print(f"\nگزارش نهایی:")
    print(f"تعداد کل فایل‌های بررسی شده: {total_files}")
    print(f"تعداد فایل‌های اصلاح شده برای datetime.now(): {fixed_datetime_files}")
    print(f"تعداد کل موارد اصلاح شده datetime.now(): {total_datetime_fixes}")
    print(f"تعداد فایل‌های اصلاح شده برای مسیرهای import: {fixed_import_files}")
    print(f"تعداد کل موارد اصلاح شده مسیرهای import: {total_import_fixes}")
    if args.dry_run:
        print("\nتوجه: این اجرا در حالت آزمایشی بود و هیچ فایلی تغییر نکرد.")

if __name__ == "__main__":
    main()