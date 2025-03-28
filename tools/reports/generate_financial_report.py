#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
اسکریپت تولید گزارش مالی

این اسکریپت برای تولید گزارش‌های تحلیلی مالی از عملکرد ربات تلگرام طراحی شده است.
قابلیت‌های اصلی:
- تولید گزارش درآمد (روزانه، ماهانه، سالانه)
- تولید گزارش هزینه‌ها
- تولید گزارش سود و زیان
- تولید گزارش تراکنش‌ها
- تولید گزارش درآمد بر اساس نوع اشتراک
- تولید گزارش پرداخت‌های ناموفق
- تولید گزارش تبدیل ارز
- خروجی به فرمت‌های مختلف (JSON، CSV، Excel)
"""

import os
import sys
import argparse
import logging
import datetime
from src.utils.timezone_utils import get_current_datetime
import sqlite3
import json
import csv
import shutil
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set, Union
from collections import defaultdict

# افزودن مسیر ریشه پروژه به sys.path برای واردسازی ماژول‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.config import Config
from src.utils.timezone_utils import get_current_datetime
from src.utils.chart_generator import ChartGenerator
from src.accounting.currency_converter import CurrencyConverter

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
        description='تولید گزارش‌های تحلیلی مالی از عملکرد ربات تلگرام'
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
        '--output-dir',
        default='data/reports/financial_reports',
        help='مسیر دایرکتوری خروجی گزارش‌ها (پیش‌فرض: data/reports/financial_reports)'
    )
    
    parser.add_argument(
        '--format',
        choices=['json', 'csv', 'excel', 'all'],
        default='all',
        help='فرمت خروجی گزارش (پیش‌فرض: all)'
    )
    
    parser.add_argument(
        '--report-type',
        choices=[
            'revenue', 'expense', 'profit', 'transactions', 
            'subscription', 'failed_payments', 'currency', 'all'
        ],
        default='all',
        help='نوع گزارش (پیش‌فرض: all)'
    )
    
    parser.add_argument(
        '--period',
        choices=['day', 'week', 'month', 'year', 'all'],
        default='month',
        help='دوره زمانی گزارش (پیش‌فرض: month)'
    )
    
    parser.add_argument(
        '--start-date',
        default=None,
        help='تاریخ شروع گزارش (فرمت: YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--end-date',
        default=None,
        help='تاریخ پایان گزارش (فرمت: YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--group-by',
        choices=['day', 'week', 'month', 'year', 'subscription_type', 'payment_method', 'currency'],
        default='day',
        help='گروه‌بندی نتایج (پیش‌فرض: day)'
    )
    
    parser.add_argument(
        '--base-currency',
        default='USD',
        help='ارز پایه برای تبدیل مبالغ (پیش‌فرض: USD)'
    )
    
    parser.add_argument(
        '--include-charts',
        action='store_true',
        help='تولید نمودارهای گرافیکی'
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


def get_date_range(
    period: str, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
) -> Tuple[datetime.datetime, datetime.datetime]:
    """
    ÙØ­Ø§Ø³Ø¨Ù ÙØ­Ø¯ÙØ¯Ù ØªØ§Ø±ÛØ® Ú¯Ø²Ø§Ø±Ø´
    
    :param period: Ø¯ÙØ±Ù Ø²ÙØ§ÙÛ (day, week, month, year, all)
    :param start_date: ØªØ§Ø±ÛØ® Ø´Ø±ÙØ¹ (Ø§Ø®ØªÛØ§Ø±Û)
    :param end_date: ØªØ§Ø±ÛØ® Ù¾Ø§ÛØ§Ù (Ø§Ø®ØªÛØ§Ø±Û)
    :return: (ØªØ§Ø±ÛØ® Ø´Ø±ÙØ¹, ØªØ§Ø±ÛØ® Ù¾Ø§ÛØ§Ù)
    """
    # ØªØ§Ø±ÛØ® Ù¾Ø§ÛØ§Ù (Ø§ÙØ±ÙØ²)
    if end_date:
        end_datetime = datetime.datetime.strptime(end_date, '%Y-%m-%d')
    else:
        end_datetime = get_current_datetime().replace(hour=23, minute=59, second=59)
    
    # تاریخ شروع (بر اساس دوره)
    if start_date:
        start_datetime = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    elif period == 'day':
        start_datetime = end_datetime.replace(hour=0, minute=0, second=0)
    elif period == 'week':
        start_datetime = end_datetime - datetime.timedelta(days=7)
    elif period == 'month':
        if end_datetime.month == 1:
            start_datetime = end_datetime.replace(year=end_datetime.year-1, month=12, day=1, hour=0, minute=0, second=0)
        else:
            start_datetime = end_datetime.replace(month=end_datetime.month-1, day=1, hour=0, minute=0, second=0)
    elif period == 'year':
        start_datetime = end_datetime.replace(year=end_datetime.year-1, hour=0, minute=0, second=0)
    else:  # 'all'
        start_datetime = datetime.datetime(2000, 1, 1)
    
    return start_datetime, end_datetime


def generate_revenue_report(
    conn: sqlite3.Connection,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    group_by: str = 'day',
    base_currency: str = 'USD',
    verbose: bool = False
) -> Dict[str, Any]:
    """
    تولید گزارش درآمد
    
    :param conn: اتصال به پایگاه داده
    :param start_date: تاریخ شروع گزارش
    :param end_date: تاریخ پایان گزارش
    :param group_by: نحوه گروه‌بندی نتایج (day, week, month, year, subscription_type, payment_method, currency)
    :param base_currency: ارز پایه برای تبدیل مبالغ
    :param verbose: نمایش اطلاعات بیشتر
    :return: داده‌های گزارش
    """
    try:
        if verbose:
            logger.info(f"تولید گزارش درآمد از {start_date} تا {end_date} (گروه‌بندی: {group_by})")
        
        cursor = conn.cursor()
        
        # تبدیل تاریخ‌ها به رشته برای استفاده در کوئری SQL
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        # بررسی وجود جدول transactions
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
        if not cursor.fetchone():
            logger.warning("جدول transactions در پایگاه داده وجود ندارد")
            return {
                'status': 'warning',
                'message': 'جدول transactions در پایگاه داده وجود ندارد'
            }
        
        # تعیین نحوه گروه‌بندی بر اساس زمان
        time_group = None
        if group_by == 'day':
            time_group = "strftime('%Y-%m-%d', timestamp)"
        elif group_by == 'week':
            time_group = "strftime('%Y-%W', timestamp)"
        elif group_by == 'month':
            time_group = "strftime('%Y-%m', timestamp)"
        elif group_by == 'year':
            time_group = "strftime('%Y', timestamp)"
        
        # کوئری اصلی برای دریافت درآمدها
        if group_by in ['day', 'week', 'month', 'year']:
            # گروه‌بندی بر اساس زمان
            cursor.execute(f"""
                SELECT 
                    {time_group} as time_period,
                    SUM(amount) as total_amount,
                    currency,
                    COUNT(*) as transaction_count
                FROM transactions
                WHERE timestamp BETWEEN ? AND ? AND status = 'completed'
                GROUP BY time_period, currency
                ORDER BY time_period, currency
            """, (start_date_str, end_date_str))
        
        elif group_by == 'subscription_type':
            # گروه‌بندی بر اساس نوع اشتراک
            cursor.execute("""
                SELECT 
                    subscription_type as group_key,
                    SUM(amount) as total_amount,
                    currency,
                    COUNT(*) as transaction_count
                FROM transactions
                WHERE timestamp BETWEEN ? AND ? AND status = 'completed'
                GROUP BY subscription_type, currency
                ORDER BY subscription_type, currency
            """, (start_date_str, end_date_str))
        
        elif group_by == 'payment_method':
            # گروه‌بندی بر اساس روش پرداخت
            cursor.execute("""
                SELECT 
                    payment_method as group_key,
                    SUM(amount) as total_amount,
                    currency,
                    COUNT(*) as transaction_count
                FROM transactions
                WHERE timestamp BETWEEN ? AND ? AND status = 'completed'
                GROUP BY payment_method, currency
                ORDER BY payment_method, currency
            """, (start_date_str, end_date_str))
        
        elif group_by == 'currency':
            # گروه‌بندی بر اساس ارز
            cursor.execute("""
                SELECT 
                    currency as group_key,
                    SUM(amount) as total_amount,
                    currency,
                    COUNT(*) as transaction_count
                FROM transactions
                WHERE timestamp BETWEEN ? AND ? AND status = 'completed'
                GROUP BY currency
                ORDER BY currency
            """, (start_date_str, end_date_str))
        
        # دریافت نتایج
        raw_results = [dict(row) for row in cursor.fetchall()]
        
        # تبدیل ارزها به ارز پایه
        currency_converter = CurrencyConverter()
        
        revenues = []
        total_in_base = 0
        
        for row in raw_results:
            currency = row['currency']
            amount = float(row['total_amount']) if row['total_amount'] else 0
            
            # تبدیل به ارز پایه
            amount_in_base = amount
            if currency != base_currency:
                amount_in_base = currency_converter.convert(amount, currency, base_currency)
            
            total_in_base += amount_in_base
            
            # اضافه کردن به لیست درآمدها
            entry = dict(row)
            entry['total_amount_original'] = amount
            entry['total_amount_base'] = amount_in_base
            entry['base_currency'] = base_currency
            
            revenues.append(entry)
        
        # محاسبه آمار کلی
        total_transactions = sum(r['transaction_count'] for r in revenues)
        avg_transaction_value = total_in_base / max(1, total_transactions)
        
        # دریافت درآمد دوره قبل برای مقایسه
        previous_period_start = start_date - (end_date - start_date)
        previous_period_end = start_date
        
        cursor.execute("""
            SELECT 
                SUM(amount) as total_amount,
                currency
            FROM transactions
            WHERE timestamp BETWEEN ? AND ? AND status = 'completed'
            GROUP BY currency
        """, (previous_period_start.isoformat(), previous_period_end.isoformat()))
        
        previous_revenues = [dict(row) for row in cursor.fetchall()]
        
        # تبدیل درآمد دوره قبل به ارز پایه
        previous_total_in_base = 0
        
        for row in previous_revenues:
            currency = row['currency']
            amount = float(row['total_amount']) if row['total_amount'] else 0
            
            # تبدیل به ارز پایه
            amount_in_base = amount
            if currency != base_currency:
                amount_in_base = currency_converter.convert(amount, currency, base_currency)
            
            previous_total_in_base += amount_in_base
        
        # محاسبه نرخ رشد
        growth_rate = 0
        if previous_total_in_base > 0:
            growth_rate = ((total_in_base - previous_total_in_base) / previous_total_in_base) * 100
        
        # ساخت گزارش نهایی
        report = {
            'status': 'success',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_revenue': round(total_in_base, 2),
                'base_currency': base_currency,
                'total_transactions': total_transactions,
                'avg_transaction_value': round(avg_transaction_value, 2),
                'previous_period_revenue': round(previous_total_in_base, 2),
                'growth_rate': round(growth_rate, 2)
            },
            'group_by': group_by,
            'revenues': revenues
        }
        
        return report
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پایگاه داده: {str(e)}")
        return {
            'status': 'error',
            'message': f"خطا در پایگاه داده: {str(e)}"
        }
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش درآمد: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


def generate_expense_report(
    conn: sqlite3.Connection,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    group_by: str = 'day',
    base_currency: str = 'USD',
    verbose: bool = False
) -> Dict[str, Any]:
    """
    تولید گزارش هزینه‌ها
    
    :param conn: اتصال به پایگاه داده
    :param start_date: تاریخ شروع گزارش
    :param end_date: تاریخ پایان گزارش
    :param group_by: نحوه گروه‌بندی نتایج (day, week, month, year, category)
    :param base_currency: ارز پایه برای تبدیل مبالغ
    :param verbose: نمایش اطلاعات بیشتر
    :return: داده‌های گزارش
    """
    try:
        if verbose:
            logger.info(f"تولید گزارش هزینه‌ها از {start_date} تا {end_date} (گروه‌بندی: {group_by})")
        
        cursor = conn.cursor()
        
        # تبدیل تاریخ‌ها به رشته برای استفاده در کوئری SQL
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        # بررسی وجود جدول expenses
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='expenses'")
        if not cursor.fetchone():
            logger.warning("جدول expenses در پایگاه داده وجود ندارد")
            
            # تلاش برای جستجو در جدول transactions با تراکنش‌های خروجی
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
            if not cursor.fetchone():
                return {
                    'status': 'warning',
                    'message': 'جدول expenses یا transactions در پایگاه داده وجود ندارد'
                }
            
            # استفاده از جدول transactions برای هزینه‌ها
            use_transactions = True
        else:
            use_transactions = False
        
        # تعیین نحوه گروه‌بندی بر اساس زمان
        time_group = None
        if group_by == 'day':
            time_group = "strftime('%Y-%m-%d', timestamp)"
        elif group_by == 'week':
            time_group = "strftime('%Y-%W', timestamp)"
        elif group_by == 'month':
            time_group = "strftime('%Y-%m', timestamp)"
        elif group_by == 'year':
            time_group = "strftime('%Y', timestamp)"
        
        # کوئری اصلی برای دریافت هزینه‌ها
        if use_transactions:
            # استفاده از جدول transactions
            if group_by in ['day', 'week', 'month', 'year']:
                # گروه‌بندی بر اساس زمان
                cursor.execute(f"""
                    SELECT 
                        {time_group} as time_period,
                        SUM(amount) as total_amount,
                        currency,
                        COUNT(*) as transaction_count
                    FROM transactions
                    WHERE timestamp BETWEEN ? AND ? AND transaction_type = 'expense'
                    GROUP BY time_period, currency
                    ORDER BY time_period, currency
                """, (start_date_str, end_date_str))
            
            elif group_by == 'category':
                # گروه‌بندی بر اساس دسته‌بندی
                cursor.execute("""
                    SELECT 
                        COALESCE(category, 'unknown') as group_key,
                        SUM(amount) as total_amount,
                        currency,
                        COUNT(*) as transaction_count
                    FROM transactions
                    WHERE timestamp BETWEEN ? AND ? AND transaction_type = 'expense'
                    GROUP BY category, currency
                    ORDER BY category, currency
                """, (start_date_str, end_date_str))
        
        else:
            # استفاده از جدول expenses
            if group_by in ['day', 'week', 'month', 'year']:
                # بررسی وجود ستون timestamp در جدول expenses
                cursor.execute("PRAGMA table_info(expenses)")
                columns = [row[1] for row in cursor.fetchall()]
                
                timestamp_column = 'timestamp'
                if 'timestamp' not in columns:
                    if 'date' in columns:
                        timestamp_column = 'date'
                    else:
                        timestamp_column = 'created_at'
                
                # گروه‌بندی بر اساس زمان
                cursor.execute(f"""
                    SELECT 
                        strftime('%Y-%m-%d', {timestamp_column}) as time_period,
                        SUM(amount) as total_amount,
                        currency,
                        COUNT(*) as transaction_count
                    FROM expenses
                    WHERE {timestamp_column} BETWEEN ? AND ?
                    GROUP BY time_period, currency
                    ORDER BY time_period, currency
                """, (start_date_str, end_date_str))
            
            elif group_by == 'category':
                # گروه‌بندی بر اساس دسته‌بندی
                cursor.execute("""
                    SELECT 
                        COALESCE(category, 'unknown') as group_key,
                        SUM(amount) as total_amount,
                        currency,
                        COUNT(*) as transaction_count
                    FROM expenses
                    WHERE timestamp BETWEEN ? AND ?
                    GROUP BY category, currency
                    ORDER BY category, currency
                """, (start_date_str, end_date_str))
        
        # دریافت نتایج
        raw_results = [dict(row) for row in cursor.fetchall()]
        
        # تبدیل ارزها به ارز پایه
        currency_converter = CurrencyConverter()
        
        expenses = []
        total_in_base = 0
        
        for row in raw_results:
            currency = row['currency']
            amount = float(row['total_amount']) if row['total_amount'] else 0
            
            # تبدیل به ارز پایه
            amount_in_base = amount
            if currency != base_currency:
                amount_in_base = currency_converter.convert(amount, currency, base_currency)
            
            total_in_base += amount_in_base
            
            # اضافه کردن به لیست هزینه‌ها
            entry = dict(row)
            entry['total_amount_original'] = amount
            entry['total_amount_base'] = amount_in_base
            entry['base_currency'] = base_currency
            
            expenses.append(entry)
        
        # محاسبه آمار کلی
        total_transactions = sum(r['transaction_count'] for r in expenses)
        avg_transaction_value = total_in_base / max(1, total_transactions)
        
        # ساخت گزارش نهایی
        report = {
            'status': 'success',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_expense': round(total_in_base, 2),
                'base_currency': base_currency,
                'total_transactions': total_transactions,
                'avg_transaction_value': round(avg_transaction_value, 2)
            },
            'group_by': group_by,
            'expenses': expenses
        }
        
        return report
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پایگاه داده: {str(e)}")
        return {
            'status': 'error',
            'message': f"خطا در پایگاه داده: {str(e)}"
        }
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش هزینه‌ها: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


def generate_profit_report(
    conn: sqlite3.Connection,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    group_by: str = 'month',
    base_currency: str = 'USD',
    verbose: bool = False
) -> Dict[str, Any]:
    """
    تولید گزارش سود و زیان
    
    :param conn: اتصال به پایگاه داده
    :param start_date: تاریخ شروع گزارش
    :param end_date: تاریخ پایان گزارش
    :param group_by: نحوه گروه‌بندی نتایج (day, week, month, year)
    :param base_currency: ارز پایه برای تبدیل مبالغ
    :param verbose: نمایش اطلاعات بیشتر
    :return: داده‌های گزارش
    """
    try:
        if verbose:
            logger.info(f"تولید گزارش سود و زیان از {start_date} تا {end_date} (گروه‌بندی: {group_by})")
        
        # ابتدا گزارش درآمد را دریافت می‌کنیم
        revenue_report = generate_revenue_report(
            conn, start_date, end_date, group_by, base_currency, verbose=False
        )
        
        # سپس گزارش هزینه‌ها را دریافت می‌کنیم
        expense_report = generate_expense_report(
            conn, start_date, end_date, group_by, base_currency, verbose=False
        )
        
        # بررسی خطاها
        if revenue_report.get('status') == 'error':
            return revenue_report
        
        if expense_report.get('status') == 'error':
            return expense_report
        
        # محاسبه سود کلی
        total_revenue = revenue_report.get('summary', {}).get('total_revenue', 0)
        total_expense = expense_report.get('summary', {}).get('total_expense', 0)
        total_profit = total_revenue - total_expense
        
        # محاسبه حاشیه سود
        profit_margin = 0
        if total_revenue > 0:
            profit_margin = (total_profit / total_revenue) * 100
        
        # ترکیب داده‌های درآمد و هزینه بر اساس گروه‌بندی
        profits = []
        
        # ساختن دیکشنری برای درآمدها
        revenue_by_period = {}
        for item in revenue_report.get('revenues', []):
            key = None
            if group_by in ['day', 'week', 'month', 'year']:
                key = item.get('time_period')
            else:
                key = item.get('group_key')
            
            if key not in revenue_by_period:
                revenue_by_period[key] = 0
            
            revenue_by_period[key] += item.get('total_amount_base', 0)
        
        # ساختن دیکشنری برای هزینه‌ها
        expense_by_period = {}
        for item in expense_report.get('expenses', []):
            key = None
            if group_by in ['day', 'week', 'month', 'year']:
                key = item.get('time_period')
            else:
                key = item.get('group_key')
            
            if key not in expense_by_period:
                expense_by_period[key] = 0
            
            expense_by_period[key] += item.get('total_amount_base', 0)
        
        # ترکیب داده‌ها
        all_periods = set(revenue_by_period.keys()) | set(expense_by_period.keys())
        
        for period in sorted(all_periods):
            revenue = revenue_by_period.get(period, 0)
            expense = expense_by_period.get(period, 0)
            profit = revenue - expense
            
            profit_margin_period = 0
            if revenue > 0:
                profit_margin_period = (profit / revenue) * 100
            
            profits.append({
                'period': period,
                'revenue': round(revenue, 2),
                'expense': round(expense, 2),
                'profit': round(profit, 2),
                'profit_margin': round(profit_margin_period, 2),
                'base_currency': base_currency
            })
        
        # ساخت گزارش نهایی
        report = {
            'status': 'success',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_revenue': round(total_revenue, 2),
                'total_expense': round(total_expense, 2),
                'total_profit': round(total_profit, 2),
                'profit_margin': round(profit_margin, 2),
                'base_currency': base_currency
            },
            'group_by': group_by,
            'profits': profits
        }
        
        return report
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش سود و زیان: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


def generate_transactions_report(
    conn: sqlite3.Connection,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    base_currency: str = 'USD',
    verbose: bool = False
) -> Dict[str, Any]:
    """
    تولید گزارش تراکنش‌ها
    
    :param conn: اتصال به پایگاه داده
    :param start_date: تاریخ شروع گزارش
    :param end_date: تاریخ پایان گزارش
    :param base_currency: ارز پایه برای تبدیل مبالغ
    :param verbose: نمایش اطلاعات بیشتر
    :return: داده‌های گزارش
    """
    try:
        if verbose:
            logger.info(f"تولید گزارش تراکنش‌ها از {start_date} تا {end_date}")
        
        cursor = conn.cursor()
        
        # تبدیل تاریخ‌ها به رشته برای استفاده در کوئری SQL
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        # بررسی وجود جدول transactions
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
        if not cursor.fetchone():
            logger.warning("جدول transactions در پایگاه داده وجود ندارد")
            return {
                'status': 'warning',
                'message': 'جدول transactions در پایگاه داده وجود ندارد'
            }
        
        # آمار کلی تراکنش‌ها
        cursor.execute("""
            SELECT 
                COUNT(*) as total_count,
                COUNT(DISTINCT user_id) as unique_users
            FROM transactions
            WHERE timestamp BETWEEN ? AND ?
        """, (start_date_str, end_date_str))
        
        summary = dict(cursor.fetchone())
        
        # آمار تراکنش‌ها بر اساس وضعیت
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count,
                SUM(amount) as total_amount,
                currency
            FROM transactions
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY status, currency
            ORDER BY status, currency
        """, (start_date_str, end_date_str))
        
        status_stats_raw = [dict(row) for row in cursor.fetchall()]
        
        # تبدیل ارزها به ارز پایه
        currency_converter = CurrencyConverter()
        
        status_stats = []
        for row in status_stats_raw:
            currency = row['currency']
            amount = float(row['total_amount']) if row['total_amount'] else 0
            
            # تبدیل به ارز پایه
            amount_in_base = amount
            if currency != base_currency:
                amount_in_base = currency_converter.convert(amount, currency, base_currency)
            
            entry = dict(row)
            entry['total_amount_original'] = amount
            entry['total_amount_base'] = amount_in_base
            entry['base_currency'] = base_currency
            
            status_stats.append(entry)
        
        # آمار تراکنش‌ها بر اساس روش پرداخت
        cursor.execute("""
            SELECT 
                payment_method,
                COUNT(*) as count,
                SUM(amount) as total_amount,
                currency
            FROM transactions
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY payment_method, currency
            ORDER BY payment_method, currency
        """, (start_date_str, end_date_str))
        
        payment_methods_raw = [dict(row) for row in cursor.fetchall()]
        
        # تبدیل ارزها به ارز پایه
        payment_methods = []
        for row in payment_methods_raw:
            currency = row['currency']
            amount = float(row['total_amount']) if row['total_amount'] else 0
            
            # تبدیل به ارز پایه
            amount_in_base = amount
            if currency != base_currency:
                amount_in_base = currency_converter.convert(amount, currency, base_currency)
            
            entry = dict(row)
            entry['total_amount_original'] = amount
            entry['total_amount_base'] = amount_in_base
            entry['base_currency'] = base_currency
            
            payment_methods.append(entry)
        
        # روند تراکنش‌ها بر اساس روز
        cursor.execute("""
            SELECT 
                strftime('%Y-%m-%d', timestamp) as date,
                COUNT(*) as count,
                SUM(amount) as total_amount,
                currency
            FROM transactions
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY date, currency
            ORDER BY date, currency
        """, (start_date_str, end_date_str))
        
        daily_transactions_raw = [dict(row) for row in cursor.fetchall()]
        
        # ساماندهی داده‌ها برای روند روزانه
        daily_data = defaultdict(lambda: {'date': None, 'count': 0, 'total': 0})
        
        for row in daily_transactions_raw:
            date = row['date']
            count = row['count']
            amount = float(row['total_amount']) if row['total_amount'] else 0
            currency = row['currency']
            
            # تبدیل به ارز پایه
            amount_in_base = amount
            if currency != base_currency:
                amount_in_base = currency_converter.convert(amount, currency, base_currency)
            
            daily_data[date]['date'] = date
            daily_data[date]['count'] += count
            daily_data[date]['total'] += amount_in_base
        
        # تبدیل به لیست
        daily_transactions = [
            {
                'date': data['date'],
                'count': data['count'],
                'total_amount': round(data['total'], 2),
                'base_currency': base_currency
            }
            for data in daily_data.values()
        ]
        
        # مرتب‌سازی بر اساس تاریخ
        daily_transactions.sort(key=lambda x: x['date'])
        
        # محاسبه میانگین ارزش تراکنش
        avg_transaction_value = 0
        total_amount_base = sum(t['total_amount'] for t in daily_transactions)
        total_count = sum(t['count'] for t in daily_transactions)
        
        if total_count > 0:
            avg_transaction_value = total_amount_base / total_count
        
        # اضافه کردن اطلاعات آماری به خلاصه
        summary['total_amount_base'] = round(total_amount_base, 2)
        summary['avg_transaction_value'] = round(avg_transaction_value, 2)
        summary['base_currency'] = base_currency
        
        # ساخت گزارش نهایی
        report = {
            'status': 'success',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': summary,
            'status_stats': status_stats,
            'payment_methods': payment_methods,
            'daily_transactions': daily_transactions
        }
        
        return report
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پایگاه داده: {str(e)}")
        return {
            'status': 'error',
            'message': f"خطا در پایگاه داده: {str(e)}"
        }
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش تراکنش‌ها: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


def generate_subscription_revenue_report(
    conn: sqlite3.Connection,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    base_currency: str = 'USD',
    verbose: bool = False
) -> Dict[str, Any]:
    """
    تولید گزارش درآمد بر اساس نوع اشتراک
    
    :param conn: اتصال به پایگاه داده
    :param start_date: تاریخ شروع گزارش
    :param end_date: تاریخ پایان گزارش
    :param base_currency: ارز پایه برای تبدیل مبالغ
    :param verbose: نمایش اطلاعات بیشتر
    :return: داده‌های گزارش
    """
    try:
        if verbose:
            logger.info(f"تولید گزارش درآمد بر اساس نوع اشتراک از {start_date} تا {end_date}")
        
        cursor = conn.cursor()
        
        # تبدیل تاریخ‌ها به رشته برای استفاده در کوئری SQL
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        # بررسی وجود جدول subscriptions
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subscriptions'")
        if not cursor.fetchone():
            logger.warning("جدول subscriptions در پایگاه داده وجود ندارد")
            
            # در صورت عدم وجود جدول subscriptions، از جدول transactions استفاده می‌کنیم
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
            if not cursor.fetchone():
                return {
                    'status': 'warning',
                    'message': 'جدول subscriptions یا transactions در پایگاه داده وجود ندارد'
                }
            
            # استفاده از جدول transactions برای اطلاعات اشتراک‌ها
            cursor.execute("""
                SELECT 
                    subscription_type as plan_type,
                    COUNT(*) as subscription_count,
                    SUM(amount) as total_amount,
                    currency
                FROM transactions
                WHERE timestamp BETWEEN ? AND ? AND status = 'completed' AND transaction_type = 'subscription'
                GROUP BY subscription_type, currency
                ORDER BY total_amount DESC
            """, (start_date_str, end_date_str))
        else:
            # استفاده از جدول subscriptions
            cursor.execute("""
                SELECT 
                    s.plan_type,
                    COUNT(s.id) as subscription_count,
                    SUM(t.amount) as total_amount,
                    t.currency
                FROM subscriptions s
                JOIN transactions t ON s.transaction_id = t.id
                WHERE s.created_at BETWEEN ? AND ? AND t.status = 'completed'
                GROUP BY s.plan_type, t.currency
                ORDER BY total_amount DESC
            """, (start_date_str, end_date_str))
        
        # دریافت نتایج
        raw_results = [dict(row) for row in cursor.fetchall()]
        
        # تبدیل ارزها به ارز پایه
        currency_converter = CurrencyConverter()
        
        subscription_revenue = []
        total_in_base = 0
        
        for row in raw_results:
            currency = row['currency']
            amount = float(row['total_amount']) if row['total_amount'] else 0
            
            # تبدیل به ارز پایه
            amount_in_base = amount
            if currency != base_currency:
                amount_in_base = currency_converter.convert(amount, currency, base_currency)
            
            total_in_base += amount_in_base
            
            # اضافه کردن به لیست درآمدها
            entry = dict(row)
            entry['total_amount_original'] = amount
            entry['total_amount_base'] = amount_in_base
            entry['base_currency'] = base_currency
            
            subscription_revenue.append(entry)
        
        # محاسبه آمار کلی
        total_subscriptions = sum(r['subscription_count'] for r in subscription_revenue)
        avg_subscription_value = total_in_base / max(1, total_subscriptions)
        
        # محاسبه سهم هر نوع اشتراک از کل درآمد
        for entry in subscription_revenue:
            entry['revenue_share'] = round((entry['total_amount_base'] / max(1, total_in_base)) * 100, 2)
        
        # مرتب‌سازی بر اساس سهم درآمد
        subscription_revenue.sort(key=lambda x: x['revenue_share'], reverse=True)
        
        # روند ماهانه اشتراک‌ها
        cursor.execute("""
            SELECT 
                strftime('%Y-%m', created_at) as month,
                plan_type,
                COUNT(*) as count
            FROM subscriptions
            WHERE created_at BETWEEN ? AND ?
            GROUP BY month, plan_type
            ORDER BY month, plan_type
        """, (start_date_str, end_date_str))
        
        monthly_trends = [dict(row) for row in cursor.fetchall()]
        
        # ساخت گزارش نهایی
        report = {
            'status': 'success',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_revenue': round(total_in_base, 2),
                'base_currency': base_currency,
                'total_subscriptions': total_subscriptions,
                'avg_subscription_value': round(avg_subscription_value, 2)
            },
            'subscription_revenue': subscription_revenue,
            'monthly_trends': monthly_trends
        }
        
        return report
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پایگاه داده: {str(e)}")
        return {
            'status': 'error',
            'message': f"خطا در پایگاه داده: {str(e)}"
        }
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش درآمد اشتراک‌ها: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


def generate_failed_payments_report(
    conn: sqlite3.Connection,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    تولید گزارش پرداخت‌های ناموفق
    
    :param conn: اتصال به پایگاه داده
    :param start_date: تاریخ شروع گزارش
    :param end_date: تاریخ پایان گزارش
    :param verbose: نمایش اطلاعات بیشتر
    :return: داده‌های گزارش
    """
    try:
        if verbose:
            logger.info(f"تولید گزارش پرداخت‌های ناموفق از {start_date} تا {end_date}")
        
        cursor = conn.cursor()
        
        # تبدیل تاریخ‌ها به رشته برای استفاده در کوئری SQL
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        # بررسی وجود جدول transactions
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
        if not cursor.fetchone():
            logger.warning("جدول transactions در پایگاه داده وجود ندارد")
            return {
                'status': 'warning',
                'message': 'جدول transactions در پایگاه داده وجود ندارد'
            }
        
        # آمار کلی پرداخت‌های ناموفق
        cursor.execute("""
            SELECT 
                COUNT(*) as total_failed,
                COUNT(DISTINCT user_id) as unique_users,
                SUM(amount) as total_amount
            FROM transactions
            WHERE timestamp BETWEEN ? AND ? AND status IN ('failed', 'rejected', 'canceled')
        """, (start_date_str, end_date_str))
        
        summary = dict(cursor.fetchone())
        
        # آمار کل تراکنش‌ها
        cursor.execute("""
            SELECT COUNT(*) as total_transactions
            FROM transactions
            WHERE timestamp BETWEEN ? AND ?
        """, (start_date_str, end_date_str))
        
        total_transactions = cursor.fetchone()[0]
        
        # محاسبه نرخ شکست
        failure_rate = 0
        if total_transactions > 0:
            failure_rate = (summary['total_failed'] / total_transactions) * 100
        
        summary['total_transactions'] = total_transactions
        summary['failure_rate'] = round(failure_rate, 2)
        
        # آمار پرداخت‌های ناموفق بر اساس دلیل شکست
        cursor.execute("""
            SELECT 
                error_code,
                COUNT(*) as count,
                (COUNT(*) * 100.0 / ?) as percentage
            FROM transactions
            WHERE timestamp BETWEEN ? AND ? AND status IN ('failed', 'rejected', 'canceled')
            GROUP BY error_code
            ORDER BY count DESC
        """, (max(1, summary['total_failed']), start_date_str, end_date_str))
        
        failure_reasons = [dict(row) for row in cursor.fetchall()]
        
        # آمار پرداخت‌های ناموفق بر اساس روش پرداخت
        cursor.execute("""
            SELECT 
                payment_method,
                COUNT(*) as count,
                (COUNT(*) * 100.0 / ?) as percentage
            FROM transactions
            WHERE timestamp BETWEEN ? AND ? AND status IN ('failed', 'rejected', 'canceled')
            GROUP BY payment_method
            ORDER BY count DESC
        """, (max(1, summary['total_failed']), start_date_str, end_date_str))
        
        failed_by_method = [dict(row) for row in cursor.fetchall()]
        
        # روند روزانه پرداخت‌های ناموفق
        cursor.execute("""
            SELECT 
                strftime('%Y-%m-%d', timestamp) as date,
                COUNT(*) as count
            FROM transactions
            WHERE timestamp BETWEEN ? AND ? AND status IN ('failed', 'rejected', 'canceled')
            GROUP BY date
            ORDER BY date
        """, (start_date_str, end_date_str))
        
        daily_failures = [dict(row) for row in cursor.fetchall()]
        
        # کاربران با بیشترین پرداخت‌های ناموفق
        cursor.execute("""
            SELECT 
                user_id,
                COUNT(*) as failure_count
            FROM transactions
            WHERE timestamp BETWEEN ? AND ? AND status IN ('failed', 'rejected', 'canceled')
            GROUP BY user_id
            ORDER BY failure_count DESC
            LIMIT 10
        """, (start_date_str, end_date_str))
        
        top_failing_users = [dict(row) for row in cursor.fetchall()]
        
        # اضافه کردن اطلاعات کاربر
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone():
            for i, user in enumerate(top_failing_users):
                user_id = user['user_id']
                
                cursor.execute("""
                    SELECT username, first_name, last_name
                    FROM users
                    WHERE id = ?
                """, (user_id,))
                
                user_info = cursor.fetchone()
                if user_info:
                    top_failing_users[i]['username'] = user_info[0]
                    top_failing_users[i]['first_name'] = user_info[1]
                    top_failing_users[i]['last_name'] = user_info[2]
        
        # ساخت گزارش نهایی
        report = {
            'status': 'success',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': summary,
            'failure_reasons': failure_reasons,
            'failed_by_method': failed_by_method,
            'daily_failures': daily_failures,
            'top_failing_users': top_failing_users
        }
        
        return report
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پایگاه داده: {str(e)}")
        return {
            'status': 'error',
            'message': f"خطا در پایگاه داده: {str(e)}"
        }
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش پرداخت‌های ناموفق: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


def generate_currency_report(
    conn: sqlite3.Connection,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    base_currency: str = 'USD',
    verbose: bool = False
) -> Dict[str, Any]:
    """
    تولید گزارش تبدیل ارز
    
    :param conn: اتصال به پایگاه داده
    :param start_date: تاریخ شروع گزارش
    :param end_date: تاریخ پایان گزارش
    :param base_currency: ارز پایه برای تبدیل مبالغ
    :param verbose: نمایش اطلاعات بیشتر
    :return: داده‌های گزارش
    """
    try:
        if verbose:
            logger.info(f"تولید گزارش تبدیل ارز از {start_date} تا {end_date}")
        
        cursor = conn.cursor()
        
        # تبدیل تاریخ‌ها به رشته برای استفاده در کوئری SQL
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        # بررسی وجود جدول transactions
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
        if not cursor.fetchone():
            logger.warning("جدول transactions در پایگاه داده وجود ندارد")
            return {
                'status': 'warning',
                'message': 'جدول transactions در پایگاه داده وجود ندارد'
            }
        
        # آمار تراکنش‌ها بر اساس ارز
        cursor.execute("""
            SELECT 
                currency,
                COUNT(*) as transaction_count,
                SUM(amount) as total_amount
            FROM transactions
            WHERE timestamp BETWEEN ? AND ? AND status = 'completed'
            GROUP BY currency
            ORDER BY total_amount DESC
        """, (start_date_str, end_date_str))
        
        currency_stats_raw = [dict(row) for row in cursor.fetchall()]
        
        # تبدیل ارزها به ارز پایه
        currency_converter = CurrencyConverter()
        
        currency_stats = []
        total_in_base = 0
        
        for row in currency_stats_raw:
            currency = row['currency']
            amount = float(row['total_amount']) if row['total_amount'] else 0
            
            # تبدیل به ارز پایه
            amount_in_base = amount
            if currency != base_currency:
                amount_in_base = currency_converter.convert(amount, currency, base_currency)
            
            total_in_base += amount_in_base
            
            # دریافت نرخ تبدیل
            exchange_rate = 1.0
            if currency != base_currency:
                exchange_rate = currency_converter.get_rate(currency, base_currency)
            
            entry = dict(row)
            entry['total_amount_original'] = amount
            entry['total_amount_base'] = amount_in_base
            entry['base_currency'] = base_currency
            entry['exchange_rate'] = exchange_rate
            
            currency_stats.append(entry)
        
        # محاسبه سهم هر ارز از کل تراکنش‌ها
        for entry in currency_stats:
            entry['percentage'] = round((entry['total_amount_base'] / max(1, total_in_base)) * 100, 2)
        
        # دریافت نرخ‌های تبدیل فعلی
        current_rates = {}
        all_currencies = [row['currency'] for row in currency_stats]
        
        for currency in all_currencies:
            if currency != base_currency:
                rate = currency_converter.get_rate(currency, base_currency)
                current_rates[currency] = rate
        
        # بررسی روند نرخ‌های تبدیل (اگر در پایگاه داده نگهداری می‌شوند)
        exchange_rate_trends = []
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='exchange_rates'")
        if cursor.fetchone():
            for currency in all_currencies:
                if currency != base_currency:
                    cursor.execute("""
                        SELECT 
                            strftime('%Y-%m-%d', timestamp) as date,
                            rate
                        FROM exchange_rates
                        WHERE from_currency = ? AND to_currency = ? AND timestamp BETWEEN ? AND ?
                        GROUP BY date
                        ORDER BY date
                    """, (currency, base_currency, start_date_str, end_date_str))
                    
                    rate_trend = [dict(row) for row in cursor.fetchall()]
                    
                    if rate_trend:
                        exchange_rate_trends.append({
                            'currency': currency,
                            'base_currency': base_currency,
                            'rates': rate_trend
                        })
        
        # ساخت گزارش نهایی
        report = {
            'status': 'success',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_amount_base': round(total_in_base, 2),
                'base_currency': base_currency,
                'unique_currencies': len(currency_stats)
            },
            'currency_stats': currency_stats,
            'current_rates': current_rates,
            'exchange_rate_trends': exchange_rate_trends
        }
        
        return report
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پایگاه داده: {str(e)}")
        return {
            'status': 'error',
            'message': f"خطا در پایگاه داده: {str(e)}"
        }
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش تبدیل ارز: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


def generate_charts(report_data: Dict[str, Any], report_type: str, output_dir: str) -> Dict[str, str]:
    """
    تولید نمودارهای گرافیکی از داده‌های گزارش
    
    :param report_data: داده‌های گزارش
    :param report_type: نوع گزارش
    :param output_dir: مسیر دایرکتوری خروجی
    :return: مسیر فایل‌های نمودار
    """
    try:
        # مسیر دایرکتوری نمودارها
        charts_dir = os.path.join(output_dir, 'charts')
        os.makedirs(charts_dir, exist_ok=True)
        
        # تاریخ تولید گزارش
        timestamp = datetime.get_current_datetime().strftime('%Y%m%d_%H%M%S')
        
        # استفاده از ChartGenerator برای تولید نمودارها
        chart_generator = ChartGenerator()
        
        # مسیر فایل‌های نمودار
        chart_files = {}
        
        if report_type == 'revenue' or report_type == 'all':
            if report_data.get('status') == 'success' and 'revenues' in report_data:
                revenues = report_data['revenues']
                group_by = report_data.get('group_by', 'day')
                
                # گروه‌بندی و جمع‌آوری داده‌ها بر اساس نوع گروه‌بندی
                if group_by in ['day', 'week', 'month', 'year']:
                    # داده‌های سری زمانی
                    data_by_period = {}
                    
                    for rev in revenues:
                        period = rev.get('time_period', '')
                        amount = rev.get('total_amount_base', 0)
                        
                        if period not in data_by_period:
                            data_by_period[period] = 0
                        
                        data_by_period[period] += amount
                    
                    periods = sorted(data_by_period.keys())
                    amounts = [data_by_period[p] for p in periods]
                    
                    if periods and amounts:
                        # نمودار روند درآمد
                        chart_path = os.path.join(charts_dir, f'revenue_trend_{timestamp}.png')
                        chart_generator.create_line_chart(
                            periods, amounts, 
                            f'روند درآمد ({group_by})', 
                            'زمان', f'مبلغ ({report_data["summary"]["base_currency"]})',
                            chart_path
                        )
                        
                        chart_files['revenue_trend'] = chart_path
                
                elif group_by in ['subscription_type', 'payment_method', 'currency']:
                    # داده‌های دسته‌بندی
                    data_by_group = {}
                    
                    for rev in revenues:
                        group = rev.get('group_key', '')
                        amount = rev.get('total_amount_base', 0)
                        
                        if group not in data_by_group:
                            data_by_group[group] = 0
                        
                        data_by_group[group] += amount
                    
                    # مرتب‌سازی بر اساس مبلغ (نزولی)
                    sorted_groups = sorted(data_by_group.items(), key=lambda x: x[1], reverse=True)
                    groups = [g[0] for g in sorted_groups]
                    amounts = [g[1] for g in sorted_groups]
                    
                    if groups and amounts:
                        # نمودار نسبت درآمد بر اساس گروه
                        chart_path = os.path.join(charts_dir, f'revenue_by_{group_by}_{timestamp}.png')
                        chart_generator.create_pie_chart(
                            groups, amounts, 
                            f'درآمد بر اساس {group_by}', 
                            chart_path
                        )
                        
                        chart_files[f'revenue_by_{group_by}'] = chart_path
        
        if report_type == 'expense' or report_type == 'all':
            if report_data.get('status') == 'success' and 'expenses' in report_data:
                expenses = report_data['expenses']
                group_by = report_data.get('group_by', 'day')
                
                # گروه‌بندی و جمع‌آوری داده‌ها بر اساس نوع گروه‌بندی
                if group_by in ['day', 'week', 'month', 'year']:
                    # داده‌های سری زمانی
                    data_by_period = {}
                    
                    for exp in expenses:
                        period = exp.get('time_period', '')
                        amount = exp.get('total_amount_base', 0)
                        
                        if period not in data_by_period:
                            data_by_period[period] = 0
                        
                        data_by_period[period] += amount
                    
                    periods = sorted(data_by_period.keys())
                    amounts = [data_by_period[p] for p in periods]
                    
                    if periods and amounts:
                        # نمودار روند هزینه‌ها
                        chart_path = os.path.join(charts_dir, f'expense_trend_{timestamp}.png')
                        chart_generator.create_line_chart(
                            periods, amounts, 
                            f'روند هزینه‌ها ({group_by})', 
                            'زمان', f'مبلغ ({report_data["summary"]["base_currency"]})',
                            chart_path
                        )
                        
                        chart_files['expense_trend'] = chart_path
                
                elif group_by == 'category':
                    # داده‌های دسته‌بندی
                    data_by_category = {}
                    
                    for exp in expenses:
                        category = exp.get('group_key', 'نامشخص')
                        amount = exp.get('total_amount_base', 0)
                        
                        if category not in data_by_category:
                            data_by_category[category] = 0
                        
                        data_by_category[category] += amount
                    
                    # مرتب‌سازی بر اساس مبلغ (نزولی)
                    sorted_categories = sorted(data_by_category.items(), key=lambda x: x[1], reverse=True)
                    categories = [c[0] for c in sorted_categories]
                    amounts = [c[1] for c in sorted_categories]
                    
                    if categories and amounts:
                        # نمودار نسبت هزینه‌ها بر اساس دسته‌بندی
                        chart_path = os.path.join(charts_dir, f'expense_by_category_{timestamp}.png')
                        chart_generator.create_pie_chart(
                            categories, amounts, 
                            'هزینه‌ها بر اساس دسته‌بندی', 
                            chart_path
                        )
                        
                        chart_files['expense_by_category'] = chart_path
        
        if report_type == 'profit' or report_type == 'all':
            if report_data.get('status') == 'success' and 'profits' in report_data:
                profits = report_data['profits']
                group_by = report_data.get('group_by', 'month')
                
                if profits:
                    # داده‌های سری زمانی برای درآمد، هزینه و سود
                    periods = [p['period'] for p in profits]
                    revenues = [p['revenue'] for p in profits]
                    expenses = [p['expense'] for p in profits]
                    profits_data = [p['profit'] for p in profits]
                    
                    # نمودار روند درآمد، هزینه و سود
                    chart_path = os.path.join(charts_dir, f'profit_trend_{timestamp}.png')
                    
                    plt.figure(figsize=(12, 6))
                    plt.plot(periods, revenues, marker='o', label='درآمد')
                    plt.plot(periods, expenses, marker='s', label='هزینه')
                    plt.plot(periods, profits_data, marker='^', label='سود')
                    plt.title(f'روند درآمد، هزینه و سود ({group_by})')
                    plt.xlabel('زمان')
                    plt.ylabel(f'مبلغ ({report_data["summary"]["base_currency"]})')
                    plt.grid(True, linestyle='--', alpha=0.7)
                    plt.legend()
                    
                    # چرخش برچسب‌های محور X برای خوانایی بهتر
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    
                    plt.savefig(chart_path)
                    plt.close()
                    
                    chart_files['profit_trend'] = chart_path
                    
                    # نمودار حاشیه سود
                    margins = [p['profit_margin'] for p in profits]
                    
                    chart_path = os.path.join(charts_dir, f'profit_margin_trend_{timestamp}.png')
                    chart_generator.create_line_chart(
                        periods, margins, 
                        f'روند حاشیه سود ({group_by})', 
                        'زمان', 'حاشیه سود (%)',
                        chart_path
                    )
                    
                    chart_files['profit_margin_trend'] = chart_path
        
        if report_type == 'transactions' or report_type == 'all':
            if report_data.get('status') == 'success':
                # نمودار روند تراکنش‌های روزانه
                daily_transactions = report_data.get('daily_transactions', [])
                if daily_transactions:
                    dates = [t['date'] for t in daily_transactions]
                    counts = [t['count'] for t in daily_transactions]
                    amounts = [t['total_amount'] for t in daily_transactions]
                    
                    # نمودار تعداد تراکنش‌ها
                    chart_path = os.path.join(charts_dir, f'transaction_counts_{timestamp}.png')
                    chart_generator.create_line_chart(
                        dates, counts, 
                        'تعداد روزانه تراکنش‌ها', 
                        'تاریخ', 'تعداد تراکنش‌ها',
                        chart_path
                    )
                    
                    chart_files['transaction_counts'] = chart_path
                    
                    # نمودار مبلغ تراکنش‌ها
                    chart_path = os.path.join(charts_dir, f'transaction_amounts_{timestamp}.png')
                    chart_generator.create_line_chart(
                        dates, amounts, 
                        'مبلغ روزانه تراکنش‌ها', 
                        'تاریخ', f'مبلغ ({report_data["summary"]["base_currency"]})',
                        chart_path
                    )
                    
                    chart_files['transaction_amounts'] = chart_path
                
                # نمودار وضعیت تراکنش‌ها
                status_stats = report_data.get('status_stats', [])
                if status_stats:
                    # جمع‌آوری داده‌ها بر اساس وضعیت
                    status_data = {}
                    
                    for stat in status_stats:
                        status = stat['status']
                        amount = stat.get('total_amount_base', 0)
                        
                        if status not in status_data:
                            status_data[status] = 0
                        
                        status_data[status] += amount
                    
                    statuses = list(status_data.keys())
                    amounts = [status_data[s] for s in statuses]
                    
                    chart_path = os.path.join(charts_dir, f'transaction_by_status_{timestamp}.png')
                    chart_generator.create_pie_chart(
                        statuses, amounts, 
                        'تراکنش‌ها بر اساس وضعیت', 
                        chart_path
                    )
                    
                    chart_files['transaction_by_status'] = chart_path
                
                # نمودار روش‌های پرداخت
                payment_methods = report_data.get('payment_methods', [])
                if payment_methods:
                    # جمع‌آوری داده‌ها بر اساس روش پرداخت
                    method_data = {}
                    
                    for method in payment_methods:
                        name = method['payment_method']
                        amount = method.get('total_amount_base', 0)
                        
                        if name not in method_data:
                            method_data[name] = 0
                        
                        method_data[name] += amount
                    
                    # مرتب‌سازی بر اساس مبلغ (نزولی)
                    sorted_methods = sorted(method_data.items(), key=lambda x: x[1], reverse=True)
                    methods = [m[0] for m in sorted_methods]
                    amounts = [m[1] for m in sorted_methods]
                    
                    chart_path = os.path.join(charts_dir, f'transaction_by_method_{timestamp}.png')
                    chart_generator.create_pie_chart(
                        methods, amounts, 
                        'تراکنش‌ها بر اساس روش پرداخت', 
                        chart_path
                    )
                    
                    chart_files['transaction_by_method'] = chart_path
        
        if report_type == 'subscription' or report_type == 'all':
            if report_data.get('status') == 'success' and 'subscription_revenue' in report_data:
                subscription_revenue = report_data['subscription_revenue']
                
                if subscription_revenue:
                    # نمودار درآمد بر اساس نوع اشتراک
                    plan_types = [s['plan_type'] for s in subscription_revenue]
                    amounts = [s['total_amount_base'] for s in subscription_revenue]
                    
                    chart_path = os.path.join(charts_dir, f'revenue_by_plan_{timestamp}.png')
                    chart_generator.create_pie_chart(
                        plan_types, amounts, 
                        'درآمد بر اساس نوع اشتراک', 
                        chart_path
                    )
                    
                    chart_files['revenue_by_plan'] = chart_path
                
                # نمودار روند ماهانه اشتراک‌ها
                monthly_trends = report_data.get('monthly_trends', [])
                if monthly_trends:
                    # ساماندهی داده‌ها بر اساس ماه و نوع اشتراک
                    trend_data = {}
                    plan_types = set()
                    
                    for trend in monthly_trends:
                        month = trend['month']
                        plan = trend['plan_type']
                        count = trend['count']
                        
                        if month not in trend_data:
                            trend_data[month] = {}
                        
                        trend_data[month][plan] = count
                        plan_types.add(plan)
                    
                    # مرتب‌سازی ماه‌ها
                    months = sorted(trend_data.keys())
                    
                    # تبدیل به فرمت مناسب برای نمودار
                    plt.figure(figsize=(12, 6))
                    
                    for plan in sorted(plan_types):
                        counts = [trend_data[m].get(plan, 0) for m in months]
                        plt.plot(months, counts, marker='o', label=plan)
                    
                    plt.title('روند ماهانه اشتراک‌ها بر اساس نوع')
                    plt.xlabel('ماه')
                    plt.ylabel('تعداد اشتراک‌ها')
                    plt.grid(True, linestyle='--', alpha=0.7)
                    plt.legend()
                    
                    # چرخش برچسب‌های محور X برای خوانایی بهتر
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    
                    chart_path = os.path.join(charts_dir, f'subscription_monthly_trend_{timestamp}.png')
                    plt.savefig(chart_path)
                    plt.close()
                    
                    chart_files['subscription_monthly_trend'] = chart_path
        
        if report_type == 'failed_payments' or report_type == 'all':
            if report_data.get('status') == 'success':
                # نمودار روند روزانه پرداخت‌های ناموفق
                daily_failures = report_data.get('daily_failures', [])
                if daily_failures:
                    dates = [f['date'] for f in daily_failures]
                    counts = [f['count'] for f in daily_failures]
                    
                    chart_path = os.path.join(charts_dir, f'daily_failures_{timestamp}.png')
                    chart_generator.create_line_chart(
                        dates, counts, 
                        'روند روزانه پرداخت‌های ناموفق', 
                        'تاریخ', 'تعداد پرداخت‌های ناموفق',
                        chart_path
                    )
                    
                    chart_files['daily_failures'] = chart_path
                
                # نمودار دلایل شکست پرداخت
                failure_reasons = report_data.get('failure_reasons', [])
                if failure_reasons:
                    reasons = [f['error_code'] or 'نامشخص' for f in failure_reasons]
                    counts = [f['count'] for f in failure_reasons]
                    
                    chart_path = os.path.join(charts_dir, f'failure_reasons_{timestamp}.png')
                    chart_generator.create_pie_chart(
                        reasons, counts, 
                        'دلایل شکست پرداخت', 
                        chart_path
                    )
                    
                    chart_files['failure_reasons'] = chart_path
                
                # نمودار روش‌های پرداخت ناموفق
                failed_by_method = report_data.get('failed_by_method', [])
                if failed_by_method:
                    methods = [f['payment_method'] for f in failed_by_method]
                    counts = [f['count'] for f in failed_by_method]
                    
                    chart_path = os.path.join(charts_dir, f'failed_by_method_{timestamp}.png')
                    chart_generator.create_pie_chart(
                        methods, counts, 
                        'پرداخت‌های ناموفق بر اساس روش پرداخت', 
                        chart_path
                    )
                    
                    chart_files['failed_by_method'] = chart_path
        
        if report_type == 'currency' or report_type == 'all':
            if report_data.get('status') == 'success' and 'currency_stats' in report_data:
                currency_stats = report_data['currency_stats']
                
                if currency_stats:
                    # نمودار توزیع ارزها
                    currencies = [c['currency'] for c in currency_stats]
                    amounts = [c['total_amount_base'] for c in currency_stats]
                    
                    chart_path = os.path.join(charts_dir, f'currency_distribution_{timestamp}.png')
                    chart_generator.create_pie_chart(
                        currencies, amounts, 
                        'توزیع ارزها در تراکنش‌ها', 
                        chart_path
                    )
                    
                    chart_files['currency_distribution'] = chart_path
                
                # نمودار روند نرخ‌های تبدیل
                exchange_rate_trends = report_data.get('exchange_rate_trends', [])
                if exchange_rate_trends:
                    for trend in exchange_rate_trends:
                        currency = trend['currency']
                        base_currency = trend['base_currency']
                        rates = trend['rates']
                        
                        dates = [r['date'] for r in rates]
                        rate_values = [r['rate'] for r in rates]
                        
                        chart_path = os.path.join(charts_dir, f'exchange_rate_{currency}_{base_currency}_{timestamp}.png')
                        chart_generator.create_line_chart(
                            dates, rate_values, 
                            f'روند نرخ تبدیل {currency} به {base_currency}', 
                            'تاریخ', 'نرخ تبدیل',
                            chart_path
                        )
                        
                        chart_files[f'exchange_rate_{currency}_{base_currency}'] = chart_path
        
        return chart_files
    
    except Exception as e:
        logger.error(f"خطا در تولید نمودارها: {str(e)}")
        return {}


def save_report(
    report_data: Dict[str, Any],
    output_format: str,
    output_dir: str,
    report_type: str
) -> Dict[str, str]:
    """
    ذخیره گزارش در فرمت‌های مختلف
    
    :param report_data: داده‌های گزارش
    :param output_format: فرمت خروجی (json, csv, excel, all)
    :param output_dir: مسیر دایرکتوری خروجی
    :param report_type: نوع گزارش
    :return: مسیر فایل‌های خروجی
    """
    try:
        # ایجاد دایرکتوری خروجی
        os.makedirs(output_dir, exist_ok=True)
        
        # تاریخ تولید گزارش
        timestamp = datetime.get_current_datetime().strftime('%Y%m%d_%H%M%S')
        
        # مسیر فایل‌های خروجی
        output_files = {}
        
        # ذخیره به فرمت JSON
        if output_format in ['json', 'all']:
            json_path = os.path.join(output_dir, f'{report_type}_report_{timestamp}.json')
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            output_files['json'] = json_path
            logger.info(f"گزارش JSON در {json_path} ذخیره شد")
        
        # ذخیره به فرمت CSV
        if output_format in ['csv', 'all']:
            # تعیین داده‌های اصلی برای ذخیره در CSV (بر اساس نوع گزارش)
            csv_data = None
            
            if report_type == 'revenue':
                csv_data = report_data.get('revenues', [])
                csv_path = os.path.join(output_dir, f'revenue_report_{timestamp}.csv')
            
            elif report_type == 'expense':
                csv_data = report_data.get('expenses', [])
                csv_path = os.path.join(output_dir, f'expense_report_{timestamp}.csv')
            
            elif report_type == 'profit':
                csv_data = report_data.get('profits', [])
                csv_path = os.path.join(output_dir, f'profit_report_{timestamp}.csv')
            
            elif report_type == 'transactions':
                csv_data = report_data.get('daily_transactions', [])
                csv_path = os.path.join(output_dir, f'transactions_report_{timestamp}.csv')
            
            elif report_type == 'subscription':
                csv_data = report_data.get('subscription_revenue', [])
                csv_path = os.path.join(output_dir, f'subscription_report_{timestamp}.csv')
            
            elif report_type == 'failed_payments':
                csv_data = report_data.get('daily_failures', [])
                csv_path = os.path.join(output_dir, f'failed_payments_report_{timestamp}.csv')
            
            elif report_type == 'currency':
                csv_data = report_data.get('currency_stats', [])
                csv_path = os.path.join(output_dir, f'currency_report_{timestamp}.csv')
            
            else:  # 'all'
                # خلاصه همه گزارش‌ها
                csv_data = report_data.get('summary', {})
                csv_path = os.path.join(output_dir, f'all_reports_summary_{timestamp}.csv')
            
            if csv_data:
                if isinstance(csv_data, list):
                    # تبدیل لیست دیکشنری‌ها به فایل CSV
                    if csv_data:
                        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                            writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
                            writer.writeheader()
                            writer.writerows(csv_data)
                
                elif isinstance(csv_data, dict):
                    # تبدیل دیکشنری به فایل CSV
                    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['key', 'value'])
                        for key, value in csv_data.items():
                            writer.writerow([key, value])
                
                output_files['csv'] = csv_path
                logger.info(f"گزارش CSV در {csv_path} ذخیره شد")
        
        # ذخیره به فرمت Excel
        if output_format in ['excel', 'all']:
            excel_path = os.path.join(output_dir, f'{report_type}_report_{timestamp}.xlsx')
            
            # تبدیل داده‌های گزارش به DataFrames
            writer = pd.ExcelWriter(excel_path, engine='xlsxwriter')
            
            # خلاصه
            if 'summary' in report_data:
                summary_df = pd.DataFrame([report_data['summary']])
                summary_df = summary_df.transpose().reset_index()
                summary_df.columns = ['metric', 'value']
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # داده‌های اصلی بر اساس نوع گزارش
            if report_type == 'revenue' and 'revenues' in report_data:
                df = pd.DataFrame(report_data['revenues'])
                df.to_excel(writer, sheet_name='Revenues', index=False)
            
            elif report_type == 'expense' and 'expenses' in report_data:
                df = pd.DataFrame(report_data['expenses'])
                df.to_excel(writer, sheet_name='Expenses', index=False)
            
            elif report_type == 'profit' and 'profits' in report_data:
                df = pd.DataFrame(report_data['profits'])
                df.to_excel(writer, sheet_name='Profits', index=False)
            
            elif report_type == 'transactions':
                if 'daily_transactions' in report_data:
                    df = pd.DataFrame(report_data['daily_transactions'])
                    df.to_excel(writer, sheet_name='Daily Transactions', index=False)
                
                if 'status_stats' in report_data:
                    df = pd.DataFrame(report_data['status_stats'])
                    df.to_excel(writer, sheet_name='Status Stats', index=False)
                
                if 'payment_methods' in report_data:
                    df = pd.DataFrame(report_data['payment_methods'])
                    df.to_excel(writer, sheet_name='Payment Methods', index=False)
            
            elif report_type == 'subscription':
                if 'subscription_revenue' in report_data:
                    df = pd.DataFrame(report_data['subscription_revenue'])
                    df.to_excel(writer, sheet_name='Subscription Revenue', index=False)
                
                if 'monthly_trends' in report_data:
                    df = pd.DataFrame(report_data['monthly_trends'])
                    df.to_excel(writer, sheet_name='Monthly Trends', index=False)
            
            elif report_type == 'failed_payments':
                if 'daily_failures' in report_data:
                    df = pd.DataFrame(report_data['daily_failures'])
                    df.to_excel(writer, sheet_name='Daily Failures', index=False)
                
                if 'failure_reasons' in report_data:
                    df = pd.DataFrame(report_data['failure_reasons'])
                    df.to_excel(writer, sheet_name='Failure Reasons', index=False)
                
                if 'failed_by_method' in report_data:
                    df = pd.DataFrame(report_data['failed_by_method'])
                    df.to_excel(writer, sheet_name='Failed by Method', index=False)
                
                if 'top_failing_users' in report_data:
                    df = pd.DataFrame(report_data['top_failing_users'])
                    df.to_excel(writer, sheet_name='Top Failing Users', index=False)
            
            elif report_type == 'currency':
                if 'currency_stats' in report_data:
                    df = pd.DataFrame(report_data['currency_stats'])
                    df.to_excel(writer, sheet_name='Currency Stats', index=False)
                
                if 'current_rates' in report_data:
                    # تبدیل دیکشنری نرخ‌های تبدیل به DataFrame
                    rates_df = pd.DataFrame([
                        {'currency': currency, 'rate': rate}
                        for currency, rate in report_data['current_rates'].items()
                    ])
                    rates_df.to_excel(writer, sheet_name='Current Rates', index=False)
                
                if 'exchange_rate_trends' in report_data:
                    # ایجاد شیت جداگانه برای هر ارز
                    for i, trend in enumerate(report_data['exchange_rate_trends']):
                        currency = trend['currency']
                        df = pd.DataFrame(trend['rates'])
                        df.to_excel(writer, sheet_name=f'Rates {currency}', index=False)
            
            # ذخیره فایل Excel
            writer.close()
            
            output_files['excel'] = excel_path
            logger.info(f"گزارش Excel در {excel_path} ذخیره شد")
        
        return output_files
    
    except Exception as e:
        logger.error(f"خطا در ذخیره گزارش: {str(e)}")
        return {}


def run_report_generation(args: argparse.Namespace) -> int:
    """
    اجرای تولید گزارش
    
    :param args: آرگومان‌های خط فرمان
    :return: کد خروجی (0 موفق، 1 ناموفق)
    """
    try:
        # تنظیم سطح لاگینگ
        if args.verbose:
            logger.setLevel(logging.DEBUG)
        
        logger.info("شروع تولید گزارش مالی")
        
        # دریافت مسیر پایگاه داده
        db_path = get_db_path(args.db_path)
        
        # بررسی وجود فایل پایگاه داده
        if not os.path.exists(db_path):
            logger.error(f"فایل پایگاه داده {db_path} وجود ندارد")
            return 1
        
        # محاسبه محدوده تاریخ گزارش
        start_date, end_date = get_date_range(args.period, args.start_date, args.end_date)
        
        if args.verbose:
            logger.info(f"محدوده زمانی گزارش: از {start_date} تا {end_date}")
        
        # اتصال به پایگاه داده
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            # ایجاد دایرکتوری خروجی
            os.makedirs(args.output_dir, exist_ok=True)
            
            # گزارش‌های مورد نیاز
            reports_to_generate = []
            
            if args.report_type == 'all':
                reports_to_generate = ['revenue', 'expense', 'profit', 'transactions', 'subscription', 'failed_payments', 'currency']
            else:
                reports_to_generate = [args.report_type]
            
            # تولید گزارش‌های درخواستی
            all_reports = {}
            all_chart_files = {}
            all_output_files = {}
            
            for report_type in reports_to_generate:
                logger.info(f"تولید گزارش {report_type}")
                
                # تولید گزارش
                report_data = None
                
                if report_type == 'revenue':
                    report_data = generate_revenue_report(conn, start_date, end_date, args.group_by, args.base_currency, args.verbose)
                
                elif report_type == 'expense':
                    report_data = generate_expense_report(conn, start_date, end_date, args.group_by, args.base_currency, args.verbose)
                
                elif report_type == 'profit':
                    report_data = generate_profit_report(conn, start_date, end_date, args.group_by, args.base_currency, args.verbose)
                
                elif report_type == 'transactions':
                    report_data = generate_transactions_report(conn, start_date, end_date, args.base_currency, args.verbose)
                
                elif report_type == 'subscription':
                    report_data = generate_subscription_revenue_report(conn, start_date, end_date, args.base_currency, args.verbose)
                
                elif report_type == 'failed_payments':
                    report_data = generate_failed_payments_report(conn, start_date, end_date, args.verbose)
                
                elif report_type == 'currency':
                    report_data = generate_currency_report(conn, start_date, end_date, args.base_currency, args.verbose)
                
                if report_data and report_data.get('status') in ['success', 'warning']:
                    all_reports[report_type] = report_data
                    
                    # تولید نمودارها
                    if args.include_charts:
                        chart_files = generate_charts(report_data, report_type, args.output_dir)
                        if chart_files:
                            all_chart_files[report_type] = chart_files
                    
                    # ذخیره گزارش
                    output_files = save_report(report_data, args.format, args.output_dir, report_type)
                    if output_files:
                        all_output_files[report_type] = output_files
                else:
                    logger.error(f"خطا در تولید گزارش {report_type}")
            
            # بستن اتصال به پایگاه داده
            conn.close()
            
            # ذخیره گزارش کامل اگر چندین گزارش تولید شده باشد
            if len(all_reports) > 1:
                complete_report = {
                    'status': 'success',
                    'timestamp': datetime.get_current_datetime().isoformat(),
                    'period': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat()
                    },
                    'reports': all_reports
                }
                
                # ذخیره گزارش کامل
                timestamp = datetime.get_current_datetime().strftime('%Y%m%d_%H%M%S')
                complete_report_path = os.path.join(args.output_dir, f'complete_financial_report_{timestamp}.json')
                
                with open(complete_report_path, 'w', encoding='utf-8') as f:
                    json.dump(complete_report, f, ensure_ascii=False, indent=2)
                
                logger.info(f"گزارش کامل در {complete_report_path} ذخیره شد")
            
            # خلاصه گزارش
            logger.info("===== خلاصه تولید گزارش =====")
            logger.info(f"تعداد گزارش‌های تولید شده: {len(all_reports)}")
            
            # نمایش مسیر فایل‌های خروجی
            if all_output_files:
                logger.info("فایل‌های خروجی:")
                for report_type, files in all_output_files.items():
                    for format_type, file_path in files.items():
                        logger.info(f"  - {report_type} ({format_type}): {file_path}")
            
            return 0
        
        finally:
            # اطمینان از بسته شدن اتصال به پایگاه داده
            if conn:
                conn.close()
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش: {str(e)}")
        return 1


def main() -> None:
    """
    تابع اصلی
    """
    args = parse_arguments()
    exit_code = run_report_generation(args)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()