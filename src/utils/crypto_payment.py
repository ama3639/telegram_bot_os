#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول پرداخت‌های رمزارزی

این ماژول شامل توابع و کلاس‌های مورد نیاز برای مدیریت پرداخت‌های رمزارزی،
تولید آدرس کیف پول، بررسی وضعیت تراکنش‌ها و ارتباط با API‌های رمزارزی است.
"""

import os
import json
import time
import hashlib
import uuid
import hmac
import base64
import datetime
from src.utils.timezone_utils import get_current_datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Any, Tuple
import asyncio
import logging

import aiohttp
import qrcode
from io import BytesIO

from src.core.config import Config
from src.utils.logger import get_logger
from src.utils.cache import Cache, CacheExpiry

# تنظیم لاگر
logger = get_logger(__name__)


class CryptoNetwork(Enum):
    """
    شبکه‌های مختلف برای رمزارزها
    """
    BITCOIN_MAINNET = "bitcoin_mainnet"
    BITCOIN_TESTNET = "bitcoin_testnet"
    ETHEREUM_MAINNET = "ethereum_mainnet"
    ETHEREUM_TESTNET = "ethereum_testnet"
    TRON_MAINNET = "tron_mainnet"
    TRON_TESTNET = "tron_testnet"
    BINANCE_SMART_CHAIN = "bsc_mainnet"
    BINANCE_SMART_CHAIN_TESTNET = "bsc_testnet"
    POLYGON = "polygon_mainnet"
    POLYGON_TESTNET = "polygon_testnet"


class CryptoPaymentStatus(Enum):
    """
    وضعیت‌های مختلف پرداخت رمزارزی
    """
    PENDING = "pending"  # در انتظار پرداخت
    RECEIVED = "received"  # دریافت شده اما در انتظار تایید
    CONFIRMED = "confirmed"  # تایید شده
    COMPLETED = "completed"  # تکمیل شده و پردازش شده
    EXPIRED = "expired"  # منقضی شده
    INSUFFICIENT = "insufficient"  # مبلغ کمتر از حد مورد نیاز
    FAILED = "failed"  # شکست خورده
    REFUNDED = "refunded"  # بازگشت داده شده


class CryptoPaymentProvider:
    """
    کلاس پایه برای ارائه‌دهنده خدمات پرداخت رمزارزی
    """
    def __init__(self, config: Config, provider_name: str):
        """
        مقداردهی اولیه کلاس پرداخت رمزارزی
        
        :param config: تنظیمات پیکربندی
        :param provider_name: نام ارائه‌دهنده خدمات
        """
        self.config = config
        self.provider_name = provider_name
        self.api_key = config.get(f"{provider_name.upper()}_API_KEY", "")
        self.api_secret = config.get(f"{provider_name.upper()}_API_SECRET", "")
        self.base_url = config.get(f"{provider_name.upper()}_API_URL", "")
        self.payment_endpoint = config.get(f"{provider_name.upper()}_PAYMENT_ENDPOINT", "")
        self.status_endpoint = config.get(f"{provider_name.upper()}_STATUS_ENDPOINT", "")
        self.rate_endpoint = config.get(f"{provider_name.upper()}_RATE_ENDPOINT", "")
        
        # کش برای ذخیره موقت اطلاعات
        self.cache = Cache()
        
        # شناسه یکتا برای ارائه‌دهنده
        self.provider_id = f"{provider_name}_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"ارائه‌دهنده پرداخت رمزارزی {provider_name} راه‌اندازی شد")
    
    async def create_payment(
        self, 
        amount: float,
        currency: str,
        crypto_currency: str,
        callback_url: str,
        order_id: Optional[str] = None,
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expiration_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        ایجاد درخواست پرداخت جدید
        
        :param amount: مبلغ به ارز فیات
        :param currency: نوع ارز فیات (USD, EUR, ...)
        :param crypto_currency: نوع رمزارز (BTC, ETH, ...)
        :param callback_url: آدرس برگشت بعد از پرداخت
        :param order_id: شناسه سفارش (اختیاری)
        :param user_id: شناسه کاربر (اختیاری)
        :param metadata: اطلاعات اضافی (اختیاری)
        :param expiration_minutes: زمان انقضا به دقیقه
        :return: دیکشنری اطلاعات پرداخت
        """
        # توابع مجازی که باید در کلاس‌های فرزند پیاده‌سازی شود
        raise NotImplementedError("این متد باید در کلاس فرزند پیاده‌سازی شود")
    
    async def check_payment_status(self, payment_id: str) -> CryptoPaymentStatus:
        """
        بررسی وضعیت پرداخت
        
        :param payment_id: شناسه پرداخت
        :return: وضعیت پرداخت
        """
        # توابع مجازی که باید در کلاس‌های فرزند پیاده‌سازی شود
        raise NotImplementedError("این متد باید در کلاس فرزند پیاده‌سازی شود")
    
    async def get_exchange_rate(
        self, 
        crypto_currency: str,
        fiat_currency: str = "USD"
    ) -> Optional[float]:
        """
        دریافت نرخ تبدیل ارز
        
        :param crypto_currency: نوع رمزارز (BTC, ETH, ...)
        :param fiat_currency: نوع ارز فیات (USD, EUR, ...)
        :return: نرخ تبدیل یا None در صورت خطا
        """
        # توابع مجازی که باید در کلاس‌های فرزند پیاده‌سازی شود
        raise NotImplementedError("این متد باید در کلاس فرزند پیاده‌سازی شود")
    
    def generate_qr_code(self, data: str) -> bytes:
        """
        تولید کد QR برای آدرس کیف پول یا پرداخت
        
        :param data: متن مورد نظر (آدرس کیف پول یا URI پرداخت)
        :return: داده‌های باینری تصویر QR
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # تبدیل تصویر به داده‌های باینری
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"خطا در تولید کد QR: {str(e)}")
            return b""
    
    def sign_request(self, data: Dict[str, Any], timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        امضای درخواست API با استفاده از HMAC
        
        :param data: داده‌های درخواست
        :param timestamp: زمان فعلی به میلی‌ثانیه (اختیاری)
        :return: داده‌های امضا شده
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)
        
        # تبدیل دیکشنری به رشته JSON
        data_str = json.dumps(data, separators=(',', ':'), sort_keys=True)
        
        # ایجاد رشته برای امضا (timestamp + data_str)
        message = f"{timestamp}{data_str}"
        
        # ایجاد امضا با استفاده از HMAC-SHA256
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # افزودن اطلاعات امضا به داده‌ها
        signed_data = data.copy()
        signed_data.update({
            "timestamp": timestamp,
            "signature": signature
        })
        
        return signed_data


class CoinpayProvider(CryptoPaymentProvider):
    """
    ارائه‌دهنده خدمات پرداخت رمزارزی CoinPay (نمونه)
    """
    def __init__(self, config: Config):
        """
        مقداردهی اولیه ارائه‌دهنده CoinPay
        
        :param config: تنظیمات پیکربندی
        """
        super().__init__(config, "coinpay")
    
    async def create_payment(
        self, 
        amount: float,
        currency: str,
        crypto_currency: str,
        callback_url: str,
        order_id: Optional[str] = None,
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expiration_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        ایجاد درخواست پرداخت جدید در CoinPay
        
        :param amount: مبلغ به ارز فیات
        :param currency: نوع ارز فیات (USD, EUR, ...)
        :param crypto_currency: نوع رمزارز (BTC, ETH, ...)
        :param callback_url: آدرس برگشت بعد از پرداخت
        :param order_id: شناسه سفارش (اختیاری)
        :param user_id: شناسه کاربر (اختیاری)
        :param metadata: اطلاعات اضافی (اختیاری)
        :param expiration_minutes: زمان انقضا به دقیقه
        :return: دیکشنری اطلاعات پرداخت
        """
        try:
            # ایجاد شناسه سفارش اگر ارائه نشده باشد
            if not order_id:
                order_id = f"order_{uuid.uuid4().hex[:12]}"
            
            # آماده‌سازی داده‌های درخواست
            request_data = {
                "amount": amount,
                "currency": currency.upper(),
                "crypto_currency": crypto_currency.upper(),
                "callback_url": callback_url,
                "order_id": order_id,
                "expiration_minutes": expiration_minutes
            }
            
            # افزودن شناسه کاربر اگر ارائه شده باشد
            if user_id is not None:
                request_data["user_id"] = str(user_id)
            
            # افزودن متادیتا اگر ارائه شده باشد
            if metadata:
                request_data["metadata"] = json.dumps(metadata)
            
            # امضای درخواست
            signed_data = self.sign_request(request_data)
            
            # ارسال درخواست به API
            endpoint = f"{self.base_url}{self.payment_endpoint}"
            headers = {
                "Content-Type": "application/json",
                "X-API-KEY": self.api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, json=signed_data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # ذخیره اطلاعات پرداخت در کش
                        self.cache.set(
                            f"payment_{result['payment_id']}",
                            {
                                "order_id": order_id,
                                "amount": amount,
                                "currency": currency,
                                "crypto_currency": crypto_currency,
                                "status": CryptoPaymentStatus.PENDING.value,
                                "created_at": datetime.get_current_datetime().isoformat(),
                                "expiration_minutes": expiration_minutes
                            },
                            expiry=CacheExpiry.ONE_DAY
                        )
                        
                        logger.info(f"درخواست پرداخت جدید ایجاد شد: {result['payment_id']}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"خطا در ایجاد درخواست پرداخت: {response.status} - {error_text}")
                        return {
                            "error": True,
                            "status": response.status,
                            "message": error_text
                        }
        
        except Exception as e:
            logger.error(f"خطا در ایجاد درخواست پرداخت: {str(e)}")
            return {
                "error": True,
                "message": str(e)
            }
    
    async def check_payment_status(self, payment_id: str) -> CryptoPaymentStatus:
        """
        بررسی وضعیت پرداخت در CoinPay
        
        :param payment_id: شناسه پرداخت
        :return: وضعیت پرداخت
        """
        try:
            # بررسی وضعیت از کش
            cached_data = self.cache.get(f"payment_{payment_id}")
            if cached_data and cached_data.get("status") == CryptoPaymentStatus.COMPLETED.value:
                return CryptoPaymentStatus.COMPLETED
            
            # آماده‌سازی داده‌های درخواست
            request_data = {
                "payment_id": payment_id
            }
            
            # امضای درخواست
            signed_data = self.sign_request(request_data)
            
            # ارسال درخواست به API
            endpoint = f"{self.base_url}{self.status_endpoint}"
            headers = {
                "Content-Type": "application/json",
                "X-API-KEY": self.api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, json=signed_data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # نگاشت وضعیت API به CryptoPaymentStatus
                        status_mapping = {
                            "pending": CryptoPaymentStatus.PENDING,
                            "received": CryptoPaymentStatus.RECEIVED,
                            "confirmed": CryptoPaymentStatus.CONFIRMED,
                            "completed": CryptoPaymentStatus.COMPLETED,
                            "expired": CryptoPaymentStatus.EXPIRED,
                            "insufficient": CryptoPaymentStatus.INSUFFICIENT,
                            "failed": CryptoPaymentStatus.FAILED,
                            "refunded": CryptoPaymentStatus.REFUNDED
                        }
                        
                        api_status = result.get("status", "").lower()
                        payment_status = status_mapping.get(api_status, CryptoPaymentStatus.PENDING)
                        
                        # به‌روزرسانی وضعیت در کش
                        if cached_data:
                            cached_data["status"] = payment_status.value
                            self.cache.set(
                                f"payment_{payment_id}",
                                cached_data,
                                expiry=CacheExpiry.ONE_DAY
                            )
                        
                        logger.info(f"وضعیت پرداخت {payment_id}: {payment_status.value}")
                        return payment_status
                    else:
                        error_text = await response.text()
                        logger.error(f"خطا در بررسی وضعیت پرداخت: {response.status} - {error_text}")
                        return CryptoPaymentStatus.FAILED
        
        except Exception as e:
            logger.error(f"خطا در بررسی وضعیت پرداخت: {str(e)}")
            return CryptoPaymentStatus.FAILED
    
    async def get_exchange_rate(
        self, 
        crypto_currency: str,
        fiat_currency: str = "USD"
    ) -> Optional[float]:
        """
        دریافت نرخ تبدیل ارز از CoinPay
        
        :param crypto_currency: نوع رمزارز (BTC, ETH, ...)
        :param fiat_currency: نوع ارز فیات (USD, EUR, ...)
        :return: نرخ تبدیل یا None در صورت خطا
        """
        try:
            # بررسی کش
            cache_key = f"rate_{crypto_currency}_{fiat_currency}"
            cached_rate = self.cache.get(cache_key)
            if cached_rate is not None:
                return cached_rate
            
            # آماده‌سازی داده‌های درخواست
            request_data = {
                "crypto_currency": crypto_currency.upper(),
                "fiat_currency": fiat_currency.upper()
            }
            
            # امضای درخواست
            signed_data = self.sign_request(request_data)
            
            # ارسال درخواست به API
            endpoint = f"{self.base_url}{self.rate_endpoint}"
            headers = {
                "Content-Type": "application/json",
                "X-API-KEY": self.api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, json=signed_data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        rate = result.get("rate")
                        
                        if rate:
                            # ذخیره در کش برای 5 دقیقه
                            self.cache.set(cache_key, rate, expiry=CacheExpiry.FIVE_MINUTES)
                            return rate
                        
                        return None
                    else:
                        error_text = await response.text()
                        logger.error(f"خطا در دریافت نرخ تبدیل ارز: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            logger.error(f"خطا در دریافت نرخ تبدیل ارز: {str(e)}")
            return None


# ایجاد نمونه از ارائه‌دهنده‌های پرداخت رمزارزی
provider_instances = {}


def get_crypto_payment_provider(provider_name: str, config: Optional[Config] = None) -> Optional[CryptoPaymentProvider]:
    """
    دریافت نمونه ارائه‌دهنده پرداخت رمزارزی
    
    :param provider_name: نام ارائه‌دهنده
    :param config: تنظیمات (اختیاری)
    :return: نمونه ارائه‌دهنده یا None در صورت عدم پشتیبانی
    """
    global provider_instances
    
    # بررسی وجود نمونه قبلی
    if provider_name in provider_instances:
        return provider_instances[provider_name]
    
    # ایجاد نمونه جدید
    if config is None:
        from ..core.config import Config
        config = Config()
    
    provider = None
    
    if provider_name.lower() == "coinpay":
        provider = CoinpayProvider(config)
    # افزودن سایر ارائه‌دهنده‌ها در اینجا
    # elif provider_name.lower() == "another_provider":
    #     provider = AnotherProvider(config)
    
    if provider:
        provider_instances[provider_name] = provider
        
    return provider


async def generate_wallet_address(
    crypto_currency: str,
    network: Optional[CryptoNetwork] = None,
    provider_name: str = "coinpay",
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    تولید آدرس کیف پول برای دریافت رمزارز
    
    :param crypto_currency: نوع رمزارز (BTC, ETH, ...)
    :param network: شبکه رمزارز (اختیاری)
    :param provider_name: نام ارائه‌دهنده خدمات
    :param config: تنظیمات (اختیاری)
    :return: دیکشنری حاوی اطلاعات آدرس کیف پول
    """
    # دریافت ارائه‌دهنده پرداخت
    provider = get_crypto_payment_provider(provider_name, config)
    
    if not provider:
        logger.error(f"ارائه‌دهنده پرداخت {provider_name} پشتیبانی نمی‌شود")
        return {
            "error": True,
            "message": f"ارائه‌دهنده پرداخت {provider_name} پشتیبانی نمی‌شود"
        }
    
    try:
        # آماده‌سازی داده‌های درخواست
        request_data = {
            "crypto_currency": crypto_currency.upper()
        }
        
        if network:
            request_data["network"] = network.value
        
        # امضای درخواست
        signed_data = provider.sign_request(request_data)
        
        # ارسال درخواست به API
        endpoint = f"{provider.base_url}/generate-address"
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": provider.api_key
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=signed_data, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # ایجاد QR code برای آدرس
                    if "address" in result:
                        qr_data = provider.generate_qr_code(result["address"])
                        result["qr_code"] = base64.b64encode(qr_data).decode('utf-8')
                    
                    logger.info(f"آدرس کیف پول {crypto_currency} تولید شد")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"خطا در تولید آدرس کیف پول: {response.status} - {error_text}")
                    return {
                        "error": True,
                        "status": response.status,
                        "message": error_text
                    }
    
    except Exception as e:
        logger.error(f"خطا در تولید آدرس کیف پول: {str(e)}")
        return {
            "error": True,
            "message": str(e)
        }


async def verify_crypto_transaction(
    transaction_hash: str,
    crypto_currency: str,
    expected_amount: Optional[float] = None,
    recipient_address: Optional[str] = None,
    provider_name: str = "coinpay",
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    تایید تراکنش رمزارزی
    
    :param transaction_hash: هش تراکنش
    :param crypto_currency: نوع رمزارز
    :param expected_amount: مبلغ مورد انتظار (اختیاری)
    :param recipient_address: آدرس گیرنده (اختیاری)
    :param provider_name: نام ارائه‌دهنده خدمات
    :param config: تنظیمات (اختیاری)
    :return: دیکشنری حاوی اطلاعات تایید تراکنش
    """
    # دریافت ارائه‌دهنده پرداخت
    provider = get_crypto_payment_provider(provider_name, config)
    
    if not provider:
        logger.error(f"ارائه‌دهنده پرداخت {provider_name} پشتیبانی نمی‌شود")
        return {
            "error": True,
            "message": f"ارائه‌دهنده پرداخت {provider_name} پشتیبانی نمی‌شود"
        }
    
    try:
        # آماده‌سازی داده‌های درخواست
        request_data = {
            "transaction_hash": transaction_hash,
            "crypto_currency": crypto_currency.upper()
        }
        
        if expected_amount is not None:
            request_data["expected_amount"] = expected_amount
            
        if recipient_address:
            request_data["recipient_address"] = recipient_address
        
        # امضای درخواست
        signed_data = provider.sign_request(request_data)
        
        # ارسال درخواست به API
        endpoint = f"{provider.base_url}/verify-transaction"
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": provider.api_key
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=signed_data, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"تراکنش {transaction_hash} تایید شد: {result}")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"خطا در تایید تراکنش: {response.status} - {error_text}")
                    return {
                        "error": True,
                        "status": response.status,
                        "message": error_text
                    }
    
    except Exception as e:
        logger.error(f"خطا در تایید تراکنش: {str(e)}")
        return {
            "error": True,
            "message": str(e)
        }


async def get_crypto_payment_status(
    payment_id: str,
    provider_name: str = "coinpay",
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    دریافت وضعیت پرداخت رمزارزی
    
    :param payment_id: شناسه پرداخت
    :param provider_name: نام ارائه‌دهنده خدمات
    :param config: تنظیمات (اختیاری)
    :return: دیکشنری حاوی اطلاعات وضعیت پرداخت
    """
    # دریافت ارائه‌دهنده پرداخت
    provider = get_crypto_payment_provider(provider_name, config)
    
    if not provider:
        logger.error(f"ارائه‌دهنده پرداخت {provider_name} پشتیبانی نمی‌شود")
        return {
            "error": True,
            "message": f"ارائه‌دهنده پرداخت {provider_name} پشتیبانی نمی‌شود"
        }
    
    try:
        # بررسی وضعیت پرداخت
        status = await provider.check_payment_status(payment_id)
        
        return {
            "payment_id": payment_id,
            "status": status.value,
            "is_completed": status == CryptoPaymentStatus.COMPLETED,
            "is_pending": status in [CryptoPaymentStatus.PENDING, CryptoPaymentStatus.RECEIVED]
        }
    
    except Exception as e:
        logger.error(f"خطا در دریافت وضعیت پرداخت: {str(e)}")
        return {
            "error": True,
            "message": str(e)
        }


async def get_current_exchange_rate(
    crypto_currency: str,
    fiat_currency: str = "USD",
    provider_name: str = "coinpay",
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    دریافت نرخ تبدیل ارز فعلی
    
    :param crypto_currency: نوع رمزارز
    :param fiat_currency: نوع ارز فیات
    :param provider_name: نام ارائه‌دهنده خدمات
    :param config: تنظیمات (اختیاری)
    :return: دیکشنری حاوی اطلاعات نرخ تبدیل
    """
    # دریافت ارائه‌دهنده پرداخت
    provider = get_crypto_payment_provider(provider_name, config)
    
    if not provider:
        logger.error(f"ارائه‌دهنده پرداخت {provider_name} پشتیبانی نمی‌شود")
        return {
            "error": True,
            "message": f"ارائه‌دهنده پرداخت {provider_name} پشتیبانی نمی‌شود"
        }
    
    try:
        # دریافت نرخ تبدیل
        rate = await provider.get_exchange_rate(crypto_currency, fiat_currency)
        
        if rate is not None:
            return {
                "crypto_currency": crypto_currency.upper(),
                "fiat_currency": fiat_currency.upper(),
                "rate": rate,
                "timestamp": int(time.time())
            }
        else:
            return {
                "error": True,
                "message": "خطا در دریافت نرخ تبدیل ارز"
            }
    
    except Exception as e:
        logger.error(f"خطا در دریافت نرخ تبدیل ارز: {str(e)}")
        return {
            "error": True,
            "message": str(e)
        }


def create_crypto_payment_uri(
    address: str,
    crypto_currency: str,
    amount: Optional[float] = None,
    label: Optional[str] = None,
    message: Optional[str] = None
) -> str:
    """
    ایجاد URI پرداخت رمزارزی برای QR code
    
    :param address: آدرس کیف پول
    :param crypto_currency: نوع رمزارز
    :param amount: مبلغ (اختیاری)
    :param label: برچسب (اختیاری)
    :param message: پیام (اختیاری)
    :return: URI پرداخت
    """
    # تبدیل رمزارز به حروف کوچک
    crypto_lower = crypto_currency.lower()
    
    # شروع URI با پروتکل مناسب
    uri = f"{crypto_lower}:{address}"
    
    # پارامترهای اختیاری
    params = []
    
    if amount is not None:
        params.append(f"amount={amount}")
    
    if label:
        params.append(f"label={label}")
    
    if message:
        params.append(f"message={message}")
    
    # افزودن پارامترها به URI
    if params:
        uri += "?" + "&".join(params)
    
    return uri


class BitkhabProvider(CryptoPaymentProvider):
    """
    ارائه‌دهنده خدمات پرداخت رمزارزی Bitkhab (نمونه ایرانی)
    """
    def __init__(self, config: Config):
        """
        مقداردهی اولیه ارائه‌دهنده Bitkhab
        
        :param config: تنظیمات پیکربندی
        """
        super().__init__(config, "bitkhab")
    
    async def create_payment(
        self, 
        amount: float,
        currency: str,
        crypto_currency: str,
        callback_url: str,
        order_id: Optional[str] = None,
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expiration_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        ایجاد درخواست پرداخت جدید در Bitkhab
        
        :param amount: مبلغ به ارز فیات
        :param currency: نوع ارز فیات (USD, EUR, IRT, ...)
        :param crypto_currency: نوع رمزارز (BTC, ETH, ...)
        :param callback_url: آدرس برگشت بعد از پرداخت
        :param order_id: شناسه سفارش (اختیاری)
        :param user_id: شناسه کاربر (اختیاری)
        :param metadata: اطلاعات اضافی (اختیاری)
        :param expiration_minutes: زمان انقضا به دقیقه
        :return: دیکشنری اطلاعات پرداخت
        """
        try:
            # ایجاد شناسه سفارش اگر ارائه نشده باشد
            if not order_id:
                order_id = f"order_{uuid.uuid4().hex[:12]}"
            
            # آماده‌سازی داده‌های درخواست
            request_data = {
                "amount": amount,
                "source_currency": currency.upper(),
                "destination_currency": crypto_currency.upper(),
                "callback_url": callback_url,
                "merchant_id": self.config.get("BITKHAB_MERCHANT_ID", ""),
                "ref_id": order_id,
                "timeout": expiration_minutes * 60  # تبدیل به ثانیه
            }
            
            # افزودن شناسه کاربر اگر ارائه شده باشد
            if user_id is not None:
                request_data["customer_id"] = str(user_id)
            
            # افزودن متادیتا اگر ارائه شده باشد
            if metadata:
                request_data["extra_data"] = json.dumps(metadata)
            
            # امضای درخواست
            timestamp = int(time.time())
            nonce = uuid.uuid4().hex
            
            message = f"{timestamp}.{nonce}.{request_data['ref_id']}.{request_data['amount']}"
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # افزودن اطلاعات امنیتی
            headers = {
                "Content-Type": "application/json",
                "X-API-KEY": self.api_key,
                "X-TIMESTAMP": str(timestamp),
                "X-NONCE": nonce,
                "X-SIGNATURE": signature
            }
            
            # ارسال درخواست به API
            endpoint = f"{self.base_url}/api/v2/payment/create"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, json=request_data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get("success", False):
                            payment_data = result.get("data", {})
                            payment_id = payment_data.get("payment_id")
                            
                            # ذخیره اطلاعات پرداخت در کش
                            if payment_id:
                                self.cache.set(
                                    f"payment_{payment_id}",
                                    {
                                        "order_id": order_id,
                                        "amount": amount,
                                        "currency": currency,
                                        "crypto_currency": crypto_currency,
                                        "status": CryptoPaymentStatus.PENDING.value,
                                        "created_at": datetime.get_current_datetime().isoformat(),
                                        "expiration_minutes": expiration_minutes
                                    },
                                    expiry=CacheExpiry.ONE_DAY
                                )
                                
                                logger.info(f"درخواست پرداخت جدید در Bitkhab ایجاد شد: {payment_id}")
                            
                            return {
                                "payment_id": payment_id,
                                "order_id": order_id,
                                "amount": payment_data.get("crypto_amount"),
                                "crypto_currency": crypto_currency.upper(),
                                "address": payment_data.get("address"),
                                "qr_code": payment_data.get("qr_code"),
                                "payment_url": payment_data.get("payment_url"),
                                "expires_at": payment_data.get("expires_at"),
                                "status": "pending"
                            }
                        else:
                            error = result.get("error", {})
                            error_message = error.get("message", "خطای نامشخص")
                            error_code = error.get("code", 0)
                            
                            logger.error(f"خطا در ایجاد درخواست پرداخت در Bitkhab: {error_code} - {error_message}")
                            return {
                                "error": True,
                                "error_code": error_code,
                                "message": error_message
                            }
                    else:
                        error_text = await response.text()
                        logger.error(f"خطا در ایجاد درخواست پرداخت در Bitkhab: {response.status} - {error_text}")
                        return {
                            "error": True,
                            "status": response.status,
                            "message": error_text
                        }
        
        except Exception as e:
            logger.error(f"خطا در ایجاد درخواست پرداخت در Bitkhab: {str(e)}")
            return {
                "error": True,
                "message": str(e)
            }
    
    async def check_payment_status(self, payment_id: str) -> CryptoPaymentStatus:
        """
        بررسی وضعیت پرداخت در Bitkhab
        
        :param payment_id: شناسه پرداخت
        :return: وضعیت پرداخت
        """
        try:
            # بررسی وضعیت از کش
            cached_data = self.cache.get(f"payment_{payment_id}")
            if cached_data and cached_data.get("status") == CryptoPaymentStatus.COMPLETED.value:
                return CryptoPaymentStatus.COMPLETED
            
            # آماده‌سازی درخواست
            timestamp = int(time.time())
            nonce = uuid.uuid4().hex
            
            message = f"{timestamp}.{nonce}.{payment_id}"
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # افزودن اطلاعات امنیتی
            headers = {
                "Content-Type": "application/json",
                "X-API-KEY": self.api_key,
                "X-TIMESTAMP": str(timestamp),
                "X-NONCE": nonce,
                "X-SIGNATURE": signature
            }
            
            # ارسال درخواست به API
            endpoint = f"{self.base_url}/api/v2/payment/status"
            request_data = {
                "payment_id": payment_id
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, json=request_data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get("success", False):
                            payment_data = result.get("data", {})
                            api_status = payment_data.get("status", "").lower()
                            
                            # نگاشت وضعیت API به CryptoPaymentStatus
                            status_mapping = {
                                "pending": CryptoPaymentStatus.PENDING,
                                "received": CryptoPaymentStatus.RECEIVED,
                                "confirmed": CryptoPaymentStatus.CONFIRMED,
                                "completed": CryptoPaymentStatus.COMPLETED,
                                "expired": CryptoPaymentStatus.EXPIRED,
                                "insufficient": CryptoPaymentStatus.INSUFFICIENT,
                                "failed": CryptoPaymentStatus.FAILED,
                                "refunded": CryptoPaymentStatus.REFUNDED
                            }
                            
                            payment_status = status_mapping.get(api_status, CryptoPaymentStatus.PENDING)
                            
                            # به‌روزرسانی وضعیت در کش
                            if cached_data:
                                cached_data["status"] = payment_status.value
                                cached_data["confirmations"] = payment_data.get("confirmations", 0)
                                cached_data["received_amount"] = payment_data.get("received_amount", 0)
                                
                                self.cache.set(
                                    f"payment_{payment_id}",
                                    cached_data,
                                    expiry=CacheExpiry.ONE_DAY
                                )
                            
                            logger.info(f"وضعیت پرداخت {payment_id} در Bitkhab: {payment_status.value}")
                            return payment_status
                        else:
                            error = result.get("error", {})
                            error_message = error.get("message", "خطای نامشخص")
                            logger.error(f"خطا در بررسی وضعیت پرداخت در Bitkhab: {error_message}")
                            return CryptoPaymentStatus.FAILED
                    else:
                        error_text = await response.text()
                        logger.error(f"خطا در بررسی وضعیت پرداخت در Bitkhab: {response.status} - {error_text}")
                        return CryptoPaymentStatus.FAILED
        
        except Exception as e:
            logger.error(f"خطا در بررسی وضعیت پرداخت در Bitkhab: {str(e)}")
            return CryptoPaymentStatus.FAILED
    
    async def get_exchange_rate(
        self, 
        crypto_currency: str,
        fiat_currency: str = "USD"
    ) -> Optional[float]:
        """
        دریافت نرخ تبدیل ارز از Bitkhab
        
        :param crypto_currency: نوع رمزارز (BTC, ETH, ...)
        :param fiat_currency: نوع ارز فیات (USD, EUR, IRT, ...)
        :return: نرخ تبدیل یا None در صورت خطا
        """
        try:
            # بررسی کش
            cache_key = f"rate_{crypto_currency}_{fiat_currency}"
            cached_rate = self.cache.get(cache_key)
            if cached_rate is not None:
                return cached_rate
            
            # آماده‌سازی درخواست
            timestamp = int(time.time())
            nonce = uuid.uuid4().hex
            
            message = f"{timestamp}.{nonce}.{crypto_currency}.{fiat_currency}"
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # افزودن اطلاعات امنیتی
            headers = {
                "Content-Type": "application/json",
                "X-API-KEY": self.api_key,
                "X-TIMESTAMP": str(timestamp),
                "X-NONCE": nonce,
                "X-SIGNATURE": signature
            }
            
            # ارسال درخواست به API
            endpoint = f"{self.base_url}/api/v2/exchange/rate"
            request_data = {
                "source_currency": fiat_currency.upper(),
                "destination_currency": crypto_currency.upper()
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, json=request_data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get("success", False):
                            rate_data = result.get("data", {})
                            rate = rate_data.get("rate")
                            
                            if rate:
                                # ذخیره در کش برای 5 دقیقه
                                self.cache.set(cache_key, rate, expiry=CacheExpiry.FIVE_MINUTES)
                                return rate
                            
                            return None
                        else:
                            error = result.get("error", {})
                            error_message = error.get("message", "خطای نامشخص")
                            logger.error(f"خطا در دریافت نرخ تبدیل ارز از Bitkhab: {error_message}")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"خطا در دریافت نرخ تبدیل ارز از Bitkhab: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            logger.error(f"خطا در دریافت نرخ تبدیل ارز از Bitkhab: {str(e)}")
            return None


# اضافه کردن Bitkhab به لیست ارائه‌دهنده‌های پشتیبانی شده
def get_crypto_payment_provider(provider_name: str, config: Optional[Config] = None) -> Optional[CryptoPaymentProvider]:
    """
    دریافت نمونه ارائه‌دهنده پرداخت رمزارزی
    
    :param provider_name: نام ارائه‌دهنده
    :param config: تنظیمات (اختیاری)
    :return: نمونه ارائه‌دهنده یا None در صورت عدم پشتیبانی
    """
    global provider_instances
    
    # بررسی وجود نمونه قبلی
    if provider_name in provider_instances:
        return provider_instances[provider_name]
    
    # ایجاد نمونه جدید
    if config is None:
        from ..core.config import Config
        config = Config()
    
    provider = None
    
    if provider_name.lower() == "coinpay":
        provider = CoinpayProvider(config)
    elif provider_name.lower() == "bitkhab":
        provider = BitkhabProvider(config)
    # افزودن سایر ارائه‌دهنده‌ها در اینجا
    # elif provider_name.lower() == "another_provider":
    #     provider = AnotherProvider(config)
    
    if provider:
        provider_instances[provider_name] = provider
        
    return provider


async def calculate_crypto_amount(
    fiat_amount: float,
    fiat_currency: str,
    crypto_currency: str,
    provider_name: str = "coinpay",
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    محاسبه معادل رمزارزی یک مبلغ فیات
    
    :param fiat_amount: مبلغ ارز فیات
    :param fiat_currency: نوع ارز فیات
    :param crypto_currency: نوع رمزارز
    :param provider_name: نام ارائه‌دهنده خدمات
    :param config: تنظیمات (اختیاری)
    :return: دیکشنری حاوی اطلاعات مبلغ محاسبه شده
    """
    # دریافت نرخ تبدیل ارز
    rate_info = await get_current_exchange_rate(
        crypto_currency,
        fiat_currency,
        provider_name,
        config
    )
    
    if "error" in rate_info:
        return rate_info
    
    # محاسبه مبلغ رمزارز
    rate = rate_info["rate"]
    crypto_amount = fiat_amount / rate
    
    # گرد کردن مبلغ رمزارز به تعداد رقم اعشار مناسب
    decimals = {
        "BTC": 8,
        "ETH": 6,
        "USDT": 2,
        "USDC": 2,
        "XRP": 6,
        "LTC": 8,
        "BNB": 6,
        "ADA": 6,
        "SOL": 6,
        "DOGE": 8
    }
    
    decimal_places = decimals.get(crypto_currency.upper(), 8)
    crypto_amount = round(crypto_amount, decimal_places)
    
    return {
        "fiat_amount": fiat_amount,
        "fiat_currency": fiat_currency.upper(),
        "crypto_amount": crypto_amount,
        "crypto_currency": crypto_currency.upper(),
        "exchange_rate": rate,
        "timestamp": rate_info["timestamp"]
    }


async def track_crypto_payment(
    payment_id: str,
    check_interval: int = 60,
    max_checks: int = 60,
    provider_name: str = "coinpay",
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    پیگیری وضعیت پرداخت رمزارزی با بررسی دوره‌ای
    
    :param payment_id: شناسه پرداخت
    :param check_interval: فاصله زمانی بررسی به ثانیه
    :param max_checks: حداکثر تعداد بررسی‌ها
    :param provider_name: نام ارائه‌دهنده خدمات
    :param config: تنظیمات (اختیاری)
    :return: دیکشنری حاوی اطلاعات وضعیت نهایی پرداخت
    """
    # دریافت ارائه‌دهنده پرداخت
    provider = get_crypto_payment_provider(provider_name, config)
    
    if not provider:
        logger.error(f"ارائه‌دهنده پرداخت {provider_name} پشتیبانی نمی‌شود")
        return {
            "error": True,
            "message": f"ارائه‌دهنده پرداخت {provider_name} پشتیبانی نمی‌شود"
        }
    
    check_count = 0
    final_status = None
    
    # بررسی دوره‌ای وضعیت پرداخت
    while check_count < max_checks:
        # بررسی وضعیت فعلی
        status = await provider.check_payment_status(payment_id)
        
        # اگر پرداخت تکمیل یا رد شده باشد
        if status in [
            CryptoPaymentStatus.COMPLETED,
            CryptoPaymentStatus.FAILED,
            CryptoPaymentStatus.EXPIRED,
            CryptoPaymentStatus.REFUNDED
        ]:
            final_status = status
            break
        
        # انتظار برای بررسی بعدی
        check_count += 1
        if check_count < max_checks:
            await asyncio.sleep(check_interval)
    
    # اگر پرداخت هنوز در حال انجام باشد
    if final_status is None:
        final_status = await provider.check_payment_status(payment_id)
    
    return {
        "payment_id": payment_id,
        "status": final_status.value,
        "checks_performed": check_count,
        "is_completed": final_status == CryptoPaymentStatus.COMPLETED,
        "is_final": final_status in [
            CryptoPaymentStatus.COMPLETED,
            CryptoPaymentStatus.FAILED,
            CryptoPaymentStatus.EXPIRED,
            CryptoPaymentStatus.REFUNDED
        ]
    }


def estimate_confirmation_time(
    crypto_currency: str,
    fee_level: str = "medium"
) -> Dict[str, Any]:
    """
    تخمین زمان تایید تراکنش رمزارزی بر اساس شبکه و سطح کارمزد
    
    :param crypto_currency: نوع رمزارز
    :param fee_level: سطح کارمزد (low, medium, high)
    :return: دیکشنری حاوی اطلاعات تخمین زمان
    """
    # مقادیر تخمینی بر حسب دقیقه
    estimations = {
        "BTC": {
            "low": 60,      # 1 ساعت
            "medium": 30,   # 30 دقیقه
            "high": 10      # 10 دقیقه
        },
        "ETH": {
            "low": 10,      # 10 دقیقه
            "medium": 5,    # 5 دقیقه
            "high": 2       # 2 دقیقه
        },
        "LTC": {
            "low": 15,      # 15 دقیقه
            "medium": 7,    # 7 دقیقه
            "high": 2       # 2 دقیقه
        },
        "BCH": {
            "low": 15,      # 15 دقیقه
            "medium": 7,    # 7 دقیقه
            "high": 2       # 2 دقیقه
        },
        "XRP": {
            "low": 1,       # 1 دقیقه
            "medium": 0.5,  # 30 ثانیه
            "high": 0.2     # 12 ثانیه
        },
        "BNB": {
            "low": 3,       # 3 دقیقه
            "medium": 1,    # 1 دقیقه
            "high": 0.5     # 30 ثانیه
        },
        "TRX": {
            "low": 2,       # 2 دقیقه
            "medium": 1,    # 1 دقیقه
            "high": 0.5     # 30 ثانیه
        },
        "DOGE": {
            "low": 10,      # 10 دقیقه
            "medium": 5,    # 5 دقیقه
            "high": 2       # 2 دقیقه
        }
    }
    
    # مقادیر پیش‌فرض
    default_times = {
        "low": 30,      # 30 دقیقه
        "medium": 15,   # 15 دقیقه
        "high": 5       # 5 دقیقه
    }
    
    crypto = crypto_currency.upper()
    
    # بررسی وجود رمزارز در لیست
    if crypto not in estimations:
        times = default_times
    else:
        times = estimations[crypto]
    
    # بررسی وجود سطح کارمزد
    if fee_level.lower() not in times:
        fee_level = "medium"
    
    minutes = times[fee_level.lower()]
    seconds = minutes * 60
    
    # اگر زمان کمتر از 1 دقیقه باشد، به ثانیه نمایش داده شود
    if minutes < 1:
        time_display = f"{int(seconds)} ثانیه"
    else:
        time_display = f"{int(minutes)} دقیقه"
    
    return {
        "crypto_currency": crypto,
        "fee_level": fee_level.lower(),
        "estimated_minutes": minutes,
        "estimated_seconds": seconds,
        "display": time_display,
        "min_confirmations": get_min_confirmations(crypto)
    }


def get_min_confirmations(crypto_currency: str) -> int:
    """
    دریافت حداقل تعداد تاییدیه‌های مورد نیاز برای اطمینان از تراکنش
    
    :param crypto_currency: نوع رمزارز
    :return: تعداد تاییدیه‌های مورد نیاز
    """
    confirmations = {
        "BTC": 3,
        "ETH": 16,
        "USDT": 16,  # بر روی اتریوم
        "USDC": 16,  # بر روی اتریوم
        "LTC": 6,
        "BCH": 6,
        "XRP": 1,
        "BNB": 15,
        "TRX": 19,
        "DOGE": 40,
        "ADA": 15,
        "SOL": 32
    }
    
    crypto = crypto_currency.upper()
    return confirmations.get(crypto, 10)  # مقدار پیش‌فرض 10 تاییدیه