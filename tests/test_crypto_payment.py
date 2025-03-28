#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
تست‌های مربوط به سیستم پرداخت رمزارزی

این ماژول شامل تست‌های مختلف برای بررسی عملکرد صحیح سیستم پرداخت رمزارزی است.
"""

import os
import sys
import unittest
import json
import time
import datetime
import uuid
from unittest import mock
from unittest.mock import patch, MagicMock, PropertyMock

# افزودن مسیر ریشه پروژه به sys.path برای واردسازی ماژول‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.crypto_payment import (
    CryptoPaymentProvider,
    TronProvider,
    BinancePayProvider,
    BitkhabProvider,
    generate_payment_address,
    verify_transaction,
    calculate_crypto_amount
)
from src.core.config import Config


class TestCryptoPaymentProvider(unittest.TestCase):
    """
    تست کلاس پایه ارائه‌دهنده پرداخت رمزارزی
    """
    
    def setUp(self):
        """
        تنظیمات اولیه قبل از هر تست
        """
        # ایجاد نمونه از کلاس پایه
        self.provider = CryptoPaymentProvider(
            api_key="test_key",
            api_secret="test_secret",
            network="TRON"
        )
    
    def test_init(self): 
        """
        تست سازنده کلاس
        """
        self.assertEqual(self.provider.api_key, "test_key")
        self.assertEqual(self.provider.api_secret, "test_secret")
        self.assertEqual(self.provider.network, "TRON")
    
    def test_abstract_methods(self):
        """
        تست متدهای انتزاعی
        """
        # این متدها در کلاس پایه انتزاعی هستند و باید پیاده‌سازی شوند
        with self.assertRaises(NotImplementedError):
            self.provider.create_payment(amount=100, currency="USDT")
        
        with self.assertRaises(NotImplementedError):
            self.provider.check_payment(payment_id="payment123")
        
        with self.assertRaises(NotImplementedError):
            self.provider.get_payment_address(payment_id="payment123")


class TestTronProvider(unittest.TestCase):
    """
    تست ارائه‌دهنده پرداخت شبکه ترون
    """
    
    def setUp(self):
        """
        تنظیمات اولیه قبل از هر تست
        """
        self.provider = TronProvider(
            api_key="tron_api_key",
            api_secret="tron_api_secret",
            wallet_address="TXyzAbc123",
            contract_address="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"  # USDT contract
        )
    
    @patch('requests.post')
    def test_create_payment(self, mock_post):
        """
        تست ایجاد پرداخت در شبکه ترون
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "payment_id": "tron_payment_123",
            "address": "TXyzAbc123",
            "amount": "100.00",
            "currency": "USDT",
            "expires_at": int(time.time()) + 3600
        }
        mock_post.return_value = mock_response
        
        # فراخوانی متد
        payment = self.provider.create_payment(amount=100, currency="USDT")
        
        # بررسی نتایج
        self.assertTrue(payment["success"])
        self.assertEqual(payment["payment_id"], "tron_payment_123")
        self.assertEqual(payment["address"], "TXyzAbc123")
        
        # بررسی پارامترهای ارسالی به API
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["amount"], 100)
        self.assertEqual(kwargs["json"]["currency"], "USDT")
    
    @patch('requests.get')
    def test_check_payment(self, mock_get):
        """
        تست بررسی وضعیت پرداخت
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API در وضعیت پرداخت موفق
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "payment_id": "tron_payment_123",
            "status": "completed",
            "amount": "100.00",
            "received_amount": "100.00",
            "transaction_id": "0x1234567890abcdef",
            "completed_at": int(time.time())
        }
        mock_get.return_value = mock_response
        
        # فراخوانی متد
        payment_status = self.provider.check_payment(payment_id="tron_payment_123")
        
        # بررسی نتایج
        self.assertTrue(payment_status["success"])
        self.assertEqual(payment_status["status"], "completed")
        self.assertEqual(payment_status["payment_id"], "tron_payment_123")
        
        # بررسی پارامترهای ارسالی به API
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn("tron_payment_123", args[0])
    
    @patch('src.utils.crypto_payment.TronProvider.create_payment')
    def test_get_payment_address(self, mock_create_payment):
        """
        تست دریافت آدرس پرداخت
        """
        # تنظیم mock برای شبیه‌سازی پاسخ متد create_payment
        mock_create_payment.return_value = {
            "success": True,
            "payment_id": "tron_payment_123",
            "address": "TXyzAbc123",
            "amount": "100.00",
            "currency": "USDT"
        }
        
        # فراخوانی متد
        address = self.provider.get_payment_address(payment_id="tron_payment_123")
        
        # بررسی نتایج
        self.assertEqual(address, "TXyzAbc123")


class TestBinancePayProvider(unittest.TestCase):
    """
    تست ارائه‌دهنده پرداخت بایننس پی
    """
    
    def setUp(self):
        """
        تنظیمات اولیه قبل از هر تست
        """
        self.provider = BinancePayProvider(
            api_key="binance_api_key",
            api_secret="binance_api_secret",
            merchant_id="123456"
        )
    
    @patch('requests.post')
    def test_create_payment(self, mock_post):
        """
        تست ایجاد پرداخت در بایننس پی
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "SUCCESS",
            "code": "000000",
            "data": {
                "prepayId": "29383937493",
                "terminalType": "WEB",
                "expireTime": int(time.time() * 1000) + 3600000,
                "qrcodeLink": "https://qrcode.example.com/29383937493",
                "checkoutUrl": "https://checkout.example.com/29383937493",
                "qrContent": "binance://pay?prepayId=29383937493",
                "universalUrl": "https://universalurl.example.com/29383937493"
            }
        }
        mock_post.return_value = mock_response
        
        # فراخوانی متد
        payment = self.provider.create_payment(amount=100, currency="USDT")
        
        # بررسی نتایج
        self.assertEqual(payment["status"], "SUCCESS")
        self.assertEqual(payment["data"]["prepayId"], "29383937493")
        
        # بررسی پارامترهای ارسالی به API
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        request_data = kwargs["json"]
        self.assertEqual(request_data["merchantTradeNo"], request_data["merchantTradeNo"])  # باید یک شناسه منحصر به فرد باشد
        self.assertEqual(request_data["totalFee"], "100.00")
        self.assertEqual(request_data["currency"], "USDT")
    
    @patch('requests.post')
    def test_check_payment(self, mock_post):
        """
        تست بررسی وضعیت پرداخت در بایننس پی
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "SUCCESS",
            "code": "000000",
            "data": {
                "merchantTradeNo": "order_123456",
                "prepayId": "29383937493",
                "status": "PAID",
                "transactionId": "9182736451",
                "currency": "USDT",
                "totalFee": "100.00",
                "openUserId": "user_83736452",
                "createTime": int(time.time() * 1000) - 60000,
                "updateTime": int(time.time() * 1000)
            }
        }
        mock_post.return_value = mock_response
        
        # فراخوانی متد
        payment_status = self.provider.check_payment(payment_id="29383937493")
        
        # بررسی نتایج
        self.assertEqual(payment_status["status"], "SUCCESS")
        self.assertEqual(payment_status["data"]["status"], "PAID")
        
        # بررسی پارامترهای ارسالی به API
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["prepayId"], "29383937493")


class TestBitkhabProvider(unittest.TestCase):
    """
    تست ارائه‌دهنده پرداخت بیت‌خب
    """
    
    def setUp(self):
        """
        تنظیمات اولیه قبل از هر تست
        """
        self.provider = BitkhabProvider(
            api_key="bitkhab_api_key",
            api_secret="bitkhab_api_secret",
            merchant_id="bitkhab_merchant"
        )
    
    @patch('requests.post')
    def test_create_payment(self, mock_post):
        """
        تست ایجاد پرداخت در بیت‌خب
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "id": "bitkhab_payment_123",
            "amount": 100,
            "currency": "toman",
            "crypto_amount": 2.5,
            "crypto_currency": "USDT",
            "wallet_address": "TS7FgcXqf9nfM5gT2zXNya",
            "payment_url": "https://bitkhab.io/pay/bitkhab_payment_123",
            "status": "pending",
            "expires_at": int(time.time()) + 3600
        }
        mock_post.return_value = mock_response
        
        # فراخوانی متد
        payment = self.provider.create_payment(amount=100, currency="IRR")
        
        # بررسی نتایج
        self.assertTrue(payment["success"])
        self.assertEqual(payment["id"], "bitkhab_payment_123")
        self.assertEqual(payment["wallet_address"], "TS7FgcXqf9nfM5gT2zXNya")
        
        # بررسی پارامترهای ارسالی به API
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["amount"], 100)
        self.assertEqual(kwargs["json"]["currency"], "IRR")
    
    @patch('requests.get')
    def test_check_payment(self, mock_get):
        """
        تست بررسی وضعیت پرداخت در بیت‌خب
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "id": "bitkhab_payment_123",
            "status": "completed",
            "transaction_hash": "0xabcdef1234567890",
            "completed_at": int(time.time())
        }
        mock_get.return_value = mock_response
        
        # فراخوانی متد
        payment_status = self.provider.check_payment(payment_id="bitkhab_payment_123")
        
        # بررسی نتایج
        self.assertTrue(payment_status["success"])
        self.assertEqual(payment_status["status"], "completed")
        
        # بررسی پارامترهای ارسالی به API
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn("bitkhab_payment_123", args[0])
    
    @patch('src.utils.crypto_payment.BitkhabProvider.check_payment')
    def test_confirm_payment(self, mock_check_payment):
        """
        تست تایید پرداخت
        """
        # تنظیم mock برای شبیه‌سازی پاسخ متد check_payment
        mock_check_payment.return_value = {
            "success": True,
            "id": "bitkhab_payment_123",
            "status": "completed",
            "transaction_hash": "0xabcdef1234567890"
        }
        
        # فراخوانی متد
        result = self.provider.confirm_payment("bitkhab_payment_123", "0xabcdef1234567890")
        
        # بررسی نتایج
        self.assertTrue(result)
        mock_check_payment.assert_called_once_with("bitkhab_payment_123")


class TestUtilityFunctions(unittest.TestCase):
    """
    تست توابع کمکی
    """
    
    def test_generate_payment_address(self):
        """
        تست تابع تولید آدرس پرداخت
        """
        # فراخوانی تابع برای شبکه‌های مختلف
        tron_address = generate_payment_address("TRON")
        eth_address = generate_payment_address("ETH")
        btc_address = generate_payment_address("BTC")
        
        # بررسی فرمت آدرس‌ها
        self.assertTrue(tron_address.startswith('T'))
        self.assertTrue(eth_address.startswith('0x'))
        self.assertTrue(btc_address.startswith('1') or btc_address.startswith('3') or btc_address.startswith('bc1'))
    
    @patch('requests.get')
    def test_verify_transaction(self, mock_get):
        """
        تست تابع تایید تراکنش
        """
        # تنظیم mock برای شبیه‌سازی پاسخ API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "transaction": {
                "hash": "0x1234567890abcdef",
                "from": "TXyzAbc123",
                "to": "TReceiver456",
                "value": "100.00",
                "confirmations": 12,
                "timestamp": int(time.time())
            }
        }
        mock_get.return_value = mock_response
        
        # فراخوانی تابع
        result = verify_transaction(
            tx_hash="0x1234567890abcdef",
            network="TRON",
            expected_amount=100.0,
            recipient_address="TReceiver456"
        )
        
        # بررسی نتایج
        self.assertTrue(result["verified"])
        self.assertEqual(result["transaction"]["hash"], "0x1234567890abcdef")
        
        # بررسی فراخوانی API
        mock_get.assert_called_once()
    
    @patch('src.api.live_price.LivePriceAPI.get_live_price')
    def test_calculate_crypto_amount(self, mock_get_live_price):
        """
        تست تابع محاسبه مقدار ارز دیجیتال
        """
        # تنظیم mock برای قیمت ارز
        mock_get_live_price.return_value = 45000.0  # قیمت BTC به USD
        
        # فراخوانی تابع (محاسبه مقدار BTC معادل 1000 USD)
        crypto_amount = calculate_crypto_amount(
            fiat_amount=1000,
            fiat_currency="USD",
            crypto_currency="BTC"
        )
        
        # بررسی نتایج (1000 USD معادل 0.02222... BTC با قیمت 45000 USD)
        expected_amount = 1000 / 45000
        self.assertAlmostEqual(crypto_amount, expected_amount)
        
        # بررسی فراخوانی API
        mock_get_live_price.assert_called_once_with("BTC", "USD")


if __name__ == '__main__':
    unittest.main()