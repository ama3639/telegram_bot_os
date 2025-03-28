#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
یافتن موارد استفاده از get_current_datetime()

این اسکریپت پوشه‌های مشخص شده را برای یافتن موارد استفاده از get_current_datetime() جستجو می‌کند.
استفاده از get_current_datetime() به جای get_current_datetime از ماژول timezone_utils می‌تواند
منجر به مشکلات منطقه زمانی شود، زیرا منطقه زمانی را در نظر نمی‌گیرد.
"""


from src.utils.timezone_utils import get_current_datetime
import os
import re
import sys
import argparse
from typing import List, Dict, Any, Set, Optional, Tuple
import logging
import fnmatch
import json

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
        description='یافتن موارد استفاده از get_current_datetime() در فایل‌های پایتون'
    )
    
    parser.add_argument(
        '-d', '--directory',
        default='src',
        help='دایرکتوری برای جستجو (پیش‌فرض: src)'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='usage_report.json',
        help='فایل خروجی JSON (پیش‌فرض: usage_report.json)'
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


def find_datetime_now_usages(
    directory: str,
    ignore_patterns: List[str],
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    یافتن موارد استفاده از get_current_datetime() در فایل‌های پایتون
    
    :param directory: دایرکتوری برای جستجو
    :param ignore_patterns: الگوهای فایل و پوشه برای نادیده گرفتن
    :param verbose: نمایش اطلاعات بیشتر
    :return: لیست اطلاعات مربوط به استفاده‌های یافت شده
    """
    results = []
    patterns = [
        r'datetime\.now\(\)',
        r'datetime\.datetime\.now\(\)',
        r'from\s+datetime\s+import\s+datetime\s*(?:.*\n){0,5}?.*datetime\.now\(\)'
    ]
    
    # الگوهای منفی (مواردی که نباید به عنوان خطا گزارش شوند)
    negative_patterns = [
        r'get_current_datetime',  # اگر در همان خط از get_current_datetime استفاده شده باشد
        r'def\s+get_current_datetime'  # تعریف تابع get_current_datetime
    ]
    
    # شمارنده‌ها
    file_count = 0
    issue_count = 0
    checked_files_count = 0
    
    for root, dirs, files in os.walk(directory):
        # حذف پوشه‌های نادیده گرفته شده
        dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d), ignore_patterns)]
        
        for file in files:
            # بررسی فقط فایل‌های پایتون
            if not file.endswith('.py') or should_ignore(os.path.join(root, file), ignore_patterns):
                continue
            
            file_path = os.path.join(root, file)
            checked_files_count += 1
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                file_issues = []
                for line_number, line in enumerate(content.splitlines(), 1):
                    # بررسی الگوهای منفی
                    skip_line = False
                    for negative_pattern in negative_patterns:
                        if re.search(negative_pattern, line):
                            skip_line = True
                            break
                    
                    if skip_line:
                        continue
                    
                    # بررسی الگوهای مثبت
                    for pattern in patterns:
                        match = re.search(pattern, line)
                        if match:
                            context = []
                            # اضافه کردن خطوط قبل و بعد برای زمینه
                            lines = content.splitlines()
                            start_line = max(0, line_number - 3)
                            end_line = min(len(lines), line_number + 2)
                            
                            for i in range(start_line, end_line):
                                prefix = '> ' if i + 1 == line_number else '  '
                                context.append(f"{prefix}{i + 1}: {lines[i]}")
                            
                            file_issues.append({
                                'line_number': line_number,
                                'line': line.strip(),
                                'matched_pattern': pattern,
                                'context': context
                            })
                
                if file_issues:
                    file_count += 1
                    issue_count += len(file_issues)
                    results.append({
                        'file': os.path.relpath(file_path, directory),
                        'issues': file_issues
                    })
                    
                    if verbose:
                        logger.info(f"یافتن {len(file_issues)} مورد در {file_path}")
            
            except Exception as e:
                logger.error(f"خطا در پردازش فایل {file_path}: {str(e)}")
    
    logger.info(f"بررسی {checked_files_count} فایل، یافتن {issue_count} مورد در {file_count} فایل")
    
    return results


def save_results(results: List[Dict[str, Any]], output_file: str) -> None:
    """
    ذخیره نتایج در فایل JSON
    
    :param results: لیست نتایج
    :param output_file: مسیر فایل خروجی
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_files': len(results),
            'total_issues': sum(len(file_info['issues']) for file_info in results),
            'files': results
        }, f, ensure_ascii=False, indent=2)
    
    logger.info(f"نتایج در {output_file} ذخیره شد")


def display_results_summary(results: List[Dict[str, Any]]) -> None:
    """
    نمایش خلاصه نتایج
    
    :param results: لیست نتایج
    """
    total_issues = sum(len(file_info['issues']) for file_info in results)
    
    if not results:
        logger.info("هیچ موردی یافت نشد!")
        return
    
    logger.info("=== خلاصه نتایج ===")
    logger.info(f"تعداد کل فایل‌های با مشکل: {len(results)}")
    logger.info(f"تعداد کل موارد: {total_issues}")
    
    # نمایش 5 فایل با بیشترین موارد
    files_sorted = sorted(results, key=lambda x: len(x['issues']), reverse=True)
    logger.info("\n5 فایل با بیشترین تعداد موارد:")
    for i, file_info in enumerate(files_sorted[:5], 1):
        logger.info(f"{i}. {file_info['file']}: {len(file_info['issues'])} مورد")


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
    
    logger.info(f"جستجو در پوشه: {args.directory}")
    logger.info(f"الگوهای نادیده گرفتن: {ignore_patterns}")
    
    # بررسی وجود دایرکتوری
    if not os.path.isdir(args.directory):
        logger.error(f"دایرکتوری {args.directory} وجود ندارد")
        sys.exit(1)
    
    # یافتن موارد استفاده از get_current_datetime()
    results = find_datetime_now_usages(
        args.directory,
        ignore_patterns,
        args.verbose
    )
    
    # نمایش خلاصه نتایج
    display_results_summary(results)
    
    # ذخیره نتایج
    save_results(results, args.output)


if __name__ == '__main__':
    main()