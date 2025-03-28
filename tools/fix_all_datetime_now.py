#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
اصلاح خودکار get_current_datetime()

این اسکریپت فایل‌های پایتون را برای یافتن موارد استفاده از get_current_datetime() جستجو و 
آن‌ها را به استفاده از get_current_datetime از ماژول timezone_utils تبدیل می‌کند.
این تغییر برای اطمینان از استفاده صحیح از منطقه زمانی در کل پروژه انجام می‌شود.
"""

import os
import re
import sys
import argparse
from typing import List, Dict, Any, Set, Optional, Tuple
import logging
import fnmatch
import json
import difflib
import shutil
from datetime import datetime
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
        description='اصلاح خودکار موارد استفاده از get_current_datetime() در فایل‌های پایتون'
    )
    
    parser.add_argument(
        '-d', '--directory',
        default='src',
        help='دایرکتوری برای جستجو (پیش‌فرض: src)'
    )
    
    parser.add_argument(
        '--report-input',
        default=None,
        help='فایل گزارش ورودی از اسکریپت find_datetime_now_usages.py (اختیاری)'
    )
    
    parser.add_argument(
        '--report-output',
        default='fix_report.json',
        help='فایل گزارش خروجی (پیش‌فرض: fix_report.json)'
    )
     
    parser.add_argument(
        '--backup',
        action='store_true',
        help='ساخت نسخه پشتیبان از فایل‌ها قبل از تغییر'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='نمایش تغییرات بدون اعمال آن‌ها'
    )
    
    parser.add_argument(
        '-i', '--ignore',
        default='venv,__pycache__,.git,*.pyc,*.pyo,*~,docs,build,dist,*.egg-info',
        help='الگوهای فایل و پوشه برای نادیده گرفتن (با کاما جدا شده)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='نمایش اطلاعات بیشتر در خروجی'
    )
    
    return parser.parse_args()


def should_ignore(path: str, ignore_patterns: List[str]) -> bool:
    """
    بررسی اینکه آیا یک مسیر باید نادیده گرفته شود
    
    :param path: مسیر فایل یا پوشه
    :param ignore_patterns: لیست الگوهای نادیده گرفتن
    :return: True اگر باید نادیده گرفته شود، در غیر این صورت False
    """
    path = os.path.normpath(path)
    
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
        
        # بررسی اینکه آیا بخشی از مسیر با الگو مطابقت دارد
        path_parts = path.split(os.sep)
        for part in path_parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    
    return False


def create_backup(file_path: str) -> str:
    """
    ایجاد نسخه پشتیبان از فایل
    
    :param file_path: مسیر فایل
    :return: مسیر فایل پشتیبان
    """
    timestamp = get_current_datetime().strftime('%Y%m%d%H%M%S')
    backup_path = f"{file_path}.{timestamp}.bak"
    shutil.copy2(file_path, backup_path)
    return backup_path


def add_timezone_utils_import(content: str) -> Tuple[str, bool]:
    """
    افزودن import برای ماژول timezone_utils
    
    :param content: محتوای فایل
    :return: محتوای جدید و آیا تغییری ایجاد شده است
    """
    changed = False
    
    # بررسی اینکه آیا قبلاً import شده است
    if re.search(r'from\s+.*?utils\.timezone_utils\s+import\s+get_current_datetime', content):
        return content, changed
    
    # الگوهای مختلف برای تشخیص نوع import
    if re.search(r'from\s+\.utils\s+import', content):
        # import از utils در همان پکیج
        new_content = re.sub(
            r'(from\s+\.utils\s+import\s+[^(\n]*?)(\n|$)',
            r'\1, get_current_datetime\2',
            content,
            count=1
        )
        changed = new_content != content
        if changed:
            return new_content, changed
    
    if re.search(r'from\s+.*?\.utils\s+import', content):
        # import از utils از مسیر نسبی
        new_content = re.sub(
            r'(from\s+(.*?)\.utils\s+import\s+[^(\n]*?)(\n|$)',
            r'\1, get_current_datetime\3',
            content,
            count=1
        )
        changed = new_content != content
        if changed:
            return new_content, changed
    
    if re.search(r'from\s+src\.utils\s+import', content):
        # import مستقیم از src.utils
        new_content = re.sub(
            r'(from\s+src\.utils\s+import\s+[^(\n]*?)(\n|$)',
            r'\1, get_current_datetime\2',
            content,
            count=1
        )
        changed = new_content != content
        if changed:
            return new_content, changed
    
    if re.search(r'import\s+.*?utils', content):
        # اگر utils به صورت پکیج import شده باشد، باید به صورت دقیق‌تر import کنیم
        lines = content.splitlines()
        import_line = "from ..utils.timezone_utils import get_current_datetime"
        
        # یافتن محل مناسب برای افزودن import
        import_index = -1
        for i, line in enumerate(lines):
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                import_index = i
            elif line.strip() and import_index >= 0 and not (line.strip().startswith('import ') or line.strip().startswith('from ')):
                # اولین خط غیرخالی بعد از آخرین import
                lines.insert(import_index + 1, import_line)
                changed = True
                return '\n'.join(lines), changed
        
        # اگر هیچ import دیگری نباشد یا همه خطوط import باشند
        if import_index >= 0:
            lines.insert(import_index + 1, import_line)
        else:
            # افزودن در ابتدای فایل
            lines.insert(0, import_line)
        
        changed = True
        return '\n'.join(lines), changed
    
    # اگر هیچ import دیگری وجود نداشته باشد
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip() and not line.strip().startswith('#'):
            # اولین خط غیرخالی و غیرنظر
            lines.insert(i, "from ..utils.timezone_utils import get_current_datetime")
            changed = True
            return '\n'.join(lines), changed
    
    # اگر فایل خالی باشد
    content = "from ..utils.timezone_utils import get_current_datetime\n\n" + content
    changed = True
    return content, changed


def replace_datetime_now(content: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    جایگزینی get_current_datetime() با get_current_datetime()
    
    :param content: محتوای فایل
    :return: محتوای جدید و لیست تغییرات
    """
    changes = []
    
    # الگوهای مختلف برای get_current_datetime()
    patterns = [
        (r'datetime\.now\(\)', 'get_current_datetime()'),
        (r'datetime\.datetime\.now\(\)', 'get_current_datetime()'),
    ]
    
    lines = content.splitlines()
    new_lines = lines.copy()
    
    for i, line in enumerate(lines):
        # بررسی الگوهای منفی (مواردی که نباید تغییر کنند)
        if 'get_current_datetime' in line:
            continue
        
        original_line = line
        modified = False
        
        for pattern, replacement in patterns:
            if re.search(pattern, line):
                # ذخیره اطلاعات تغییر
                changes.append({
                    'line_number': i + 1,
                    'original': original_line,
                    'modified': line.replace(re.search(pattern, line).group(0), replacement)
                })
                
                # اعمال تغییر
                new_lines[i] = line.replace(re.search(pattern, line).group(0), replacement)
                modified = True
                break
        
        if modified:
            line = new_lines[i]
    
    return '\n'.join(new_lines), changes


def process_file(
    file_path: str,
    dry_run: bool = False,
    create_backup_file: bool = False,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    پردازش یک فایل و اصلاح موارد استفاده از get_current_datetime()
    
    :param file_path: مسیر فایل
    :param dry_run: بدون اعمال تغییرات
    :param create_backup_file: ایجاد نسخه پشتیبان
    :param verbose: نمایش اطلاعات بیشتر
    :return: اطلاعات تغییرات
    """
    result = {
        'file': file_path,
        'backup': None,
        'changes': [],
        'import_added': False
    }
    
    try:
        # خواندن محتوای فایل
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # جایگزینی get_current_datetime()
        new_content, changes = replace_datetime_now(content)
        result['changes'] = changes
        
        # اگر تغییری وجود داشته باشد، import موردنیاز را اضافه می‌کنیم
        if changes:
            import_content, import_added = add_timezone_utils_import(new_content)
            result['import_added'] = import_added
            
            if import_added:
                new_content = import_content
            
            # نمایش تفاوت‌ها در حالت verbose
            if verbose:
                diff = list(difflib.unified_diff(
                    content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=file_path,
                    tofile=f"{file_path} (modified)",
                    n=3
                ))
                if diff:
                    logger.info(f"تفاوت‌ها در {file_path}:\n{''.join(diff)}")
            
            # ذخیره تغییرات
            if not dry_run:
                # ایجاد نسخه پشتیبان
                if create_backup_file:
                    backup_path = create_backup(file_path)
                    result['backup'] = backup_path
                    if verbose:
                        logger.info(f"نسخه پشتیبان در {backup_path} ذخیره شد")
                
                # ذخیره تغییرات
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                logger.info(f"فایل {file_path} با {len(changes)} تغییر اصلاح شد")
        else:
            if verbose:
                logger.info(f"هیچ تغییری در {file_path} نیاز نبود")
    
    except Exception as e:
        logger.error(f"خطا در پردازش فایل {file_path}: {str(e)}")
        result['error'] = str(e)
    
    return result


def process_directory(
    directory: str,
    ignore_patterns: List[str],
    dry_run: bool = False,
    create_backup_file: bool = False,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    پردازش یک دایرکتوری و اصلاح موارد استفاده از get_current_datetime() در همه فایل‌های پایتون
    
    :param directory: مسیر دایرکتوری
    :param ignore_patterns: الگوهای نادیده گرفتن
    :param dry_run: بدون اعمال تغییرات
    :param create_backup_file: ایجاد نسخه پشتیبان
    :param verbose: نمایش اطلاعات بیشتر
    :return: لیست نتایج پردازش
    """
    results = []
    
    for root, dirs, files in os.walk(directory):
        # حذف پوشه‌های نادیده گرفته شده
        dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d), ignore_patterns)]
        
        for file in files:
            # بررسی فقط فایل‌های پایتون
            if not file.endswith('.py') or should_ignore(os.path.join(root, file), ignore_patterns):
                continue
            
            file_path = os.path.join(root, file)
            
            # پردازش فایل
            result = process_file(
                file_path,
                dry_run,
                create_backup_file,
                verbose
            )
            
            # اضافه کردن به نتایج اگر تغییری وجود داشته باشد
            if result['changes'] or 'error' in result:
                results.append(result)
    
    return results


def process_from_report(
    report_file: str,
    base_directory: str,
    dry_run: bool = False,
    create_backup_file: bool = False,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    پردازش فایل‌ها بر اساس گزارش ورودی
    
    :param report_file: مسیر فایل گزارش
    :param base_directory: دایرکتوری پایه
    :param dry_run: بدون اعمال تغییرات
    :param create_backup_file: ایجاد نسخه پشتیبان
    :param verbose: نمایش اطلاعات بیشتر
    :return: لیست نتایج پردازش
    """
    results = []
    
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        
        files_to_process = [os.path.join(base_directory, file_info['file']) for file_info in report_data.get('files', [])]
        
        for file_path in files_to_process:
            if not os.path.isfile(file_path):
                logger.warning(f"فایل {file_path} وجود ندارد، نادیده گرفته می‌شود")
                continue
            
            # پردازش فایل
            result = process_file(
                file_path,
                dry_run,
                create_backup_file,
                verbose
            )
            
            # اضافه کردن به نتایج اگر تغییری وجود داشته باشد
            if result['changes'] or 'error' in result:
                results.append(result)
    
    except Exception as e:
        logger.error(f"خطا در خواندن فایل گزارش {report_file}: {str(e)}")
    
    return results


def save_report(results: List[Dict[str, Any]], output_file: str) -> None:
    """
    ذخیره گزارش تغییرات در فایل JSON
    
    :param results: لیست نتایج پردازش
    :param output_file: مسیر فایل خروجی
    """
    total_changes = sum(len(result['changes']) for result in results)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': get_current_datetime().isoformat(),
            'total_files': len(results),
            'total_changes': total_changes,
            'files': results
        }, f, ensure_ascii=False, indent=2)
    
    logger.info(f"گزارش تغییرات در {output_file} ذخیره شد")


def display_summary(results: List[Dict[str, Any]], dry_run: bool) -> None:
    """
    نمایش خلاصه تغییرات
    
    :param results: لیست نتایج پردازش
    :param dry_run: آیا در حالت dry-run هستیم
    """
    total_changes = sum(len(result['changes']) for result in results)
    total_errors = sum(1 for result in results if 'error' in result)
    
    logger.info("\n=== خلاصه تغییرات ===")
    logger.info(f"تعداد کل فایل‌های تغییر یافته: {len(results) - total_errors}")
    logger.info(f"تعداد کل تغییرات: {total_changes}")
    
    if total_errors > 0:
        logger.warning(f"تعداد کل خطاها: {total_errors}")
    
    if dry_run:
        logger.info("\nاین یک اجرای آزمایشی بود. هیچ تغییری اعمال نشد.")
        logger.info("برای اعمال تغییرات، دوباره بدون پارامتر --dry-run اجرا کنید.")


def main() -> None:
    """
    تابع اصلی
    """
    args = parse_arguments()
    
    # تنظیم سطح لاگینگ
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # تبدیل رشته ignore به لیست
    ignore_patterns = [p.strip() for p in args.ignore.split(',') if p.strip()]
    
    # اطلاعات اجرا
    logger.info(f"{'اجرای آزمایشی' if args.dry_run else 'اصلاح'} موارد استفاده از get_current_datetime()")
    
    # پردازش فایل‌ها
    if args.report_input:
        logger.info(f"پردازش بر اساس گزارش: {args.report_input}")
        results = process_from_report(
            args.report_input,
            args.directory,
            args.dry_run,
            args.backup,
            args.verbose
        )
    else:
        logger.info(f"جستجو و پردازش در پوشه: {args.directory}")
        logger.info(f"الگوهای نادیده گرفتن: {ignore_patterns}")
        
        # بررسی وجود دایرکتوری
        if not os.path.isdir(args.directory):
            logger.error(f"دایرکتوری {args.directory} وجود ندارد")
            sys.exit(1)
        
        results = process_directory(
            args.directory,
            ignore_patterns,
            args.dry_run,
            args.backup,
            args.verbose
        )
    
    # نمایش خلاصه تغییرات
    display_summary(results, args.dry_run)
    
    # ذخیره گزارش
    save_report(results, args.report_output)


if __name__ == '__main__':
    main()