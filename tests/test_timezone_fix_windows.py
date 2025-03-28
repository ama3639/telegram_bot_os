#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
تست‌های مربوط به اصلاح منطقه زمانی در ویندوز

این ماژول شامل تست‌های مختص سیستم‌عامل ویندوز برای بررسی عملکرد صحیح 
ابزارهای مدیریت منطقه زمانی است.
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
import winreg
from unittest import mock
from unittest.mock import patch, MagicMock

# افزودن مسیر ریشه پروژه به sys.path برای واردسازی ماژول‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.timezone_utils import (
    get_system_timezone,
    get_current_datetime,
    convert_datetime,
    localize_datetime,
    get_windows_timezone_map,
    get_windows_timezone_from_registry
)

# تست‌ها تنها در سیستم‌عامل ویندوز اجرا می‌شوند
IS_WINDOWS = platform.system() == 'Windows'


@unittest.skipIf(not IS_WINDOWS, "تست‌ها تنها در سیستم‌عامل ویندوز اجرا می‌شوند")
class TestWindowsTimezoneUtils(unittest.TestCase):
    """
    تست‌های ابزارهای مدیریت منطقه زمانی در ویندوز
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
    
    def test_get_windows_timezone_map(self):
        """
        تست دریافت نگاشت منطقه‌های زمانی ویندوز به IANA
        """
        # دریافت نگاشت
        timezone_map = get_windows_timezone_map()
        
        # بررسی ساختار خروجی
        self.assertIsInstance(timezone_map, dict)
        self.assertTrue(len(timezone_map) > 0)
        
        # بررسی وجود کلیدهای مهم
        self.assertIn("Iran Standard Time", timezone_map)  # منطقه زمانی ایران
        self.assertIn("UTC", timezone_map)  # منطقه زمانی UTC
        self.assertIn("Eastern Standard Time", timezone_map)  # منطقه زمانی آمریکای شرقی
        
        # بررسی مقادیر نگاشت
        self.assertEqual(timezone_map["Iran Standard Time"], "Asia/Tehran")
        self.assertEqual(timezone_map["UTC"], "UTC")
        self.assertEqual(timezone_map["Eastern Standard Time"], "America/New_York")
    
    @patch('winreg.OpenKey')
    @patch('winreg.QueryValueEx')
    def test_get_windows_timezone_from_registry(self, mock_query_value, mock_open_key):
        """
        تست خواندن منطقه زمانی از رجیستری ویندوز
        """
        # تنظیم mock‌ها
        mock_key = MagicMock()
        mock_open_key.return_value = mock_key
        mock_query_value.return_value = ("Iran Standard Time", 1)
        
        # فراخوانی تابع
        windows_tz = get_windows_timezone_from_registry()
        
        # بررسی نتایج
        self.assertEqual(windows_tz, "Iran Standard Time")
        
        # بررسی فراخوانی‌های توابع
        mock_open_key.assert_called_once_with(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation"
        )
        mock_query_value.assert_called_once_with(mock_key, "TimeZoneKeyName")
    
    @patch('src.utils.timezone_utils.get_windows_timezone_from_registry')
    @patch('src.utils.timezone_utils.get_windows_timezone_map')
    def test_get_system_timezone(self, mock_get_map, mock_get_from_registry):
        """
        تست تشخیص منطقه زمانی سیستم در ویندوز
        """
        # تنظیم mock‌ها
        mock_get_from_registry.return_value = "Iran Standard Time"
        mock_get_map.return_value = {"Iran Standard Time": "Asia/Tehran"}
        
        # فراخوانی تابع
        tz = get_system_timezone()
        
        # بررسی نتایج
        self.assertEqual(tz.zone, "Asia/Tehran")
        
        # بررسی فراخوانی‌های توابع
        mock_get_from_registry.assert_called_once()
        mock_get_map.assert_called_once()
    
    @patch('src.utils.timezone_utils.get_windows_timezone_from_registry')
    @patch('src.utils.timezone_utils.get_windows_timezone_map')
    def test_get_system_timezone_fallback(self, mock_get_map, mock_get_from_registry):
        """
        تست مکانیزم پشتیبان برای تشخیص منطقه زمانی
        """
        # تنظیم mock‌ها برای شبیه‌سازی خطا
        mock_get_from_registry.side_effect = Exception("Registry error")
        mock_get_map.return_value = {"Iran Standard Time": "Asia/Tehran"}
        
        # پچ دریافت منطقه زمانی محلی
        with patch('time.tzname', ('Unknown', 'UnknownDST')), \
             patch('time.timezone', -12600):  # UTC+3:30
            
            # فراخوانی تابع
            tz = get_system_timezone()
            
            # بررسی نتایج (باید یک منطقه زمانی با اختلاف مشابه برگرداند)
            self.assertIn(tz.utcoffset(datetime.get_current_datetime()).total_seconds(), (12600, 14400))  # UTC+3:30 یا UTC+4 (بسته به ساعت تابستانی)


class TestWindowsTimezoneFixIntegration(unittest.TestCase):
    """
    تست‌های یکپارچگی برای اصلاح منطقه زمانی در ویندوز
    
    این تست‌ها در هر سیستم عاملی قابل اجرا هستند، زیرا از mock استفاده می‌کنند.
    """
    
    def setUp(self):
        """
        تنظیمات اولیه قبل از هر تست
        """
        # تنظیم تایم‌زون‌های آزمایشی
        self.tehran_tz = pytz.timezone("Asia/Tehran")
        self.utc_tz = pytz.UTC
        self.ny_tz = pytz.timezone("America/New_York")
    
    @patch('src.utils.timezone_utils.get_windows_timezone_from_registry')
    @patch('src.utils.timezone_utils.get_windows_timezone_map')
    def test_windows_to_iana_timezone_conversion(self, mock_get_map, mock_get_from_registry):
        """
        تست تبدیل منطقه زمانی ویندوز به IANA
        """
        # تنظیم mock‌ها
        mock_get_from_registry.return_value = "Iran Standard Time"
        mock_get_map.return_value = {
            "Iran Standard Time": "Asia/Tehran",
            "UTC": "UTC",
            "Eastern Standard Time": "America/New_York"
        }
        
        # فراخوانی تابع
        tz = get_system_timezone()
        
        # بررسی نتایج
        self.assertEqual(tz.zone, "Asia/Tehran")
        
        # بررسی فراخوانی‌های توابع
        mock_get_from_registry.assert_called_once()
        mock_get_map.assert_called_once()
    
    @patch('src.utils.timezone_utils.get_system_timezone')
    def test_get_current_datetime_windows(self, mock_get_system_timezone):
        """
        تست دریافت زمان جاری در ویندوز
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
            self.assertEqual(current_dt.tzinfo, self.tehran_tz)
            self.assertEqual(current_dt.year, 2023)
            self.assertEqual(current_dt.month, 5)
            self.assertEqual(current_dt.day, 15)
            self.assertEqual(current_dt.hour, 10)
            self.assertEqual(current_dt.minute, 30)
    
    @patch('src.utils.timezone_utils.get_windows_timezone_from_registry')
    @patch('src.utils.timezone_utils.get_windows_timezone_map')
    def test_fallback_mechanism(self, mock_get_map, mock_get_from_registry):
        """
        تست مکانیزم پشتیبان در صورت خطا در رجیستری
        """
        # تنظیم mock‌ها برای شبیه‌سازی خطا
        mock_get_from_registry.side_effect = Exception("Registry error")
        mock_get_map.return_value = {"Iran Standard Time": "Asia/Tehran"}
        
        # پچ time.tzname و time.timezone برای شبیه‌سازی منطقه زمانی
        with patch('time.tzname', ('IST', 'ISDT')), \
             patch('time.timezone', -12600), \
             patch('platform.system', return_value='Windows'):
            
            # فراخوانی تابع
            tz = get_system_timezone()
            
            # بررسی نتایج
            self.assertIsNotNone(tz)
            
            # بررسی فراخوانی‌های توابع
            mock_get_from_registry.assert_called_once()
    
    def test_localize_datetime_windows(self):
        """
        تست اضافه کردن منطقه زمانی به تاریخ و زمان در ویندوز
        """
        # تاریخ و زمان بدون منطقه زمانی
        naive_dt = datetime.datetime(2023, 5, 15, 10, 30, 0)
        
        # افزودن منطقه زمانی تهران
        localized_dt = localize_datetime(naive_dt, self.tehran_tz)
        
        # بررسی نتایج
        self.assertEqual(localized_dt.tzinfo, self.tehran_tz)
        self.assertEqual(localized_dt.year, naive_dt.year)
        self.assertEqual(localized_dt.month, naive_dt.month)
        self.assertEqual(localized_dt.day, naive_dt.day)
        self.assertEqual(localized_dt.hour, naive_dt.hour)
        self.assertEqual(localized_dt.minute, naive_dt.minute)

 
if __name__ == '__main__':
    unittest.main()