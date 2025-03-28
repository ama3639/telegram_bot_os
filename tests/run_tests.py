#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
اجراکننده تست‌های پروژه

این اسکریپت همه تست‌های پروژه را اجرا کرده و گزارش کاملی از نتایج ارائه می‌دهد.
قابلیت‌های این اسکریپت:
- اجرای تمام تست‌ها یا تست‌های انتخابی
- تولید گزارش پوشش کد (coverage)
- خروجی با جزئیات یا خلاصه
- تنظیم سطح لاگینگ
"""

import os
import sys
import unittest
import argparse
import time
import platform
import logging
from typing import List, Optional
import importlib

# افزودن مسیر ریشه پروژه به sys.path برای واردسازی ماژول‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# تلاش برای واردسازی کتابخانه coverage
try:
    import coverage
    HAS_COVERAGE = True
except ImportError:
    HAS_COVERAGE = False


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
        description='اجرای تست‌های پروژه'
    )
    
    parser.add_argument(
        '--test',
        action='append',
        default=[],
        help='اجرای تست‌های مشخص (می‌تواند چندین بار استفاده شود)'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='اجرای تمام تست‌ها'
    )
    
    parser.add_argument(
        '--exclude',
        action='append',
        default=[],
        help='نادیده گرفتن تست‌های مشخص (می‌تواند چندین بار استفاده شود)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='count',
        default=0,
        help='سطح جزئیات خروجی (می‌تواند تکرار شود برای سطح بیشتر)'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='خروجی حداقلی (فقط خطاها)'
    )
    
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='تولید گزارش پوشش کد'
    )
    
    parser.add_argument(
        '--coverage-html',
        action='store_true',
        help='تولید گزارش پوشش کد به فرمت HTML'
    )
    
    parser.add_argument(
        '--no-windows-tests',
        action='store_true',
        help='نادیده گرفتن تست‌های مخصوص ویندوز'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='سطح لاگینگ (پیش‌فرض: INFO)'
    )
    
    parser.add_argument(
        '--output', '-o',
        default=None,
        help='مسیر فایل خروجی (اختیاری)'
    )
    
    parser.add_argument(
        '--junit-xml',
        default=None,
        help='مسیر فایل خروجی JUnit XML (برای یکپارچگی با CI/CD)'
    )
    
    return parser.parse_args()


def discover_tests(
    exclude_list: List[str] = None,
    no_windows_tests: bool = False
) -> unittest.TestSuite:
    """
    یافتن تست‌های قابل اجرا
    
    :param exclude_list: لیست تست‌هایی که باید نادیده گرفته شوند
    :param no_windows_tests: آیا تست‌های مخصوص ویندوز نادیده گرفته شوند؟
    :return: مجموعه تست‌های قابل اجرا
    """
    if exclude_list is None:
        exclude_list = []
    
    # اضافه کردن تست‌های مخصوص ویندوز به لیست استثناها اگر لازم باشد
    if no_windows_tests:
        exclude_list.append('test_timezone_fix_windows')
    
    # بررسی اگر روی ویندوز نیستیم، تست‌های مخصوص ویندوز به طور خودکار نادیده گرفته شوند
    if platform.system() != 'Windows':
        exclude_list.append('test_timezone_fix_windows')
    
    # یافتن تست‌های قابل اجرا در دایرکتوری tests
    loader = unittest.TestLoader()
    all_tests = loader.discover('tests', pattern='test_*.py')
    
    # فیلتر کردن تست‌های مستثنی شده
    if exclude_list:
        filtered_suite = unittest.TestSuite()
        
        for suite in all_tests:
            for test_case in suite:
                if isinstance(test_case, unittest.TestSuite):
                    # بررسی نام کلاس تست
                    skip_case = False
                    for exclude_pattern in exclude_list:
                        if exclude_pattern in test_case.id():
                            skip_case = True
                            break
                    
                    if not skip_case:
                        filtered_suite.addTest(test_case)
                else:
                    # تست‌های منفرد
                    skip_test = False
                    for exclude_pattern in exclude_list:
                        if exclude_pattern in test_case.id():
                            skip_test = True
                            break
                    
                    if not skip_test:
                        filtered_suite.addTest(test_case)
        
        return filtered_suite
    
    return all_tests


def load_specific_tests(test_names: List[str]) -> unittest.TestSuite:
    """
    بارگذاری تست‌های مشخص
    
    :param test_names: لیست نام‌های تست برای بارگذاری
    :return: مجموعه تست‌های بارگذاری شده
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    for test_name in test_names:
        # بررسی آیا نام تست شامل نقطه است (یعنی کلاس.متد)
        if '.' in test_name:
            module_name, class_name = test_name.rsplit('.', 1)
            module = importlib.import_module(f'tests.{module_name}')
            suite.addTest(loader.loadTestsFromName(class_name, module))
        else:
            # بارگذاری کل ماژول تست
            try:
                module = importlib.import_module(f'tests.{test_name}')
                suite.addTest(loader.loadTestsFromModule(module))
            except ImportError:
                logger.error(f"تست {test_name} یافت نشد")
    
    return suite


def setup_coverage() -> Optional[coverage.Coverage]:
    """
    تنظیم و آغاز اندازه‌گیری پوشش کد
    
    :return: شیء coverage یا None اگر در دسترس نباشد
    """
    if not HAS_COVERAGE:
        logger.warning("کتابخانه coverage یافت نشد. گزارش پوشش کد تولید نخواهد شد.")
        return None
    
    cov = coverage.Coverage(
        source=['src'],
        omit=[
            '*/tests/*',
            '*/migrations/*',
            '*/settings/*',
            '*/docs/*'
        ]
    )
    cov.start()
    return cov


def save_coverage_report(cov: coverage.Coverage, html: bool = False) -> None:
    """
    ذخیره گزارش پوشش کد
    
    :param cov: شیء coverage
    :param html: آیا گزارش HTML هم تولید شود؟
    """
    cov.stop()
    cov.save()
    
    # نمایش گزارش خلاصه
    print("\n===== گزارش پوشش کد =====")
    cov.report()
    
    # تولید گزارش HTML
    if html:
        reports_dir = os.path.join('reports', 'coverage')
        os.makedirs(reports_dir, exist_ok=True)
        cov.html_report(directory=reports_dir)
        print(f"\nگزارش HTML پوشش کد در {reports_dir} ذخیره شد")


def run_tests(args: argparse.Namespace) -> int:
    """
    اجرای تست‌ها بر اساس آرگومان‌های ورودی
    
    :param args: آرگومان‌های خط فرمان
    :return: کد خروجی (0 موفق، 1 ناموفق)
    """
    # تنظیم سطح لاگینگ
    log_level = getattr(logging, args.log_level.upper())
    logger.setLevel(log_level)
    
    # تنظیم coverage
    cov = None
    if args.coverage or args.coverage_html:
        cov = setup_coverage()
    
    try:
        # انتخاب تست‌های مورد نظر
        if args.test:
            test_suite = load_specific_tests(args.test)
        else:
            test_suite = discover_tests(args.exclude, args.no_windows_tests)
        
        # تنظیم خروجی
        verbosity = args.verbose + 1
        if args.quiet:
            verbosity = 0
        
        # اجرای تست‌ها
        start_time = time.time()
        
        # بررسی آیا JUnit XML خروجی مورد نیاز است
        if args.junit_xml:
            try:
                import xmlrunner
                runner = xmlrunner.XMLTestRunner(output=os.path.dirname(args.junit_xml), 
                                               outsuffix=os.path.basename(args.junit_xml))
            except ImportError:
                logger.warning("کتابخانه xmlrunner یافت نشد. گزارش JUnit XML تولید نخواهد شد.")
                runner = unittest.TextTestRunner(verbosity=verbosity)
        else:
            runner = unittest.TextTestRunner(verbosity=verbosity)
        
        # اگر فایل خروجی مشخص شده باشد
        if args.output:
            os.makedirs(os.path.dirname(args.output), exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                # تغییر خروجی استاندارد به فایل
                original_stdout = sys.stdout
                sys.stdout = f
                
                test_result = runner.run(test_suite)
                
                # بازگرداندن خروجی استاندارد
                sys.stdout = original_stdout
        else:
            test_result = runner.run(test_suite)
        
        end_time = time.time()
        
        # نمایش خلاصه نتایج
        run_time = end_time - start_time
        print(f"\nزمان اجرا: {run_time:.2f} ثانیه")
        print(f"تست‌های موفق: {test_result.testsRun - len(test_result.errors) - len(test_result.failures)}")
        print(f"تست‌های ناموفق: {len(test_result.failures)}")
        print(f"خطاها: {len(test_result.errors)}")
        
        # تولید گزارش پوشش کد
        if cov:
            save_coverage_report(cov, args.coverage_html)
        
        # تعیین کد خروجی
        return 0 if len(test_result.failures) == 0 and len(test_result.errors) == 0 else 1
    
    except Exception as e:
        logger.error(f"خطا در اجرای تست‌ها: {str(e)}")
        return 1
    
    finally:
        # اطمینان از پایان coverage
        if cov:
            cov.stop()


def main() -> None:
    """
    تابع اصلی
    """
    args = parse_arguments()
    exit_code = run_tests(args)
    sys.exit(exit_code)


if __name__ == '__main__':
    main() 