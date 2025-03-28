#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
تست‌های یکپارچگی سیستم پرداخت

این ماژول شامل تست‌های یکپارچگی بین قسمت‌های مختلف سیستم پرداخت است،
از جمله رابط کاربری، پردازش پرداخت، مدیریت اشتراک و... 
"""

import os
import sys
import unittest
import json
import time
import datetime
from src.utils.timezone_utils import get_current_datetime
from decimal import Decimal
import uuid
from unittest import mock
from unittest.mock import patch, MagicMock, PropertyMock

# افزودن مسیر ریشه پروژه به sys.path برای واردسازی ماژول‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.handlers.payment_handlers import (
    PaymentHandler,
    process_payment,
    create_payment_invoice,
    verify_payment
)
from src.utils.crypto_payment import BinancePayProvider, TronProvider
from src.models.payment import Payment
from src.models.subscription import Subscription
from src.models.user import User
from src.accounting.ledger import Ledger
from src.core.config import Config
from src.core.database import Database
 

class MockDatabase:
    """
    کلاس مجازی برای شبیه‌سازی پایگاه داده
    """
    
    def __init__(self):
        """
        مقداردهی اولیه
        """
        self.payments = {}
        self.subscriptions = {}
        self.users = {}
        self.transactions = []
    
    def save_payment(self, payment):
        """
        ذخیره پرداخت در پایگاه داده
        """
        self.payments[payment.id] = payment
        return payment
    
    def get_payment(self, payment_id):
        """
        دریافت پرداخت از پایگاه داده
        """
        return self.payments.get(payment_id)
    
    def update_payment(self, payment):
        """
        به‌روزرسانی پرداخت در پایگاه داده
        """
        self.payments[payment.id] = payment
        return payment
    
    def save_subscription(self, subscription):
        """
        ذخیره اشتراک در پایگاه داده
        """
        self.subscriptions[subscription.id] = subscription
        return subscription
    
    def get_user(self, user_id):
        """
        دریافت کاربر از پایگاه داده
        """
        return self.users.get(user_id)
    
    def record_transaction(self, transaction):
        """
        ثبت تراکنش در پایگاه داده
        """
        self.transactions.append(transaction)
        return transaction


class TestPaymentIntegration(unittest.TestCase):
    """
    تست یکپارچگی سیستم پرداخت
    """
    
    def setUp(self):
        """
        تنظیمات اولیه قبل از هر تست
        """
        # ایجاد نمونه مجازی از پایگاه داده
        self.mock_db = MockDatabase()
        
        # ایجاد کاربر آزمایشی
        self.test_user = User(
            id=123456,
            username="test_user",
            first_name="Test",
            last_name="User",
            is_premium=False
        )
        self.mock_db.users[self.test_user.id] = self.test_user
        
        # ایجاد نمونه از هندلر پرداخت
        self.payment_handler = PaymentHandler(db=self.mock_db)
        
        # پچ کردن کلاس Database
        self.db_patcher = patch('src.core.database.Database')
        self.mock_db_class = self.db_patcher.start()
        self.mock_db_class.return_value = self.mock_db
        
        # پچ کردن کلاس Ledger
        self.ledger_patcher = patch('src.accounting.ledger.Ledger')
        self.mock_ledger_class = self.ledger_patcher.start()
        self.mock_ledger = MagicMock()
        self.mock_ledger_class.return_value = self.mock_ledger
    
    def tearDown(self):
        """
        پاکسازی بعد از هر تست
        """
        # خاتمه تمام پچ‌ها
        self.db_patcher.stop()
        self.ledger_patcher.stop()
    
    @patch('src.utils.crypto_payment.BinancePayProvider.create_payment')
    def test_create_payment_invoice(self, mock_create_payment):
        """
        تست ایجاد صورت‌حساب پرداخت
        """
        # تنظیم mock برای شبیه‌سازی ایجاد پرداخت
        payment_id = str(uuid.uuid4())
        mock_create_payment.return_value = {
            "status": "SUCCESS",
            "code": "000000",
            "data": {
                "prepayId": payment_id,
                "terminalType": "WEB",
                "expireTime": int(time.time() * 1000) + 3600000,
                "qrcodeLink": f"https://qrcode.example.com/{payment_id}",
                "checkoutUrl": f"https://checkout.example.com/{payment_id}",
                "qrContent": f"binance://pay?prepayId={payment_id}",
                "universalUrl": f"https://universalurl.example.com/{payment_id}"
            }
        }
        
        # فراخوانی تابع
        invoice = create_payment_invoice(
            user_id=self.test_user.id,
            amount=100,
            currency="USDT",
            payment_method="crypto",
            provider="binance",
            subscription_type="premium_monthly"
        )
        
        # بررسی نتایج
        self.assertEqual(invoice["status"], "SUCCESS")
        self.assertEqual(invoice["data"]["prepayId"], payment_id)
        
        # بررسی ذخیره پرداخت در پایگاه داده
        saved_payment = self.mock_db.payments.get(payment_id)
        self.assertIsNotNone(saved_payment)
        self.assertEqual(saved_payment.user_id, self.test_user.id)
        self.assertEqual(saved_payment.amount, 100)
        self.assertEqual(saved_payment.currency, "USDT")
        self.assertEqual(saved_payment.status, "pending")
    
    @patch('src.utils.crypto_payment.BinancePayProvider.check_payment')
    def test_verify_payment(self, mock_check_payment):
        """
        تست تایید پرداخت
        """
        # ایجاد یک پرداخت آزمایشی در پایگاه داده
        payment_id = str(uuid.uuid4())
        payment = Payment(
            id=payment_id,
            user_id=self.test_user.id,
            amount=100,
            currency="USDT",
            payment_method="crypto",
            provider="binance",
            status="pending",
            created_at=datetime.get_current_datetime().isoformat()
        )
        self.mock_db.payments[payment_id] = payment
        
        # تنظیم mock برای شبیه‌سازی بررسی پرداخت
        mock_check_payment.return_value = {
            "status": "SUCCESS",
            "code": "000000",
            "data": {
                "merchantTradeNo": "order_123456",
                "prepayId": payment_id,
                "status": "PAID",
                "transactionId": "9182736451",
                "currency": "USDT",
                "totalFee": "100.00",
                "openUserId": "user_83736452",
                "createTime": int(time.time() * 1000) - 60000,
                "updateTime": int(time.time() * 1000)
            }
        }
        
        # فراخوانی تابع
        result = verify_payment(payment_id)
        
        # بررسی نتایج
        self.assertTrue(result["success"])
        self.assertEqual(result["payment_id"], payment_id)
        self.assertEqual(result["status"], "completed")
        
        # بررسی به‌روزرسانی پرداخت در پایگاه داده
        updated_payment = self.mock_db.payments.get(payment_id)
        self.assertEqual(updated_payment.status, "completed")
        
        # بررسی ثبت تراکنش در دفتر کل
        self.mock_ledger.record_payment.assert_called_once()
        args, kwargs = self.mock_ledger.record_payment.call_args
        self.assertEqual(args[0].id, payment_id)
    
    @patch('src.utils.crypto_payment.BinancePayProvider.create_payment')
    @patch('src.utils.crypto_payment.BinancePayProvider.check_payment')
    def test_complete_payment_flow(self, mock_check_payment, mock_create_payment):
        """
        تست کامل جریان پرداخت از ایجاد تا تایید
        """
        # تنظیم mock برای شبیه‌سازی ایجاد پرداخت
        payment_id = str(uuid.uuid4())
        mock_create_payment.return_value = {
            "status": "SUCCESS",
            "code": "000000",
            "data": {
                "prepayId": payment_id,
                "terminalType": "WEB",
                "expireTime": int(time.time() * 1000) + 3600000,
                "qrcodeLink": f"https://qrcode.example.com/{payment_id}",
                "checkoutUrl": f"https://checkout.example.com/{payment_id}",
                "qrContent": f"binance://pay?prepayId={payment_id}",
                "universalUrl": f"https://universalurl.example.com/{payment_id}"
            }
        }
        
        # ایجاد صورت‌حساب پرداخت
        invoice = create_payment_invoice(
            user_id=self.test_user.id,
            amount=100,
            currency="USDT",
            payment_method="crypto",
            provider="binance",
            subscription_type="premium_monthly"
        )
        
        # تنظیم mock برای شبیه‌سازی بررسی پرداخت
        mock_check_payment.return_value = {
            "status": "SUCCESS",
            "code": "000000",
            "data": {
                "merchantTradeNo": "order_123456",
                "prepayId": payment_id,
                "status": "PAID",
                "transactionId": "9182736451",
                "currency": "USDT",
                "totalFee": "100.00",
                "openUserId": "user_83736452",
                "createTime": int(time.time() * 1000) - 60000,
                "updateTime": int(time.time() * 1000)
            }
        }
        
        # تایید پرداخت
        result = verify_payment(payment_id)
        
        # بررسی نتایج
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "completed")
        
        # بررسی به‌روزرسانی پرداخت در پایگاه داده
        updated_payment = self.mock_db.payments.get(payment_id)
        self.assertEqual(updated_payment.status, "completed")
    
    @patch('src.handlers.payment_handlers.create_payment_invoice')
    @patch('src.handlers.payment_handlers.verify_payment')
    @patch('src.models.subscription.Subscription.activate')
    def test_process_payment_and_subscription(self, mock_activate, mock_verify, mock_create):
        """
        تست پردازش پرداخت و فعال‌سازی اشتراک
        """
        # تنظیم mock برای شبیه‌سازی ایجاد پرداخت
        payment_id = str(uuid.uuid4())
        mock_create.return_value = {
            "success": True,
            "payment_id": payment_id,
            "checkout_url": f"https://checkout.example.com/{payment_id}"
        }
        
        # تنظیم mock برای شبیه‌سازی تایید پرداخت
        mock_verify.return_value = {
            "success": True,
            "payment_id": payment_id,
            "status": "completed"
        }
        
        # تنظیم mock برای فعال‌سازی اشتراک
        subscription_id = str(uuid.uuid4())
        mock_activate.return_value = {
            "success": True,
            "subscription_id": subscription_id,
            "status": "active",
            "expires_at": (datetime.get_current_datetime() + datetime.timedelta(days=30)).isoformat()
        }
        
        # فراخوانی تابع پردازش پرداخت
        result = process_payment(
            user_id=self.test_user.id,
            amount=100,
            currency="USDT",
            payment_method="crypto",
            provider="binance",
            subscription_type="premium_monthly"
        )
        
        # بررسی نتایج
        self.assertTrue(result["success"])
        self.assertEqual(result["payment_id"], payment_id)
        self.assertEqual(result["subscription_id"], subscription_id)
        self.assertEqual(result["status"], "completed")
        
        # بررسی فراخوانی تابع‌های مختلف
        mock_create.assert_called_once()
        mock_verify.assert_called_once_with(payment_id)
        mock_activate.assert_called_once()


class TestSubscriptionIntegration(unittest.TestCase):
    """
    تست یکپارچگی اشتراک با سیستم پرداخت
    """
    
    def setUp(self):
        """
        تنظیمات اولیه قبل از هر تست
        """
        # ایجاد نمونه مجازی از پایگاه داده
        self.mock_db = MockDatabase()
        
        # ایجاد کاربر آزمایشی
        self.test_user = User(
            id=123456,
            username="test_user",
            first_name="Test",
            last_name="User",
            is_premium=False
        )
        self.mock_db.users[self.test_user.id] = self.test_user
        
        # پچ کردن کلاس Database
        self.db_patcher = patch('src.core.database.Database')
        self.mock_db_class = self.db_patcher.start()
        self.mock_db_class.return_value = self.mock_db
        
        # پچ کردن کلاس User
        self.user_patcher = patch('src.models.user.User')
        self.mock_user_class = self.user_patcher.start()
        self.mock_user_class.get.return_value = self.test_user
    
    def tearDown(self):
        """
        پاکسازی بعد از هر تست
        """
        # خاتمه تمام پچ‌ها
        self.db_patcher.stop()
        self.user_patcher.stop()
    
    def test_create_and_activate_subscription(self):
        """
        تست ایجاد و فعال‌سازی اشتراک
        """
        # ایجاد یک پرداخت تکمیل شده
        payment_id = str(uuid.uuid4())
        payment = Payment(
            id=payment_id,
            user_id=self.test_user.id,
            amount=100,
            currency="USDT",
            payment_method="crypto",
            provider="binance",
            status="completed",
            created_at=datetime.get_current_datetime().isoformat()
        )
        self.mock_db.payments[payment_id] = payment
        
        # ایجاد اشتراک
        subscription = Subscription(
            id=str(uuid.uuid4()),
            user_id=self.test_user.id,
            plan_type="premium_monthly",
            status="pending",
            payment_id=payment_id,
            created_at=datetime.get_current_datetime().isoformat()
        )
        
        # فعال‌سازی اشتراک
        with patch.object(self.test_user, 'update_premium_status') as mock_update:
            result = subscription.activate()
        
        # بررسی نتایج
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "active")
        
        # بررسی به‌روزرسانی وضعیت کاربر
        mock_update.assert_called_once_with(True)
    
    def test_subscription_expiration(self):
        """
        تست انقضای اشتراک
        """
        # ایجاد یک اشتراک فعال
        subscription_id = str(uuid.uuid4())
        now = datetime.get_current_datetime()
        yesterday = now - datetime.timedelta(days=1)
        
        subscription = Subscription(
            id=subscription_id,
            user_id=self.test_user.id,
            plan_type="premium_monthly",
            status="active",
            start_date=yesterday.isoformat(),
            end_date=yesterday.isoformat(),  # منقضی شده
            created_at=yesterday.isoformat()
        )
        self.mock_db.subscriptions[subscription_id] = subscription
        
        # بررسی وضعیت اشتراک
        with patch.object(self.test_user, 'update_premium_status') as mock_update:
            is_active = subscription.is_active()
            if not is_active:
                subscription.expire()
        
        # بررسی نتایج
        self.assertFalse(is_active)
        self.assertEqual(subscription.status, "expired")
        
        # بررسی به‌روزرسانی وضعیت کاربر
        mock_update.assert_called_once_with(False)
    
    def test_subscription_renewal(self):
        """
        تست تمدید اشتراک
        """
        # ایجاد یک اشتراک فعال
        subscription_id = str(uuid.uuid4())
        now = datetime.get_current_datetime()
        start_date = now - datetime.timedelta(days=29)
        end_date = now + datetime.timedelta(days=1)  # درحال منقضی شدن
        
        subscription = Subscription(
            id=subscription_id,
            user_id=self.test_user.id,
            plan_type="premium_monthly",
            status="active",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            created_at=start_date.isoformat()
        )
        self.mock_db.subscriptions[subscription_id] = subscription
        
        # ایجاد یک پرداخت جدید برای تمدید
        payment_id = str(uuid.uuid4())
        payment = Payment(
            id=payment_id,
            user_id=self.test_user.id,
            amount=100,
            currency="USDT",
            payment_method="crypto",
            provider="binance",
            status="completed",
            created_at=now.isoformat()
        )
        self.mock_db.payments[payment_id] = payment
        
        # تمدید اشتراک
        with patch.object(Subscription, 'save_to_d') as mock_save:
            result = subscription.renew(payment_id)
        
        # Ø¨Ø±Ø±Ø³Û ÙØªØ§ÛØ¬
        self.assertTrue(result["success"])
        
        # Ø¨Ø±Ø±Ø³Û ØªØºÛÛØ± ØªØ§Ø±ÛØ® Ø§ÙÙØ¶Ø§
        new_end_date = now + datetime.timedelta(days=31)  # 30 Ø±ÙØ² + 1 Ø±ÙØ² Ø¨Ø§ÙÛÙØ§ÙØ¯Ù
        self.assertAlmostEqual(
            datetime.datetime.fromisoformat(subscription.end_date).timestamp(),
            new_end_date.timestamp(),
            delta=60  # Ø§Ø®ØªÙØ§Ù Ú©ÙØªØ± Ø§Ø² 1 Ø¯ÙÛÙÙ ÙØ§Ø¨Ù ÙØ¨ÙÙ Ø§Ø³Øª
        )
        
        # Ø¨Ø±Ø±Ø³Û Ø°Ø®ÛØ±Ù ØªØºÛÛØ±Ø§Øª
        mock_save.assert_called_once()


if __name__ == '__main__':
    unittest.main()