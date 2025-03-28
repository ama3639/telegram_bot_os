#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
اسکریپت تولید گزارش کاربران

این اسکریپت برای تولید گزارش‌های تحلیلی از کاربران ربات تلگرام طراحی شده است.
قابلیت‌های اصلی:
- تولید گزارش تعداد کاربران فعال
- تولید گزارش رشد کاربران
- تولید گزارش فعالیت کاربران
- تولید گزارش اشتراک‌های کاربران
- تولید گزارش تفکیک کاربران بر اساس کشور/زبان
- تولید گزارش کاربران با بیشترین تراکنش
- تولید گزارش وفاداری کاربران
- خروجی به فرمت‌های مختلف (JSON، CSV، Excel)
"""


from datetime import timezone
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
from collections import Counter

# افزودن مسیر ریشه پروژه به sys.path برای واردسازی ماژول‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.config import Config
from src.utils.timezone_utils import get_current_datetime
from src.utils.chart_generator import ChartGenerator

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
        description='تولید گزارش‌های تحلیلی از کاربران ربات تلگرام'
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
        default='data/reports/user_reports',
        help='مسیر دایرکتوری خروجی گزارش‌ها (پیش‌فرض: data/reports/user_reports)'
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
            'activity', 'growth', 'subscription', 'location', 
            'transactions', 'loyalty', 'all'
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
        '--top-count',
        type=int,
        default=10,
        help='تعداد موارد برتر در گزارش (پیش‌فرض: 10)'
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


def generate_activity_report(
    conn: sqlite3.Connection,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    تولید گزارش فعالیت کاربران
    
    :param conn: اتصال به پایگاه داده
    :param start_date: تاریخ شروع گزارش
    :param end_date: تاریخ پایان گزارش
    :param verbose: نمایش اطلاعات بیشتر
    :return: داده‌های گزارش
    """
    try:
        if verbose:
            logger.info(f"تولید گزارش فعالیت کاربران از {start_date} تا {end_date}")
        
        cursor = conn.cursor()
        
        # تبدیل تاریخ‌ها به رشته برای استفاده در کوئری SQL
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        # بررسی وجود جدول user_activities
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_activities'")
        if not cursor.fetchone():
            logger.warning("جدول user_activities در پایگاه داده وجود ندارد")
            return {
                'status': 'warning',
                'message': 'جدول user_activities در پایگاه داده وجود ندارد'
            }
        
        # آمار کلی فعالیت‌ها
        cursor.execute(f"""
            SELECT COUNT(*) as total_activities,
                   COUNT(DISTINCT user_id) as unique_users
            FROM user_activities
            WHERE timestamp BETWEEN ? AND ?
        """, (start_date_str, end_date_str))
        
        result = cursor.fetchone()
        total_activities = result[0]
        unique_users = result[1]
        
        # آمار فعالیت‌ها بر اساس نوع
        cursor.execute(f"""
            SELECT activity_type, COUNT(*) as count
            FROM user_activities
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY activity_type
            ORDER BY count DESC
        """, (start_date_str, end_date_str))
        
        activity_types = [dict(row) for row in cursor.fetchall()]
        
        # آمار فعالیت‌ها بر اساس روز
        cursor.execute(f"""
            SELECT strftime('%Y-%m-%d', timestamp) as date, COUNT(*) as count
            FROM user_activities
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        """, (start_date_str, end_date_str))
        
        daily_activities = [dict(row) for row in cursor.fetchall()]
        
        # کاربران فعال روزانه (DAU)
        cursor.execute(f"""
            SELECT strftime('%Y-%m-%d', timestamp) as date, COUNT(DISTINCT user_id) as count
            FROM user_activities
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        """, (start_date_str, end_date_str))
        
        dau = [dict(row) for row in cursor.fetchall()]
        
        # کاربران فعال ماهانه (MAU)
        cursor.execute(f"""
            SELECT strftime('%Y-%m', timestamp) as month, COUNT(DISTINCT user_id) as count
            FROM user_activities
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY month
            ORDER BY month
        """, (start_date_str, end_date_str))
        
        mau = [dict(row) for row in cursor.fetchall()]
        
        # کاربران با بیشترین فعالیت
        cursor.execute(f"""
            SELECT user_id, COUNT(*) as activity_count
            FROM user_activities
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY user_id
            ORDER BY activity_count DESC
            LIMIT 10
        """, (start_date_str, end_date_str))
        
        most_active_users = [dict(row) for row in cursor.fetchall()]
        
        # بررسی وجود جدول users
        has_users_table = False
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone():
            has_users_table = True
            
            # اضافه کردن اطلاعات کاربران به کاربران با بیشترین فعالیت
            for i, user in enumerate(most_active_users):
                user_id = user['user_id']
                
                cursor.execute(f"""
                    SELECT username, first_name, last_name
                    FROM users
                    WHERE id = ?
                """, (user_id,))
                
                user_info = cursor.fetchone()
                if user_info:
                    most_active_users[i]['username'] = user_info[0]
                    most_active_users[i]['first_name'] = user_info[1]
                    most_active_users[i]['last_name'] = user_info[2]
        
        # میانگین فعالیت‌های روزانه
        avg_daily_activities = round(total_activities / max(1, len(daily_activities)), 2) if daily_activities else 0
        
        # نسبت DAU/MAU
        last_month_date = (end_date - datetime.timedelta(days=30)).isoformat()
        
        cursor.execute(f"""
            SELECT COUNT(DISTINCT user_id) as mau
            FROM user_activities
            WHERE timestamp BETWEEN ? AND ?
        """, (last_month_date, end_date_str))
        
        last_month_mau = cursor.fetchone()[0]
        
        last_day_date = (end_date - datetime.timedelta(days=1)).isoformat()
        cursor.execute(f"""
            SELECT COUNT(DISTINCT user_id) as dau
            FROM user_activities
            WHERE timestamp BETWEEN ? AND ?
        """, (last_day_date, end_date_str))
        
        last_day_dau = cursor.fetchone()[0]
        
        dau_mau_ratio = round(last_day_dau / max(1, last_month_mau), 3) if last_month_mau else 0
        
        # ساخت گزارش نهایی
        report = {
            'status': 'success',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_activities': total_activities,
                'unique_users': unique_users,
                'avg_daily_activities': avg_daily_activities,
                'dau_mau_ratio': dau_mau_ratio,
                'last_day_dau': last_day_dau,
                'last_month_mau': last_month_mau
            },
            'activity_types': activity_types,
            'daily_activities': daily_activities,
            'dau': dau,
            'mau': mau,
            'most_active_users': most_active_users
        }
        
        return report
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پایگاه داده: {str(e)}")
        return {
            'status': 'error',
            'message': f"خطا در پایگاه داده: {str(e)}"
        }
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش فعالیت کاربران: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


def generate_growth_report(
    conn: sqlite3.Connection,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    تولید گزارش رشد کاربران
    
    :param conn: اتصال به پایگاه داده
    :param start_date: تاریخ شروع گزارش
    :param end_date: تاریخ پایان گزارش
    :param verbose: نمایش اطلاعات بیشتر
    :return: داده‌های گزارش
    """
    try:
        if verbose:
            logger.info(f"تولید گزارش رشد کاربران از {start_date} تا {end_date}")
        
        cursor = conn.cursor()
        
        # تبدیل تاریخ‌ها به رشته برای استفاده در کوئری SQL
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        # بررسی وجود جدول users
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            logger.warning("جدول users در پایگاه داده وجود ندارد")
            return {
                'status': 'warning',
                'message': 'جدول users در پایگاه داده وجود ندارد'
            }
        
        # تعداد کل کاربران
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # تعداد کاربران فعال (دارای فعالیت در بازه زمانی)
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) FROM user_activities
            WHERE timestamp BETWEEN ? AND ?
        """, (start_date_str, end_date_str))
        
        active_users = cursor.fetchone()[0]
        
        # رشد روزانه کاربران
        cursor.execute("""
            SELECT strftime('%Y-%m-%d', created_at) as date, COUNT(*) as count
            FROM users
            WHERE created_at BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        """, (start_date_str, end_date_str))
        
        daily_growth = [dict(row) for row in cursor.fetchall()]
        
        # رشد ماهانه کاربران
        cursor.execute("""
            SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count
            FROM users
            WHERE created_at BETWEEN ? AND ?
            GROUP BY month
            ORDER BY month
        """, (start_date_str, end_date_str))
        
        monthly_growth = [dict(row) for row in cursor.fetchall()]
        
        # کاربران جدید در بازه زمانی
        cursor.execute("""
            SELECT COUNT(*) FROM users
            WHERE created_at BETWEEN ? AND ?
        """, (start_date_str, end_date_str))
        
        new_users = cursor.fetchone()[0]
        
        # نرخ رشد
        previous_period_start = start_date - (end_date - start_date)
        previous_period_end = start_date
        
        cursor.execute("""
            SELECT COUNT(*) FROM users
            WHERE created_at BETWEEN ? AND ?
        """, (previous_period_start.isoformat(), previous_period_end.isoformat()))
        
        previous_period_new_users = cursor.fetchone()[0]
        
        growth_rate = 0
        if previous_period_new_users > 0:
            growth_rate = round(((new_users - previous_period_new_users) / previous_period_new_users) * 100, 2)
        
        # منابع ارجاع کاربران (اگر در پایگاه داده ذخیره شده باشد)
        referral_sources = []
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'referral_source' in columns:
            cursor.execute("""
                SELECT referral_source, COUNT(*) as count
                FROM users
                WHERE created_at BETWEEN ? AND ?
                GROUP BY referral_source
                ORDER BY count DESC
            """, (start_date_str, end_date_str))
            
            referral_sources = [dict(row) for row in cursor.fetchall()]
        
        # نرخ بازگشت کاربران (کاربرانی که بیش از یک بار فعالیت داشته‌اند)
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) FROM (
                SELECT user_id, COUNT(DISTINCT strftime('%Y-%m-%d', timestamp)) as days
                FROM user_activities
                WHERE timestamp BETWEEN ? AND ?
                GROUP BY user_id
                HAVING days > 1
            )
        """, (start_date_str, end_date_str))
        
        returning_users = cursor.fetchone()[0]
        retention_rate = round((returning_users / max(1, active_users)) * 100, 2) if active_users else 0
        
        # ساخت گزارش نهایی
        report = {
            'status': 'success',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_users': total_users,
                'active_users': active_users,
                'new_users': new_users,
                'growth_rate': growth_rate,
                'retention_rate': retention_rate,
                'returning_users': returning_users
            },
            'daily_growth': daily_growth,
            'monthly_growth': monthly_growth,
            'referral_sources': referral_sources
        }
        
        return report
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پایگاه داده: {str(e)}")
        return {
            'status': 'error',
            'message': f"خطا در پایگاه داده: {str(e)}"
        }
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش رشد کاربران: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


def generate_subscription_report(
    conn: sqlite3.Connection,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    تولید گزارش اشتراک‌های کاربران
    
    :param conn: اتصال به پایگاه داده
    :param start_date: تاریخ شروع گزارش
    :param end_date: تاریخ پایان گزارش
    :param verbose: نمایش اطلاعات بیشتر
    :return: داده‌های گزارش
    """
    try:
        if verbose:
            logger.info(f"تولید گزارش اشتراک‌های کاربران از {start_date} تا {end_date}")
        
        cursor = conn.cursor()
        
        # تبدیل تاریخ‌ها به رشته برای استفاده در کوئری SQL
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        # بررسی وجود جدول subscriptions
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subscriptions'")
        if not cursor.fetchone():
            logger.warning("جدول subscriptions در پایگاه داده وجود ندارد")
            return {
                'status': 'warning',
                'message': 'جدول subscriptions در پایگاه داده وجود ندارد'
            }
        
        # تعداد کل اشتراک‌ها
        cursor.execute("SELECT COUNT(*) FROM subscriptions")
        total_subscriptions = cursor.fetchone()[0]
        
        # اشتراک‌های فعال
        cursor.execute("""
            SELECT COUNT(*) FROM subscriptions
            WHERE status = 'active' AND end_date > ?
        """, (end_date_str,))
        
        active_subscriptions = cursor.fetchone()[0]
        
        # اشتراک‌های منقضی شده
        cursor.execute("""
            SELECT COUNT(*) FROM subscriptions
            WHERE status = 'expired' OR (status = 'active' AND end_date <= ?)
        """, (end_date_str,))
        
        expired_subscriptions = cursor.fetchone()[0]
        
        # اشتراک‌های جدید در بازه زمانی
        cursor.execute("""
            SELECT COUNT(*) FROM subscriptions
            WHERE created_at BETWEEN ? AND ?
        """, (start_date_str, end_date_str))
        
        new_subscriptions = cursor.fetchone()[0]
        
        # اشتراک‌های تمدید شده در بازه زمانی
        has_renewal_info = False
        renewal_count = 0
        
        cursor.execute("PRAGMA table_info(subscriptions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'is_renewal' in columns or 'renewal_count' in columns:
            has_renewal_info = True
            
            if 'is_renewal' in columns:
                cursor.execute("""
                    SELECT COUNT(*) FROM subscriptions
                    WHERE is_renewal = 1 AND created_at BETWEEN ? AND ?
                """, (start_date_str, end_date_str))
                
                renewal_count = cursor.fetchone()[0]
            
            elif 'renewal_count' in columns:
                cursor.execute("""
                    SELECT COUNT(*) FROM subscriptions
                    WHERE renewal_count > 0 AND created_at BETWEEN ? AND ?
                """, (start_date_str, end_date_str))
                
                renewal_count = cursor.fetchone()[0]
        
        # آمار اشتراک‌ها بر اساس نوع
        cursor.execute("""
            SELECT plan_type, COUNT(*) as count
            FROM subscriptions
            WHERE created_at BETWEEN ? AND ?
            GROUP BY plan_type
            ORDER BY count DESC
        """, (start_date_str, end_date_str))
        
        subscription_types = [dict(row) for row in cursor.fetchall()]
        
        # آمار اشتراک‌ها بر اساس روز
        cursor.execute("""
            SELECT strftime('%Y-%m-%d', created_at) as date, COUNT(*) as count
            FROM subscriptions
            WHERE created_at BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        """, (start_date_str, end_date_str))
        
        daily_subscriptions = [dict(row) for row in cursor.fetchall()]
        
        # محاسبه نرخ تبدیل (کاربران دارای اشتراک فعال به کل کاربران)
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        conversion_rate = round((active_subscriptions / max(1, total_users)) * 100, 2) if total_users else 0
        
        # محاسبه نرخ تمدید
        renewal_rate = 0
        if has_renewal_info and (new_subscriptions - renewal_count) > 0:
            renewal_rate = round((renewal_count / max(1, new_subscriptions)) * 100, 2)
        
        # محاسبه میانگین طول عمر اشتراک
        cursor.execute("""
            SELECT AVG(julianday(end_date) - julianday(start_date)) as avg_duration
            FROM subscriptions
            WHERE start_date IS NOT NULL AND end_date IS NOT NULL
        """)
        
        avg_duration = cursor.fetchone()[0] or 0
        
        # ساخت گزارش نهایی
        report = {
            'status': 'success',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_subscriptions': total_subscriptions,
                'active_subscriptions': active_subscriptions,
                'expired_subscriptions': expired_subscriptions,
                'new_subscriptions': new_subscriptions,
                'renewal_count': renewal_count,
                'conversion_rate': conversion_rate,
                'renewal_rate': renewal_rate,
                'avg_duration_days': round(avg_duration, 2)
            },
            'subscription_types': subscription_types,
            'daily_subscriptions': daily_subscriptions
        }
        
        return report
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پایگاه داده: {str(e)}")
        return {
            'status': 'error',
            'message': f"خطا در پایگاه داده: {str(e)}"
        }
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش اشتراک‌های کاربران: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


def generate_location_report(
    conn: sqlite3.Connection,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    تولید گزارش تفکیک کاربران بر اساس کشور/زبان
    
    :param conn: اتصال به پایگاه داده
    :param start_date: تاریخ شروع گزارش
    :param end_date: تاریخ پایان گزارش
    :param verbose: نمایش اطلاعات بیشتر
    :return: داده‌های گزارش
    """
    try:
        if verbose:
            logger.info(f"تولید گزارش تفکیک کاربران بر اساس کشور/زبان از {start_date} تا {end_date}")
        
        cursor = conn.cursor()
        
        # تبدیل تاریخ‌ها به رشته برای استفاده در کوئری SQL
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        # بررسی وجود جدول users
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            logger.warning("جدول users در پایگاه داده وجود ندارد")
            return {
                'status': 'warning',
                'message': 'جدول users در پایگاه داده وجود ندارد'
            }
        
        # بررسی وجود ستون‌های مربوط به کشور و زبان
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        has_country = 'country' in columns or 'country_code' in columns
        has_language = 'language' in columns or 'language_code' in columns
        
        # آمار کاربران بر اساس کشور
        users_by_country = []
        if has_country:
            country_column = 'country' if 'country' in columns else 'country_code'
            
            cursor.execute(f"""
                SELECT {country_column}, COUNT(*) as count
                FROM users
                WHERE created_at BETWEEN ? AND ?
                GROUP BY {country_column}
                ORDER BY count DESC
            """, (start_date_str, end_date_str))
            
            users_by_country = [dict(row) for row in cursor.fetchall()]
        
        # آمار کاربران بر اساس زبان
        users_by_language = []
        if has_language:
            language_column = 'language' if 'language' in columns else 'language_code'
            
            cursor.execute(f"""
                SELECT {language_column}, COUNT(*) as count
                FROM users
                WHERE created_at BETWEEN ? AND ?
                GROUP BY {language_column}
                ORDER BY count DESC
            """, (start_date_str, end_date_str))
            
            users_by_language = [dict(row) for row in cursor.fetchall()]
        
        # آمار کاربران بر اساس منطقه زمانی
        users_by_timezone = []
        if 'timezone' in columns:
            cursor.execute("""
                SELECT timezone, COUNT(*) as count
                FROM users
                WHERE created_at BETWEEN ? AND ?
                GROUP BY timezone
                ORDER BY count DESC
            """, (start_date_str, end_date_str))
            
            users_by_timezone = [dict(row) for row in cursor.fetchall()]
        
        # ساخت گزارش نهایی
        report = {
            'status': 'success',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'has_country_data': has_country,
            'has_language_data': has_language,
            'has_timezone_data': 'timezone' in columns,
            'users_by_country': users_by_country,
            'users_by_language': users_by_language,
            'users_by_timezone': users_by_timezone
        }
        
        return report
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پایگاه داده: {str(e)}")
        return {
            'status': 'error',
            'message': f"خطا در پایگاه داده: {str(e)}"
        }
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش تفکیک کاربران: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


def generate_transactions_report(
    conn: sqlite3.Connection,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    top_count: int = 10,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    تولید گزارش کاربران با بیشترین تراکنش
    
    :param conn: اتصال به پایگاه داده
    :param start_date: تاریخ شروع گزارش
    :param end_date: تاریخ پایان گزارش
    :param top_count: تعداد کاربران برتر
    :param verbose: نمایش اطلاعات بیشتر
    :return: داده‌های گزارش
    """
    try:
        if verbose:
            logger.info(f"تولید گزارش کاربران با بیشترین تراکنش از {start_date} تا {end_date}")
        
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
                COUNT(*) as total_transactions,
                COUNT(DISTINCT user_id) as unique_users,
                SUM(amount) as total_amount
            FROM transactions
            WHERE timestamp BETWEEN ? AND ?
        """, (start_date_str, end_date_str))
        
        result = cursor.fetchone()
        total_transactions = result[0]
        unique_users = result[1]
        total_amount = result[2] or 0
        
        # آمار تراکنش‌ها بر اساس وضعیت
        cursor.execute("""
            SELECT status, COUNT(*) as count, SUM(amount) as amount
            FROM transactions
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY status
            ORDER BY count DESC
        """, (start_date_str, end_date_str))
        
        transactions_by_status = [dict(row) for row in cursor.fetchall()]
        
        # آمار تراکنش‌ها بر اساس روز
        cursor.execute("""
            SELECT strftime('%Y-%m-%d', timestamp) as date, COUNT(*) as count, SUM(amount) as amount
            FROM transactions
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        """, (start_date_str, end_date_str))
        
        daily_transactions = [dict(row) for row in cursor.fetchall()]
        
        # کاربران با بیشترین تعداد تراکنش
        cursor.execute(f"""
            SELECT user_id, COUNT(*) as transaction_count, SUM(amount) as total_spent
            FROM transactions
            WHERE timestamp BETWEEN ? AND ? AND status = 'completed'
            GROUP BY user_id
            ORDER BY transaction_count DESC
            LIMIT {top_count}
        """, (start_date_str, end_date_str))
        
        top_users_by_count = [dict(row) for row in cursor.fetchall()]
        
        # کاربران با بیشترین مبلغ تراکنش
        cursor.execute(f"""
            SELECT user_id, COUNT(*) as transaction_count, SUM(amount) as total_spent
            FROM transactions
            WHERE timestamp BETWEEN ? AND ? AND status = 'completed'
            GROUP BY user_id
            ORDER BY total_spent DESC
            LIMIT {top_count}
        """, (start_date_str, end_date_str))
        
        top_users_by_amount = [dict(row) for row in cursor.fetchall()]
        
        # بررسی وجود جدول users
        has_users_table = False
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone():
            has_users_table = True
            
            # اضافه کردن اطلاعات کاربران به لیست‌های کاربران برتر
            for user_list in [top_users_by_count, top_users_by_amount]:
                for i, user in enumerate(user_list):
                    user_id = user['user_id']
                    
                    cursor.execute("""
                        SELECT username, first_name, last_name
                        FROM users
                        WHERE id = ?
                    """, (user_id,))
                    
                    user_info = cursor.fetchone()
                    if user_info:
                        user_list[i]['username'] = user_info[0]
                        user_list[i]['first_name'] = user_info[1]
                        user_list[i]['last_name'] = user_info[2]
        
        # محاسبه میانگین مبلغ تراکنش
        avg_transaction_amount = round(total_amount / max(1, total_transactions), 2) if total_transactions else 0
        
        # محاسبه میانگین مبلغ هر کاربر
        avg_amount_per_user = round(total_amount / max(1, unique_users), 2) if unique_users else 0
        
        # ساخت گزارش نهایی
        report = {
            'status': 'success',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_transactions': total_transactions,
                'unique_users': unique_users,
                'total_amount': total_amount,
                'avg_transaction_amount': avg_transaction_amount,
                'avg_amount_per_user': avg_amount_per_user
            },
            'transactions_by_status': transactions_by_status,
            'daily_transactions': daily_transactions,
            'top_users_by_count': top_users_by_count,
            'top_users_by_amount': top_users_by_amount
        }
        
        return report
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پایگاه داده: {str(e)}")
        return {
            'status': 'error',
            'message': f"خطا در پایگاه داده: {str(e)}"
        }
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش تراکنش‌های کاربران: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


def generate_loyalty_report(
    conn: sqlite3.Connection,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    تولید گزارش وفاداری کاربران
    
    :param conn: اتصال به پایگاه داده
    :param start_date: تاریخ شروع گزارش
    :param end_date: تاریخ پایان گزارش
    :param verbose: نمایش اطلاعات بیشتر
    :return: داده‌های گزارش
    """
    try:
        if verbose:
            logger.info(f"تولید گزارش وفاداری کاربران از {start_date} تا {end_date}")
        
        cursor = conn.cursor()
        
        # تبدیل تاریخ‌ها به رشته برای استفاده در کوئری SQL
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        # بررسی وجود جدول users و user_activities
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        has_users = cursor.fetchone() is not None
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_activities'")
        has_activities = cursor.fetchone() is not None
        
        if not (has_users and has_activities):
            logger.warning("جداول users یا user_activities در پایگاه داده وجود ندارند")
            return {
                'status': 'warning',
                'message': 'جداول users یا user_activities در پایگاه داده وجود ندارند'
            }
        
        # طول عمر کاربران (از زمان ثبت‌نام تا آخرین فعالیت)
        cursor.execute("""
            SELECT 
                u.id as user_id,
                u.created_at as signup_date,
                MAX(a.timestamp) as last_activity
            FROM users u
            LEFT JOIN user_activities a ON u.id = a.user_id
            GROUP BY u.id
        """)
        
        user_lifetimes = []
        for row in cursor.fetchall():
            user_id = row[0]
            signup_date = row[1]
            last_activity = row[2]
            
            if signup_date and last_activity:
                try:
                    signup_dt = datetime.datetime.fromisoformat(signup_date)
                    last_activity_dt = datetime.datetime.fromisoformat(last_activity)
                    
                    lifetime_days = (last_activity_dt - signup_dt).days
                    
                    user_lifetimes.append({
                        'user_id': user_id,
                        'signup_date': signup_date,
                        'last_activity': last_activity,
                        'lifetime_days': lifetime_days
                    })
                except ValueError:
                    # تاریخ‌های نامعتبر را نادیده می‌گیریم
                    pass
        
        # محاسبه میانگین طول عمر کاربران
        avg_lifetime = 0
        if user_lifetimes:
            avg_lifetime = sum(u['lifetime_days'] for u in user_lifetimes) / len(user_lifetimes)
        
        # تعداد کاربران فعال در بازه زمانی
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) FROM user_activities
            WHERE timestamp BETWEEN ? AND ?
        """, (start_date_str, end_date_str))
        
        active_users = cursor.fetchone()[0]
        
        # تعداد کل کاربران
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # محاسبه نرخ فعال بودن کاربران
        activity_rate = round((active_users / max(1, total_users)) * 100, 2) if total_users else 0
        
        # تعداد جلسات هر کاربر
        cursor.execute("""
            SELECT 
                user_id,
                COUNT(DISTINCT strftime('%Y-%m-%d', timestamp)) as sessions
            FROM user_activities
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY user_id
            ORDER BY sessions DESC
        """, (start_date_str, end_date_str))
        
        user_sessions = [dict(row) for row in cursor.fetchall()]
        
        # محاسبه میانگین تعداد جلسات
        avg_sessions = 0
        if user_sessions:
            avg_sessions = sum(u['sessions'] for u in user_sessions) / len(user_sessions)
        
        # محاسبه توزیع تعداد جلسات
        sessions_distribution = Counter(u['sessions'] for u in user_sessions)
        sessions_distribution = [
            {'sessions': sessions, 'count': count}
            for sessions, count in sorted(sessions_distribution.items())
        ]
        
        # محاسبه نرخ بازگشت کاربران (کاربرانی که بیش از یک جلسه داشته‌اند)
        returning_users = sum(1 for u in user_sessions if u['sessions'] > 1)
        retention_rate = round((returning_users / max(1, len(user_sessions))) * 100, 2) if user_sessions else 0
        
        # محاسبه وفاداری کاربران بر اساس تعداد ماه‌های فعالیت
        cursor.execute("""
            SELECT 
                user_id,
                COUNT(DISTINCT strftime('%Y-%m', timestamp)) as active_months
            FROM user_activities
            GROUP BY user_id
            ORDER BY active_months DESC
        """)
        
        user_active_months = [dict(row) for row in cursor.fetchall()]
        
        # محاسبه توزیع تعداد ماه‌های فعالیت
        months_distribution = Counter(u['active_months'] for u in user_active_months)
        months_distribution = [
            {'months': months, 'count': count}
            for months, count in sorted(months_distribution.items())
        ]
        
        # ساخت گزارش نهایی
        report = {
            'status': 'success',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_users': total_users,
                'active_users': active_users,
                'activity_rate': activity_rate,
                'avg_lifetime_days': round(avg_lifetime, 2),
                'avg_sessions': round(avg_sessions, 2),
                'returning_users': returning_users,
                'retention_rate': retention_rate
            },
            'sessions_distribution': sessions_distribution,
            'months_distribution': months_distribution
        }
        
        return report
    
    except sqlite3.Error as e:
        logger.error(f"خطا در پایگاه داده: {str(e)}")
        return {
            'status': 'error',
            'message': f"خطا در پایگاه داده: {str(e)}"
        }
    
    except Exception as e:
        logger.error(f"خطا در تولید گزارش وفاداری کاربران: {str(e)}")
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
        
        if report_type == 'activity' or report_type == 'all':
            if report_data.get('status') == 'success' and 'daily_activities' in report_data:
                # نمودار فعالیت‌های روزانه
                daily_data = report_data['daily_activities']
                if daily_data:
                    dates = [item['date'] for item in daily_data]
                    counts = [item['count'] for item in daily_data]
                    
                    chart_path = os.path.join(charts_dir, f'daily_activities_{timestamp}.png')
                    chart_generator.create_line_chart(
                        dates, counts, 
                        'فعالیت‌های روزانه کاربران', 
                        'تاریخ', 'تعداد فعالیت‌ها',
                        chart_path
                    )
                    
                    chart_files['daily_activities'] = chart_path
                
                # نمودار کاربران فعال روزانه (DAU)
                dau_data = report_data.get('dau', [])
                if dau_data:
                    dates = [item['date'] for item in dau_data]
                    counts = [item['count'] for item in dau_data]
                    
                    chart_path = os.path.join(charts_dir, f'daily_active_users_{timestamp}.png')
                    chart_generator.create_line_chart(
                        dates, counts, 
                        'کاربران فعال روزانه (DAU)', 
                        'تاریخ', 'تعداد کاربران فعال',
                        chart_path
                    )
                    
                    chart_files['daily_active_users'] = chart_path
                
                # نمودار انواع فعالیت‌ها
                activity_types = report_data.get('activity_types', [])
                if activity_types:
                    labels = [item['activity_type'] for item in activity_types]
                    counts = [item['count'] for item in activity_types]
                    
                    chart_path = os.path.join(charts_dir, f'activity_types_{timestamp}.png')
                    chart_generator.create_pie_chart(
                        labels, counts, 
                        'توزیع انواع فعالیت‌ها', 
                        chart_path
                    )
                    
                    chart_files['activity_types'] = chart_path
        
        if report_type == 'growth' or report_type == 'all':
            if report_data.get('status') == 'success':
                # نمودار رشد روزانه کاربران
                daily_growth = report_data.get('daily_growth', [])
                if daily_growth:
                    dates = [item['date'] for item in daily_growth]
                    counts = [item['count'] for item in daily_growth]
                    
                    chart_path = os.path.join(charts_dir, f'daily_growth_{timestamp}.png')
                    chart_generator.create_line_chart(
                        dates, counts, 
                        'رشد روزانه کاربران', 
                        'تاریخ', 'تعداد کاربران جدید',
                        chart_path
                    )
                    
                    chart_files['daily_growth'] = chart_path
                
                # نمودار رشد ماهانه کاربران
                monthly_growth = report_data.get('monthly_growth', [])
                if monthly_growth:
                    months = [item['month'] for item in monthly_growth]
                    counts = [item['count'] for item in monthly_growth]
                    
                    chart_path = os.path.join(charts_dir, f'monthly_growth_{timestamp}.png')
                    chart_generator.create_bar_chart(
                        months, counts, 
                        'رشد ماهانه کاربران', 
                        'ماه', 'تعداد کاربران جدید',
                        chart_path
                    )
                    
                    chart_files['monthly_growth'] = chart_path
                
                # نمودار منابع ارجاع کاربران
                referral_sources = report_data.get('referral_sources', [])
                if referral_sources:
                    labels = [item['referral_source'] for item in referral_sources]
                    counts = [item['count'] for item in referral_sources]
                    
                    chart_path = os.path.join(charts_dir, f'referral_sources_{timestamp}.png')
                    chart_generator.create_pie_chart(
                        labels, counts, 
                        'منابع ارجاع کاربران', 
                        chart_path
                    )
                    
                    chart_files['referral_sources'] = chart_path
        
        if report_type == 'subscription' or report_type == 'all':
            if report_data.get('status') == 'success':
                # نمودار اشتراک‌های روزانه
                daily_subscriptions = report_data.get('daily_subscriptions', [])
                if daily_subscriptions:
                    dates = [item['date'] for item in daily_subscriptions]
                    counts = [item['count'] for item in daily_subscriptions]
                    
                    chart_path = os.path.join(charts_dir, f'daily_subscriptions_{timestamp}.png')
                    chart_generator.create_line_chart(
                        dates, counts, 
                        'اشتراک‌های روزانه', 
                        'تاریخ', 'تعداد اشتراک‌ها',
                        chart_path
                    )
                    
                    chart_files['daily_subscriptions'] = chart_path
                
                # نمودار انواع اشتراک‌ها
                subscription_types = report_data.get('subscription_types', [])
                if subscription_types:
                    labels = [item['plan_type'] for item in subscription_types]
                    counts = [item['count'] for item in subscription_types]
                    
                    chart_path = os.path.join(charts_dir, f'subscription_types_{timestamp}.png')
                    chart_generator.create_pie_chart(
                        labels, counts, 
                        'توزیع انواع اشتراک‌ها', 
                        chart_path
                    )
                    
                    chart_files['subscription_types'] = chart_path
        
        if report_type == 'location' or report_type == 'all':
            if report_data.get('status') == 'success':
                # نمودار کاربران بر اساس کشور
                users_by_country = report_data.get('users_by_country', [])
                if users_by_country:
                    # محدود کردن به 10 کشور برتر
                    top_countries = users_by_country[:10]
                    
                    labels = [item.get('country', item.get('country_code', 'نامشخص')) for item in top_countries]
                    counts = [item['count'] for item in top_countries]
                    
                    chart_path = os.path.join(charts_dir, f'users_by_country_{timestamp}.png')
                    chart_generator.create_bar_chart(
                        labels, counts, 
                        'کاربران بر اساس کشور (10 مورد برتر)', 
                        'کشور', 'تعداد کاربران',
                        chart_path
                    )
                    
                    chart_files['users_by_country'] = chart_path
                
                # نمودار کاربران بر اساس زبان
                users_by_language = report_data.get('users_by_language', [])
                if users_by_language:
                    # محدود کردن به 10 زبان برتر
                    top_languages = users_by_language[:10]
                    
                    labels = [item.get('language', item.get('language_code', 'نامشخص')) for item in top_languages]
                    counts = [item['count'] for item in top_languages]
                    
                    chart_path = os.path.join(charts_dir, f'users_by_language_{timestamp}.png')
                    chart_generator.create_pie_chart(
                        labels, counts, 
                        'کاربران بر اساس زبان (10 مورد برتر)', 
                        chart_path
                    )
                    
                    chart_files['users_by_language'] = chart_path
        
        if report_type == 'transactions' or report_type == 'all':
            if report_data.get('status') == 'success':
                # نمودار تراکنش‌های روزانه
                daily_transactions = report_data.get('daily_transactions', [])
                if daily_transactions:
                    dates = [item['date'] for item in daily_transactions]
                    counts = [item['count'] for item in daily_transactions]
                    amounts = [float(item['amount']) if item['amount'] else 0 for item in daily_transactions]
                    
                    # نمودار تعداد تراکنش‌ها
                    chart_path = os.path.join(charts_dir, f'daily_transaction_counts_{timestamp}.png')
                    chart_generator.create_line_chart(
                        dates, counts, 
                        'تعداد تراکنش‌های روزانه', 
                        'تاریخ', 'تعداد تراکنش‌ها',
                        chart_path
                    )
                    
                    chart_files['daily_transaction_counts'] = chart_path
                    
                    # نمودار مبلغ تراکنش‌ها
                    chart_path = os.path.join(charts_dir, f'daily_transaction_amounts_{timestamp}.png')
                    chart_generator.create_line_chart(
                        dates, amounts, 
                        'مبلغ تراکنش‌های روزانه', 
                        'تاریخ', 'مبلغ تراکنش‌ها',
                        chart_path
                    )
                    
                    chart_files['daily_transaction_amounts'] = chart_path
                
                # نمودار وضعیت تراکنش‌ها
                transactions_by_status = report_data.get('transactions_by_status', [])
                if transactions_by_status:
                    labels = [item['status'] for item in transactions_by_status]
                    counts = [item['count'] for item in transactions_by_status]
                    
                    chart_path = os.path.join(charts_dir, f'transactions_by_status_{timestamp}.png')
                    chart_generator.create_pie_chart(
                        labels, counts, 
                        'توزیع وضعیت تراکنش‌ها', 
                        chart_path
                    )
                    
                    chart_files['transactions_by_status'] = chart_path
        
        if report_type == 'loyalty' or report_type == 'all':
            if report_data.get('status') == 'success':
                # نمودار توزیع تعداد جلسات
                sessions_distribution = report_data.get('sessions_distribution', [])
                if sessions_distribution:
                    labels = [str(item['sessions']) for item in sessions_distribution]
                    counts = [item['count'] for item in sessions_distribution]
                    
                    chart_path = os.path.join(charts_dir, f'sessions_distribution_{timestamp}.png')
                    chart_generator.create_bar_chart(
                        labels, counts, 
                        'توزیع تعداد جلسات کاربران', 
                        'تعداد جلسات', 'تعداد کاربران',
                        chart_path
                    )
                    
                    chart_files['sessions_distribution'] = chart_path
                
                # نمودار توزیع تعداد ماه‌های فعالیت
                months_distribution = report_data.get('months_distribution', [])
                if months_distribution:
                    labels = [str(item['months']) for item in months_distribution]
                    counts = [item['count'] for item in months_distribution]
                    
                    chart_path = os.path.join(charts_dir, f'months_distribution_{timestamp}.png')
                    chart_generator.create_bar_chart(
                        labels, counts, 
                        'توزیع تعداد ماه‌های فعالیت کاربران', 
                        'تعداد ماه‌ها', 'تعداد کاربران',
                        chart_path
                    )
                    
                    chart_files['months_distribution'] = chart_path
        
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
            
            if report_type == 'activity':
                csv_data = report_data.get('daily_activities', [])
                csv_path = os.path.join(output_dir, f'activity_report_{timestamp}.csv')
            
            elif report_type == 'growth':
                csv_data = report_data.get('daily_growth', [])
                csv_path = os.path.join(output_dir, f'growth_report_{timestamp}.csv')
            
            elif report_type == 'subscription':
                csv_data = report_data.get('daily_subscriptions', [])
                csv_path = os.path.join(output_dir, f'subscription_report_{timestamp}.csv')
            
            elif report_type == 'location':
                csv_data = report_data.get('users_by_country', [])
                csv_path = os.path.join(output_dir, f'location_report_{timestamp}.csv')
            
            elif report_type == 'transactions':
                csv_data = report_data.get('daily_transactions', [])
                csv_path = os.path.join(output_dir, f'transactions_report_{timestamp}.csv')
            
            elif report_type == 'loyalty':
                csv_data = report_data.get('sessions_distribution', [])
                csv_path = os.path.join(output_dir, f'loyalty_report_{timestamp}.csv')
            
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
            
            # داده‌های اصلی
            if report_type == 'activity':
                if 'daily_activities' in report_data:
                    df = pd.DataFrame(report_data['daily_activities'])
                    df.to_excel(writer, sheet_name='Daily Activities', index=False)
                
                if 'activity_types' in report_data:
                    df = pd.DataFrame(report_data['activity_types'])
                    df.to_excel(writer, sheet_name='Activity Types', index=False)
                
                if 'dau' in report_data:
                    df = pd.DataFrame(report_data['dau'])
                    df.to_excel(writer, sheet_name='Daily Active Users', index=False)
                
                if 'mau' in report_data:
                    df = pd.DataFrame(report_data['mau'])
                    df.to_excel(writer, sheet_name='Monthly Active Users', index=False)
                
                if 'most_active_users' in report_data:
                    df = pd.DataFrame(report_data['most_active_users'])
                    df.to_excel(writer, sheet_name='Most Active Users', index=False)
            
            elif report_type == 'growth':
                if 'daily_growth' in report_data:
                    df = pd.DataFrame(report_data['daily_growth'])
                    df.to_excel(writer, sheet_name='Daily Growth', index=False)
                
                if 'monthly_growth' in report_data:
                    df = pd.DataFrame(report_data['monthly_growth'])
                    df.to_excel(writer, sheet_name='Monthly Growth', index=False)
                
                if 'referral_sources' in report_data:
                    df = pd.DataFrame(report_data['referral_sources'])
                    df.to_excel(writer, sheet_name='Referral Sources', index=False)
            
            elif report_type == 'subscription':
                if 'subscription_types' in report_data:
                    df = pd.DataFrame(report_data['subscription_types'])
                    df.to_excel(writer, sheet_name='Subscription Types', index=False)
                
                if 'daily_subscriptions' in report_data:
                    df = pd.DataFrame(report_data['daily_subscriptions'])
                    df.to_excel(writer, sheet_name='Daily Subscriptions', index=False)
            
            elif report_type == 'location':
                if 'users_by_country' in report_data:
                    df = pd.DataFrame(report_data['users_by_country'])
                    df.to_excel(writer, sheet_name='Users by Country', index=False)
                
                if 'users_by_language' in report_data:
                    df = pd.DataFrame(report_data['users_by_language'])
                    df.to_excel(writer, sheet_name='Users by Language', index=False)
                
                if 'users_by_timezone' in report_data:
                    df = pd.DataFrame(report_data['users_by_timezone'])
                    df.to_excel(writer, sheet_name='Users by Timezone', index=False)
            
            elif report_type == 'transactions':
                if 'transactions_by_status' in report_data:
                    df = pd.DataFrame(report_data['transactions_by_status'])
                    df.to_excel(writer, sheet_name='Transactions by Status', index=False)
                
                if 'daily_transactions' in report_data:
                    df = pd.DataFrame(report_data['daily_transactions'])
                    df.to_excel(writer, sheet_name='Daily Transactions', index=False)
                
                if 'top_users_by_count' in report_data:
                    df = pd.DataFrame(report_data['top_users_by_count'])
                    df.to_excel(writer, sheet_name='Top Users by Count', index=False)
                
                if 'top_users_by_amount' in report_data:
                    df = pd.DataFrame(report_data['top_users_by_amount'])
                    df.to_excel(writer, sheet_name='Top Users by Amount', index=False)
            
            elif report_type == 'loyalty':
                if 'sessions_distribution' in report_data:
                    df = pd.DataFrame(report_data['sessions_distribution'])
                    df.to_excel(writer, sheet_name='Sessions Distribution', index=False)
                
                if 'months_distribution' in report_data:
                    df = pd.DataFrame(report_data['months_distribution'])
                    df.to_excel(writer, sheet_name='Months Distribution', index=False)
            
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
        
        logger.info("شروع تولید گزارش کاربران")
        
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
                reports_to_generate = ['activity', 'growth', 'subscription', 'location', 'transactions', 'loyalty']
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
                
                if report_type == 'activity':
                    report_data = generate_activity_report(conn, start_date, end_date, args.verbose)
                
                elif report_type == 'growth':
                    report_data = generate_growth_report(conn, start_date, end_date, args.verbose)
                
                elif report_type == 'subscription':
                    report_data = generate_subscription_report(conn, start_date, end_date, args.verbose)
                
                elif report_type == 'location':
                    report_data = generate_location_report(conn, start_date, end_date, args.verbose)
                
                elif report_type == 'transactions':
                    report_data = generate_transactions_report(conn, start_date, end_date, args.top_count, args.verbose)
                
                elif report_type == 'loyalty':
                    report_data = generate_loyalty_report(conn, start_date, end_date, args.verbose)
                
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
                complete_report_path = os.path.join(args.output_dir, f'complete_user_report_{timestamp}.json')
                
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