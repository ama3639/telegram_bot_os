#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
تست‌های مربوط به API‌های خارجی

این ماژول شامل تست‌های یکپارچگی با API‌های خارجی مانند صرافی‌ها و سرویس‌های ارز است.
"""

import os
import sys
import unittest
import json
import time
import datetime
import requests
from unittest import mock
from unittest.mock import patch, MagicMock

# افزودن مسیر ریشه پروژه به sys.path برای واردسازی ماژول‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.base import BaseAPI
from src.api.exchanges.binance import BinanceAPI
from src.api.live_price import LivePriceAPI
from src.utils.cache import Cache
from src.core.config import Config


class TestBaseAPI(unittest.TestCase):
    """
    تست کلاس پایه API
    """
    
    def setUp(self):
        """
        تنظیمات اولیه قبل از هر تست
        """
        self.api = BaseAPI()
        self.api.base_url = 'https://api.example.com'
        self.api.timeout = 10
        self.api.max_retries = 3
    
    def tearDown(self):
        """
        پاکسازی بعد از هر تست
        """
        pass
    
    def test_init(self):
        """
        تست سازنده کلاس
        """
        self.assertEqual(self.api.base_url, 'https://api.example.com')
        self.assertEqual(self.api.timeout, 10)
        self.assertEqual(self.api.max_retries, 3)
    
    @patch('requests.Session.get')
    def test_get_request(self, mock_get):
        """
        تست متد get
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'result': 'success'}
        mock_get.return_value = mock_response
        
        # فراخوانی متد
        response = self.api.get('/test', params={'param1': 'value1'})
        
        # بررسی نتایج
        self.assertEqual(response, {'result': 'success'})
        mock_get.assert_called_with(
            'https://api.example.com/test',
            params={'param1': 'value1'},
            headers=None,
            timeout=10
        )
    
    @patch('requests.Session.post')
    def test_post_request(self, mock_post):
        """
        تست متد post
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'result': 'success'}
        mock_post.return_value = mock_response
        
        # فراخوانی متد
        response = self.api.post('/test', data={'data1': 'value1'})
        
        # بررسی نتایج
        self.assertEqual(response, {'result': 'success'})
        mock_post.assert_called_with(
            'https://api.example.com/test',
            json={'data1': 'value1'},
            headers=None,
            timeout=10
        )
    
    @patch('requests.Session.get')
    def test_connection_error(self, mock_get):
        """
        تست مدیریت خطاهای اتصال
        """
        # تنظیم mock برای شبیه‌سازی خطای اتصال
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection error")
        
        # بررسی مدیریت خطا
        with self.assertRaises(requests.exceptions.ConnectionError):
            self.api.get('/test')
    
    @patch('requests.Session.get')
    def test_timeout_error(self, mock_get):
        """
        تست مدیریت خطاهای timeout
        """
        # تنظیم mock برای شبیه‌سازی خطای timeout
        mock_get.side_effect = requests.exceptions.Timeout("Timeout error")
        
        # بررسی مدیریت خطا
        with self.assertRaises(requests.exceptions.Timeout):
            self.api.get('/test')
    
    @patch('time.sleep', return_value=None)
    @patch('requests.Session.get')
    def test_retry_mechanism(self, mock_get, mock_sleep):
        """
        تست مکانیزم تلاش مجدد در صورت خطا
        """
        # تنظیم mock برای شبیه‌سازی خطا در دو تلاش اول و موفقیت در تلاش سوم
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'result': 'success'}
        
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Connection error"),
            requests.exceptions.ConnectionError("Connection error"),
            mock_response_success
        ]
        
        # فعال کردن تلاش مجدد
        self.api.enable_retries = True
        
        # فراخوانی متد
        response = self.api.get('/test', retry_on_error=True)
        
        # بررسی نتایج
        self.assertEqual(response, {'result': 'success'})
        self.assertEqual(mock_get.call_count, 3)  # تلاش سه بار


class TestBinanceAPI(unittest.TestCase):
    """
    تست API صرافی بایننس
    """
    
    def setUp(self):
        """
        تنظیمات اولیه قبل از هر تست
        """
        self.api = BinanceAPI()
    
    def tearDown(self):
        """
        پاکسازی بعد از هر تست
        """
        pass
    
    @patch('src.api.exchanges.binance.BinanceAPI.get')
    def test_get_ticker(self, mock_get):
        """
        تست دریافت قیمت لحظه‌ای
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API
        mock_get.return_value = {
            "symbol": "BTCUSDT",
            "price": "45123.45"
        }
        
        # فراخوانی متد
        ticker = self.api.get_ticker("BTCUSDT")
        
        # بررسی نتایج
        self.assertEqual(ticker['symbol'], "BTCUSDT")
        self.assertEqual(ticker['price'], "45123.45")
        mock_get.assert_called_with('/api/v3/ticker/price', params={'symbol': 'BTCUSDT'})
    
    @patch('src.api.exchanges.binance.BinanceAPI.get')
    def test_get_order_book(self, mock_get):
        """
        تست دریافت دفتر سفارشات
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API
        mock_response = {
            "lastUpdateId": 1027024,
            "bids": [
                ["45000.00", "1.50000000"],
                ["44999.00", "0.50000000"]
            ],
            "asks": [
                ["45001.00", "2.00000000"],
                ["45002.00", "1.00000000"]
            ]
        }
        mock_get.return_value = mock_response
        
        # فراخوانی متد
        order_book = self.api.get_order_book("BTCUSDT", limit=5)
        
        # بررسی نتایج
        self.assertEqual(order_book, mock_response)
        mock_get.assert_called_with('/api/v3/depth', params={'symbol': 'BTCUSDT', 'limit': 5})
    
    @patch('src.api.exchanges.binance.BinanceAPI.get')
    def test_get_klines(self, mock_get):
        """
        تست دریافت داده‌های کندل
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API
        mock_response = [
            [
                1499040000000,      # Open time
                "45000.00000000",   # Open
                "45100.00000000",   # High
                "44900.00000000",   # Low
                "45050.00000000",   # Close
                "1000.00000000",    # Volume
                1499644799999,      # Close time
                "45050000.00000000" # Quote asset volume
            ]
        ]
        mock_get.return_value = mock_response
        
        # فراخوانی متد
        klines = self.api.get_klines("BTCUSDT", interval="1h", limit=1)
        
        # بررسی نتایج
        self.assertEqual(klines, mock_response)
        mock_get.assert_called_with('/api/v3/klines', params={
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'limit': 1
        })


class TestLivePriceAPI(unittest.TestCase):
    """
    تست API قیمت‌های زنده
    """
    
    def setUp(self):
        """
        تنظیمات اولیه قبل از هر تست
        """
        self.api = LivePriceAPI()
        self.cache = Cache()
    
    def tearDown(self):
        """
        پاکسازی بعد از هر تست
        """
        # پاکسازی کش
        self.cache.clear()
    
    @patch('src.api.exchanges.binance.BinanceAPI.get_ticker')
    def test_get_live_price(self, mock_get_ticker):
        """
        تست دریافت قیمت زنده
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API بایننس
        mock_get_ticker.return_value = {
            "symbol": "BTCUSDT",
            "price": "45123.45"
        }
        
        # فراخوانی متد
        price = self.api.get_live_price("BTC", "USDT")
        
        # بررسی نتایج
        self.assertEqual(price, 45123.45)
        mock_get_ticker.assert_called_with("BTCUSDT")
    
    @patch('src.api.exchanges.binance.BinanceAPI.get_ticker')
    def test_get_live_price_with_cache(self, mock_get_ticker):
        """
        تست کش کردن قیمت‌های زنده
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API بایننس
        mock_get_ticker.return_value = {
            "symbol": "BTCUSDT",
            "price": "45123.45"
        }
        
        # فعال کردن کش
        self.api.use_cache = True
        self.api.cache_ttl = 60  # 60 ثانیه
        
        # فراخوانی متد بار اول
        price1 = self.api.get_live_price("BTC", "USDT")
        
        # تغییر مقدار mock برای تست کش
        mock_get_ticker.return_value = {
            "symbol": "BTCUSDT",
            "price": "45500.00"
        }
        
        # فراخوانی متد بار دوم (باید از کش برگردد)
        price2 = self.api.get_live_price("BTC", "USDT")
        
        # بررسی نتایج
        self.assertEqual(price1, 45123.45)
        self.assertEqual(price2, 45123.45)  # باید همان مقدار قبلی برگردد
        self.assertEqual(mock_get_ticker.call_count, 1)  # تنها یک بار فراخوانی شود
    
    @patch('src.api.exchanges.binance.BinanceAPI.get_ticker')
    def test_get_multiple_prices(self, mock_get_ticker):
        """
        تست دریافت چندین قیمت همزمان
        """
        # تنظیم mock برای شبیه‌سازی پاسخ‌های مختلف API
        mock_get_ticker.side_effect = [
            {"symbol": "BTCUSDT", "price": "45123.45"},
            {"symbol": "ETHUSDT", "price": "3000.00"},
            {"symbol": "BNBUSDT", "price": "500.00"}
        ]
        
        # فراخوانی متد
        prices = self.api.get_multiple_prices(
            [("BTC", "USDT"), ("ETH", "USDT"), ("BNB", "USDT")]
        )
        
        # بررسی نتایج
        expected = {
            "BTC/USDT": 45123.45,
            "ETH/USDT": 3000.00,
            "BNB/USDT": 500.00
        }
        self.assertEqual(prices, expected)
        self.assertEqual(mock_get_ticker.call_count, 3)
    
    @patch('src.api.exchanges.binance.BinanceAPI.get_ticker')
    def test_get_live_price_error_handling(self, mock_get_ticker):
        """
        تست مدیریت خطا در دریافت قیمت زنده
        """
        # تنظیم mock برای شبیه‌سازی خطا
        mock_get_ticker.side_effect = Exception("API Error")
        
        # بررسی مدیریت خطا
        with self.assertRaises(Exception):
            self.api.get_live_price("BTC", "USDT")


if __name__ == '__main__':
    unittest.main() 