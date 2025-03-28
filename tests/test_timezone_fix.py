#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
تست‌های مربوط به اصلاح منطقه زمانی

این ماژول شامل تست‌های مختلف برای بررسی عملکرد صحیح ابزارهای مدیریت منطقه زمانی است.
این تست‌ها شامل بررسی تشخیص منطقه زمانی، تبدیل تاریخ و زمان بین منطقه‌های مختلف و غیره می‌باشد.
"""


from datetime import timezone
import os
import sys
import unittest
import json
import time
import datetime
from src.utils.timezone_utils import get_current_datetime
import pytz
import platform
from unittest import mock
from unittest.mock import patch, MagicMock, PropertyMock

# افزودن مسیر ریشه پروژه به sys.path برای واردسازی ماژول‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.timezone_utils import (
    get_system_timezone,
    get_current_datetime,
    convert_datetime,
    localize_datetime,
    datetime_to_timestamp,
    timestamp_to_datetime,
    format_datetime,
    parse_datetime,
    is_naive_datetime,
    is_aware_datetime
)

# اگر سیستم عامل ویندوز باشد، تست‌های مخصوص ویندوز را اجرا نمی‌کنیم
IS_WINDOWS = platform.system() == 'Windows'


class TestTimezoneUtils(unittest.TestCase):
    """
    تست‌های ابزارهای مدیریت منطقه زمانی
    """
    
    def setUp(self):
        """
        تنظیمات اولیه قبل از هر تست
        """
        # تنظیم تایم‌زون‌های آزمایشی
        self.tehran_tz = pytz.timezone("Asia/Tehran")
        self.utc_tz = pytz.UTC
        self.ny_tz = pytz.timezone("America/New_York")
        
        # ایجاد تاریخ‌های آزمایشی
        self.naive_dt = datetime.datetime(2023, 5, 15, 10, 30, 0)  # بدون منطقه زمانی
        self.utc_dt = pytz.UTC.localize(datetime.datetime(2023, 5, 15, 10, 30, 0))  # زمان UTC
        self.tehran_dt = self.tehran_tz.localize(datetime.datetime(2023, 5, 15, 14, 0, 0))  # زمان تهران
    
    @patch('src.utils.timezone_utils.get_system_timezone')
    def test_get_current_datetime(self, mock_get_system_timezone):
        """
        تست دریافت زمان جاری با منطقه زمانی صحیح
        """
        # تنظیم mock برای منطقه زمانی
        mock_get_system_timezone.return_value = self.tehran_tz
        
        # پچ datetime.now برای ثابت کردن زمان
        fixed_naive_time = datetime.datetime(2023, 5, 15, 10, 30, 0)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = fixed_naive_time
            
            # فراخوانی تابع
            current_dt = get_current_datetime()
            
            # بررسی نتایج
            self.assertTrue(is_aware_datetime(current_dt))
            self.assertEqual(current_dt.year, 2023)
            self.assertEqual(current_dt.month, 5)
            self.assertEqual(current_dt.day, 15)
            self.assertEqual(current_dt.hour, 10)
            self.assertEqual(current_dt.minute, 30)
            self.assertEqual(current_dt.tzinfo, self.tehran_tz)
    
    @patch('src.utils.timezone_utils.get_system_timezone')
    def test_get_current_datetime_with_tz(self, mock_get_system_timezone):
        """
        تست دریافت زمان جاری با منطقه زمانی مشخص
        """
        # تنظیم mock برای منطقه زمانی سیستم (که نباید استفاده شود)
        mock_get_system_timezone.return_value = self.tehran_tz
        
        # پچ datetime.now برای ثابت کردن زمان
        fixed_naive_time = datetime.datetime(2023, 5, 15, 10, 30, 0)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = fixed_naive_time
            
            # فراخوانی تابع با منطقه زمانی مشخص
            current_dt = get_current_datetime(timezone=self.ny_tz)
            
            # بررسی نتایج
            self.assertTrue(is_aware_datetime(current_dt))
            self.assertEqual(current_dt.year, 2023)
            self.assertEqual(current_dt.month, 5)
            self.assertEqual(current_dt.day, 15)
            self.assertEqual(current_dt.hour, 10)
            self.assertEqual(current_dt.minute, 30)
            self.assertEqual(current_dt.tzinfo, self.ny_tz)
            
            # بررسی عدم فراخوانی get_system_timezone
            mock_get_system_timezone.assert_not_called()
    
    @unittest.skipIf(IS_WINDOWS, "تست روی سیستم ویندوز اجرا نمی‌شود")
    def test_get_system_timezone(self):
        """
        تست تشخیص منطقه زمانی سیستم
        """
        # این تست تنها در سیستم‌های غیر ویندوز اجرا می‌شود
        # زیرا تشخیص منطقه زمانی در ویندوز به روش متفاوتی انجام می‌شود
        
        # پچ os.path.exists و os.path.isfile برای شبیه‌سازی وجود فایل localtime
        with patch('os.path.exists', return_value=True), \
             patch('os.path.isfile', return_value=True), \
             patch('os.readlink', return_value='/usr/share/zoneinfo/Asia/Tehran'):
            
            # فراخوانی تابع
            tz = get_system_timezone()
            
            # بررسی نتایج
            self.assertEqual(tz.zone, 'Asia/Tehran')
    
    def test_convert_datetime(self):
        """
        تست تبدیل تاریخ و زمان بین منطقه‌های زمانی مختلف
        """
        # تبدیل از تهران به نیویورک
        ny_dt = convert_datetime(self.tehran_dt, self.ny_tz)
        
        # بررسی نتایج (اختلاف زمانی بین تهران و نیویورک)
        # تهران: GMT+3:30، نیویورک: GMT-4 یا GMT-5 (بسته به ساعت تابستانی)
        # اختلاف معمولاً بین 7:30 تا 8:30 ساعت است
        
        # مقایسه تاریخ تهران و نیویورک
        same_moment_in_utc1 = self.tehran_dt.astimezone(pytz.UTC)
        same_moment_in_utc2 = ny_dt.astimezone(pytz.UTC)
        
        self.assertEqual(same_moment_in_utc1, same_moment_in_utc2)
        
        # مطمئن شویم منطقه زمانی نتیجه صحیح است
        self.assertEqual(ny_dt.tzinfo.zone, 'America/New_York')
    
    def test_localize_datetime(self):
        """
        تست اضافه کردن منطقه زمانی به تاریخ و زمان بدون منطقه زمانی
        """
        # افزودن منطقه زمانی تهران به تاریخ و زمان
        localized_dt = localize_datetime(self.naive_dt, self.tehran_tz)
        
        # بررسی نتایج
        self.assertTrue(is_aware_datetime(localized_dt))
        self.assertEqual(localized_dt.year, self.naive_dt.year)
        self.assertEqual(localized_dt.month, self.naive_dt.month)
        self.assertEqual(localized_dt.day, self.naive_dt.day)
        self.assertEqual(localized_dt.hour, self.naive_dt.hour)
        self.assertEqual(localized_dt.minute, self.naive_dt.minute)
        self.assertEqual(localized_dt.tzinfo, self.tehran_tz)
    
    def test_datetime_to_timestamp(self):
        """
        تست تبدیل تاریخ و زمان به timestamp
        """
        # تبدیل تاریخ و زمان تهران به timestamp
        ts = datetime_to_timestamp(self.tehran_dt)
        
        # بررسی نتایج
        # timestamp مقدار ثانیه‌های سپری شده از 1970-01-01 00:00:00 UTC است
        # بنابراین برای هر تاریخ و زمانی در هر منطقه زمانی، مقدار یکسانی خواهد بود
        
        # تبدیل مجدد timestamp به تاریخ و زمان UTC
        utc_dt = datetime.datetime.fromtimestamp(ts, pytz.UTC)
        
        # تبدیل تاریخ و زمان تهران به UTC برای مقایسه
        tehran_in_utc = self.tehran_dt.astimezone(pytz.UTC)
        
        # مقایسه (ممکن است چند ثانیه اختلاف داشته باشند)
        self.assertAlmostEqual(
            utc_dt.timestamp(),
            tehran_in_utc.timestamp(),
            delta=1  # حداکثر 1 ثانیه اختلاف مجاز است
        )
    
    def test_timestamp_to_datetime(self):
        """
        تست تبدیل timestamp به تاریخ و زمان
        """
        # ایجاد یک timestamp آزمایشی
        timestamp = 1684147800  # 2023-05-15 10:30:00 UTC
        
        # تبدیل timestamp به تاریخ و زمان با منطقه زمانی UTC
        dt_utc = timestamp_to_datetime(timestamp)
        
        # بررسی نتایج
        self.assertTrue(is_aware_datetime(dt_utc))
        self.assertEqual(dt_utc.year, 2023)
        self.assertEqual(dt_utc.month, 5)
        self.assertEqual(dt_utc.day, 15)
        self.assertEqual(dt_utc.hour, 10)
        self.assertEqual(dt_utc.minute, 30)
        self.assertEqual(dt_utc.tzinfo, pytz.UTC)
        
        # تبدیل timestamp به تاریخ و زمان با منطقه زمانی تهران
        dt_tehran = timestamp_to_datetime(timestamp, timezone=self.tehran_tz)
        
        # بررسی نتایج
        self.assertTrue(is_aware_datetime(dt_tehran))
        self.assertEqual(dt_tehran.tzinfo, self.tehran_tz)
        
        # تبدیل به UTC برای مقایسه
        dt_tehran_in_utc = dt_tehran.astimezone(pytz.UTC)
        
        # مقایسه (باید یک زمان یکسان باشند)
        self.assertEqual(dt_utc.year, dt_tehran_in_utc.year)
        self.assertEqual(dt_utc.month, dt_tehran_in_utc.month)
        self.assertEqual(dt_utc.day, dt_tehran_in_utc.day)
        self.assertEqual(dt_utc.hour, dt_tehran_in_utc.hour)
        self.assertEqual(dt_utc.minute, dt_tehran_in_utc.minute)
    
    def test_format_datetime(self):
        """
        تست قالب‌بندی تاریخ و زمان
        """
        # قالب‌بندی تاریخ و زمان تهران به فرمت‌های مختلف
        
        # فرمت پیش‌فرض
        default_format = format_datetime(self.tehran_dt)
        self.assertIn("2023", default_format)
        self.assertIn("05", default_format)
        self.assertIn("15", default_format)
        
        # فرمت سفارشی
        custom_format = format_datetime(self.tehran_dt, format_str="%Y/%m/%d %H:%M")
        self.assertEqual(custom_format, "2023/05/15 14:00")
        
        # قالب‌بندی با منطقه زمانی متفاوت
        ny_format = format_datetime(self.tehran_dt, timezone=self.ny_tz, format_str="%Y/%m/%d %H:%M %Z")
        
        # بررسی وجود منطقه زمانی در خروجی
        self.assertIn("EDT", ny_format)  # Eastern Daylight Time یا
        # self.assertIn("EST", ny_format)  # Eastern Standard Time
    
    def test_parse_datetime(self):
        """
        تست تجزیه رشته تاریخ و زمان
        """
        # تجزیه رشته تاریخ و زمان با فرمت‌های مختلف
        
        # فرمت ISO (پیش‌فرض)
        dt1 = parse_datetime("2023-05-15T14:00:00+03:30")
        self.assertEqual(dt1.year, 2023)
        self.assertEqual(dt1.month, 5)
        self.assertEqual(dt1.day, 15)
        self.assertEqual(dt1.hour, 14)
        self.assertEqual(dt1.minute, 0)
        
        # فرمت سفارشی
        dt2 = parse_datetime("2023/05/15 14:00", format_str="%Y/%m/%d %H:%M", timezone=self.tehran_tz)
        self.assertEqual(dt2.year, 2023)
        self.assertEqual(dt2.month, 5)
        self.assertEqual(dt2.day, 15)
        self.assertEqual(dt2.hour, 14)
        self.assertEqual(dt2.minute, 0)
        self.assertEqual(dt2.tzinfo, self.tehran_tz)
    
    def test_is_naive_datetime(self):
        """
        تست تشخیص تاریخ و زمان بدون منطقه زمانی
        """
        # بررسی تاریخ و زمان بدون منطقه زمانی
        self.assertTrue(is_naive_datetime(self.naive_dt))
        
        # بررسی تاریخ و زمان با منطقه زمانی
        self.assertFalse(is_naive_datetime(self.utc_dt))
        self.assertFalse(is_naive_datetime(self.tehran_dt))
    
    def test_is_aware_datetime(self):
        """
        تست تشخیص تاریخ و زمان با منطقه زمانی
        """
        # بررسی تاریخ و زمان با منطقه زمانی
        self.assertTrue(is_aware_datetime(self.utc_dt))
        self.assertTrue(is_aware_datetime(self.tehran_dt))
        
        # بررسی تاریخ و زمان بدون منطقه زمانی
        self.assertFalse(is_aware_datetime(self.naive_dt))


class TestTimezoneFixIntegration(unittest.TestCase):
    """
    تست‌های یکپارچگی برای اصلاح منطقه زمانی
    """
    
    @patch('src.utils.timezone_utils.get_system_timezone')
    def test_datetime_now_replacement(self, mock_get_system_timezone):
        """
        تست جایگزینی get_current_datetime() با get_current_datetime()
        """
        # تنظیم mock برای منطقه زمانی
        tehran_tz = pytz.timezone("Asia/Tehran")
        mock_get_system_timezone.return_value = tehran_tz
        
        # ثابت کردن زمان
        fixed_time = datetime.datetime(2023, 5, 15, 10, 30, 0)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = fixed_time
            
            # فراخوانی get_current_datetime بدون پارامتر
            dt1 = get_current_datetime()
            
            # بررسی نتایج
            self.assertTrue(is_aware_datetime(dt1))
            self.assertEqual(dt1.tzinfo, tehran_tz)
            
            # فراخوانی get_current_datetime با UTC
            dt2 = get_current_datetime(timezone=pytz.UTC)
            
            # بررسی نتایج
            self.assertTrue(is_aware_datetime(dt2))
            self.assertEqual(dt2.tzinfo, pytz.UTC)
            
            # مقایسه زمان (باید متفاوت باشند اما در یک لحظه باشند)
            self.assertNotEqual(dt1, dt2)
            
            # تبدیل هر دو به UTC
            dt1_utc = dt1.astimezone(pytz.UTC)
            
            # اختلاف باید کمتر از 1 ثانیه باشد
            self.assertAlmostEqual(
                dt1_utc.timestamp(),
                dt2.timestamp(),
                delta=1
            )

 
if __name__ == '__main__':
    unittest.main()