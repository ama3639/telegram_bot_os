#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول تبدیل ارزها برای تبدیل مبالغ بین ارزهای مختلف.
این ماژول امکان تبدیل ارزها را با استفاده از نرخ‌های ارز به‌روز فراهم می‌کند.
"""


from datetime import timezone
import logging
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime
from utils.timezone_utils import get_current_datetime, timezone, timedelta
from dataclasses import dataclass, asdict, field
import json
import requests
from enum import Enum
import uuid
import time

from utils.cache import Cache

logger = logging.getLogger('accounting.currency_converter')

# کش برای نگهداری نرخ‌های ارز
exchange_rates_cache = Cache(ttl=3600)  # یک ساعت

class Currency:
    """
    کلاس نگهداری اطلاعات یک ارز
    """
    # لیست ارزهای پشتیبانی شده
    SUPPORTED_CURRENCIES = {
        "IRR": {
            "name": "Iranian Rial",
            "symbol": "﷼",
            "is_fiat": True,
            "decimal_digits": 0
        },
        "USD": {
            "name": "US Dollar",
            "symbol": "$",
            "is_fiat": True,
            "decimal_digits": 2
        },
        "EUR": {
            "name": "Euro",
            "symbol": "€",
            "is_fiat": True,
            "decimal_digits": 2
        },
        "GBP": {
            "name": "British Pound",
            "symbol": "£",
            "is_fiat": True,
            "decimal_digits": 2
        },
        "BTC": {
            "name": "Bitcoin",
            "symbol": "₿",
            "is_fiat": False,
            "decimal_digits": 8
        },
        "ETH": {
            "name": "Ethereum",
            "symbol": "Ξ",
            "is_fiat": False,
            "decimal_digits": 18
        },
        "USDT": {
            "name": "Tether",
            "symbol": "₮",
            "is_fiat": False,
            "decimal_digits": 6
        }
    }
    
    def __init__(self, code: str):
        """
        مقداردهی اولیه کلاس ارز.
        
        Args:
            code: کد ارز (مانند USD یا BTC)
        """
        if code not in self.SUPPORTED_CURRENCIES:
            raise ValueError(f"ارز '{code}' پشتیبانی نمی‌شود")
            
        self.code = code
        currency_info = self.SUPPORTED_CURRENCIES[code]
        self.name = currency_info["name"]
        self.symbol = currency_info["symbol"]
        self.is_fiat = currency_info["is_fiat"]
        self.decimal_digits = currency_info["decimal_digits"]
    
    def __str__(self) -> str:
        return f"{self.code} ({self.name})"
    
    def __repr__(self) -> str:
        return f"Currency('{self.code}')"
    
    def format_amount(self, amount: float) -> str:
        """
        قالب‌بندی مبلغ با توجه به ارز
        
        Args:
            amount: مبلغ
            
        Returns:
            str: مبلغ قالب‌بندی شده با نماد ارز
        """
        if self.code == "IRR":
            # برای ریال، از جداکننده هزارگان استفاده می‌کنیم
            formatted = f"{int(amount):,}"
            return f"{formatted} {self.symbol}"
        else:
            # برای سایر ارزها، از تعداد رقم اعشار تعریف شده استفاده می‌کنیم
            formatted = f"{amount:,.{self.decimal_digits}f}"
            
            if self.code in ["USD", "EUR", "GBP"]:
                # نماد قبل از عدد برای دلار، یورو و پوند
                return f"{self.symbol}{formatted}"
            else:
                # نماد بعد از عدد برای سایر ارزها
                return f"{formatted} {self.symbol}"

@dataclass
class CurrencyPair:
    """
    کلاس نگهداری اطلاعات یک جفت ارز
    """
    base_currency: str
    quote_currency: str
    rate: float
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "unknown"
    
    @property
    def pair_code(self) -> str:
        """
        کد جفت ارز.
        
        Returns:
            str: کد جفت ارز (مانند BTC/USD)
        """
        return f"{self.base_currency}/{self.quote_currency}"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        تبدیل جفت ارز به دیکشنری.
        
        Returns:
            Dict[str, Any]: اطلاعات جفت ارز
        """
        return {
            "base_currency": self.base_currency,
            "quote_currency": self.quote_currency,
            "rate": self.rate,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "pair_code": self.pair_code
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CurrencyPair':
        """
        ایجاد جفت ارز از دیکشنری.
        
        Args:
            data: دیکشنری اطلاعات جفت ارز
            
        Returns:
            CurrencyPair: آبجکت جفت ارز
        """
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
            
        return cls(
            base_currency=data['base_currency'],
            quote_currency=data['quote_currency'],
            rate=data['rate'],
            timestamp=timestamp,
            source=data.get('source', 'unknown')
        )

class CurrencyConverter:
    """
    کلاس تبدیل ارزها
    """
    
    def __init__(self, db, config):
        """
        مقداردهی اولیه کلاس تبدیل ارز.
        
        Args:
            db: آبجکت دیتابیس
            config: آبجکت تنظیمات
        """
        self.db = db
        self.config = config
        
        # API های خارجی برای دریافت نرخ ارز
        self.api_providers = {
            "exchangerate-api": {
                "enabled": self.config.get('currency_converter', 'use_exchangerate_api', fallback="true").lower() == "true",
                "api_key": self.config.get('currency_converter', 'exchangerate_api_key', fallback=""),
                "base_url": "https://v6.exchangerate-api.com/v6/{api_key}/latest/{base_currency}",
                "supported_currencies": ["USD", "EUR", "GBP", "IRR", "AED", "TRY", "CNY", "JPY", "CAD", "AUD"]
            },
            "coinmarketcap": {
                "enabled": self.config.get('currency_converter', 'use_coinmarketcap_api', fallback="true").lower() == "true",
                "api_key": self.config.get('currency_converter', 'coinmarketcap_api_key', fallback=""),
                "base_url": "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest",
                "supported_currencies": ["BTC", "ETH", "USDT", "BNB", "XRP", "ADA", "SOL", "DOT", "DOGE", "SHIB"]
            }
        }
    
    def get_rate(self, base_currency: str, quote_currency: str) -> Optional[CurrencyPair]:
        """
        دریافت نرخ تبدیل بین دو ارز.
        
        Args:
            base_currency: ارز مبدأ
            quote_currency: ارز مقصد
            
        Returns:
            Optional[CurrencyPair]: جفت ارز و نرخ تبدیل یا None در صورت عدم دسترسی
        """
        # بررسی اعتبار ارزها
        if base_currency not in Currency.SUPPORTED_CURRENCIES:
            logger.error(f"ارز '{base_currency}' پشتیبانی نمی‌شود")
            return None
            
        if quote_currency not in Currency.SUPPORTED_CURRENCIES:
            logger.error(f"ارز '{quote_currency}' پشتیبانی نمی‌شود")
            return None
            
        # اگر ارزها یکسان باشند، نرخ 1 است
        if base_currency == quote_currency:
            return CurrencyPair(
                base_currency=base_currency,
                quote_currency=quote_currency,
                rate=1.0,
                timestamp=get_current_datetime(),
                source="direct"
            )
        
        # بررسی کش
        cache_key = f"rate_{base_currency}_{quote_currency}"
        cached_rate = exchange_rates_cache.get(cache_key)
        if cached_rate:
            return CurrencyPair.from_dict(cached_rate)
        
        # بررسی دیتابیس برای نرخ‌های اخیر
        db_rate = self._get_rate_from_db(base_currency, quote_currency)
        if db_rate:
            # ذخیره در کش
            exchange_rates_cache.set(cache_key, db_rate.to_dict())
            return db_rate
        
        # دریافت از API های خارجی
        api_rate = self._get_rate_from_api(base_currency, quote_currency)
        if api_rate:
            # ذخیره در دیتابیس
            self._save_rate_to_db(api_rate)
            
            # ذخیره در کش
            exchange_rates_cache.set(cache_key, api_rate.to_dict())
            
            return api_rate
            
        # اگر نرخ به دست نیامد، سعی می‌کنیم از طریق USD تبدیل کنیم
        if base_currency != "USD" and quote_currency != "USD":
            base_to_usd = self.get_rate(base_currency, "USD")
            usd_to_quote = self.get_rate("USD", quote_currency)
            
            if base_to_usd and usd_to_quote:
                # محاسبه نرخ ترکیبی
                rate = base_to_usd.rate * usd_to_quote.rate
                
                currency_pair = CurrencyPair(
                    base_currency=base_currency,
                    quote_currency=quote_currency,
                    rate=rate,
                    timestamp=get_current_datetime(),
                    source="computed"
                )
                
                # ذخیره نرخ محاسبه شده
                self._save_rate_to_db(currency_pair)
                
                # ذخیره در کش
                exchange_rates_cache.set(cache_key, currency_pair.to_dict())
                
                return currency_pair
        
        logger.error(f"نرخ تبدیل برای {base_currency}/{quote_currency} یافت نشد")
        return None
    
    def convert(self, amount: float, from_currency: str, to_currency: str) -> Optional[float]:
        """
        تبدیل مبلغ از یک ارز به ارز دیگر.
        
        Args:
            amount: مبلغ
            from_currency: ارز مبدأ
            to_currency: ارز مقصد
            
        Returns:
            Optional[float]: مبلغ تبدیل شده یا None در صورت عدم دسترسی به نرخ
        """
        if amount <= 0:
            logger.error("مبلغ باید بزرگتر از صفر باشد")
            return None
            
        # دریافت نرخ تبدیل
        currency_pair = self.get_rate(from_currency, to_currency)
        if not currency_pair:
            return None
            
        # تبدیل مبلغ
        converted_amount = amount * currency_pair.rate
        
        # گرد کردن بر اساس ارز مقصد
        decimal_digits = Currency.SUPPORTED_CURRENCIES[to_currency]["decimal_digits"]
        return round(converted_amount, decimal_digits)
    
    def format_conversion(self, amount: float, from_currency: str, to_currency: str) -> Optional[str]:
        """
        تبدیل مبلغ و ارائه آن به صورت متنی قالب‌بندی شده.
        
        Args:
            amount: مبلغ
            from_currency: ارز مبدأ
            to_currency: ارز مقصد
            
        Returns:
            Optional[str]: متن نتیجه تبدیل یا None در صورت خطا
        """
        if amount <= 0:
            logger.error("مبلغ باید بزرگتر از صفر باشد")
            return None
            
        # تبدیل مبلغ
        converted_amount = self.convert(amount, from_currency, to_currency)
        if converted_amount is None:
            return None
            
        # قالب‌بندی مبالغ
        from_currency_obj = Currency(from_currency)
        to_currency_obj = Currency(to_currency)
        
        from_formatted = from_currency_obj.format_amount(amount)
        to_formatted = to_currency_obj.format_amount(converted_amount)
        
        # دریافت نرخ تبدیل
        currency_pair = self.get_rate(from_currency, to_currency)
        
        return f"{from_formatted} = {to_formatted}\nنرخ: 1 {from_currency} = {currency_pair.rate:.6f} {to_currency}"
    
    def get_all_rates(self, base_currency: str) -> Dict[str, CurrencyPair]:
        """
        دریافت نرخ تبدیل بین یک ارز و تمام ارزهای پشتیبانی شده.
        
        Args:
            base_currency: ارز مبدأ
            
        Returns:
            Dict[str, CurrencyPair]: دیکشنری از ارز مقصد به جفت ارز
        """
        if base_currency not in Currency.SUPPORTED_CURRENCIES:
            logger.error(f"ارز '{base_currency}' پشتیبانی نمی‌شود")
            return {}
            
        result = {}
        for quote_currency in Currency.SUPPORTED_CURRENCIES:
            if quote_currency == base_currency:
                continue
                
            rate = self.get_rate(base_currency, quote_currency)
            if rate:
                result[quote_currency] = rate
                
        return result
    
    def _get_rate_from_db(self, base_currency: str, quote_currency: str, max_age_hours: int = 6) -> Optional[CurrencyPair]:
        """
        دریافت نرخ تبدیل از دیتابیس.
        
        Args:
            base_currency: ارز مبدأ
            quote_currency: ارز مقصد
            max_age_hours: حداکثر عمر داده به ساعت
            
        Returns:
            Optional[CurrencyPair]: جفت ارز و نرخ تبدیل یا None در صورت عدم وجود یا قدیمی بودن
        """
        try:
            # محاسبه حداقل زمان مجاز
            min_timestamp = get_current_datetime() - timedelta(hours=max_age_hours)
            
            # دریافت آخرین نرخ از دیتابیس
            rate_data = self.db.execute(
                """
                SELECT base_currency, quote_currency, rate, timestamp, source
                FROM currency_rates
                WHERE base_currency = ? AND quote_currency = ? AND timestamp > ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (base_currency, quote_currency, min_timestamp)
            )
            
            if not rate_data:
                return None
                
            rate_row = rate_data[0]
            
            # ساخت آبجکت جفت ارز
            return CurrencyPair(
                base_currency=rate_row[0],
                quote_currency=rate_row[1],
                rate=rate_row[2],
                timestamp=rate_row[3] if isinstance(rate_row[3], datetime) else datetime.fromisoformat(rate_row[3]),
                source=rate_row[4]
            )
            
        except Exception as e:
            logger.error(f"خطا در دریافت نرخ ارز از دیتابیس: {e}")
            return None
    
    def _save_rate_to_db(self, currency_pair: CurrencyPair) -> bool:
        """
        ذخیره نرخ تبدیل در دیتابیس.
        
        Args:
            currency_pair: جفت ارز و نرخ تبدیل
            
        Returns:
            bool: True در صورت موفقیت، False در صورت خطا
        """
        try:
            # ذخیره در دیتابیس
            self.db.execute(
                """
                INSERT INTO currency_rates (base_currency, quote_currency, rate, timestamp, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    currency_pair.base_currency,
                    currency_pair.quote_currency,
                    currency_pair.rate,
                    currency_pair.timestamp,
                    currency_pair.source
                )
            )
            
            return True
            
        except Exception as e:
            logger.error(f"خطا در ذخیره نرخ ارز در دیتابیس: {e}")
            return False
    
    def _get_rate_from_api(self, base_currency: str, quote_currency: str) -> Optional[CurrencyPair]:
        """
        دریافت نرخ تبدیل از API های خارجی.
        
        Args:
            base_currency: ارز مبدأ
            quote_currency: ارز مقصد
            
        Returns:
            Optional[CurrencyPair]: جفت ارز و نرخ تبدیل یا None در صورت عدم دسترسی
        """
        # انتخاب API مناسب بر اساس نوع ارزها
        if self._is_fiat(base_currency) and self._is_fiat(quote_currency):
            # هر دو ارز فیات هستند، از API ارز استفاده می‌کنیم
            return self._get_fiat_rate(base_currency, quote_currency)
            
        elif not self._is_fiat(base_currency) and self._is_fiat(quote_currency):
            # ارز مبدأ رمزارز و مقصد فیات است
            return self._get_crypto_to_fiat_rate(base_currency, quote_currency)
            
        elif self._is_fiat(base_currency) and not self._is_fiat(quote_currency):
            # ارز مبدأ فیات و مقصد رمزارز است
            crypto_to_fiat = self._get_crypto_to_fiat_rate(quote_currency, base_currency)
            if crypto_to_fiat:
                # معکوس کردن نرخ
                return CurrencyPair(
                    base_currency=base_currency,
                    quote_currency=quote_currency,
                    rate=1.0 / crypto_to_fiat.rate,
                    timestamp=crypto_to_fiat.timestamp,
                    source=crypto_to_fiat.source
                )
            return None
            
        else:
            # هر دو ارز رمزارز هستند
            # ابتدا تبدیل به دلار و سپس از دلار به ارز مقصد
            crypto1_to_usd = self._get_crypto_to_fiat_rate(base_currency, "USD")
            crypto2_to_usd = self._get_crypto_to_fiat_rate(quote_currency, "USD")
            
            if crypto1_to_usd and crypto2_to_usd:
                # محاسبه نرخ
                rate = crypto1_to_usd.rate / crypto2_to_usd.rate
                
                return CurrencyPair(
                    base_currency=base_currency,
                    quote_currency=quote_currency,
                    rate=rate,
                    timestamp=get_current_datetime(),
                    source="computed"
                )
            
            return None
    
    def _is_fiat(self, currency_code: str) -> bool:
        """
        بررسی آیا ارز موردنظر فیات است یا خیر.
        
        Args:
            currency_code: کد ارز
            
        Returns:
            bool: True اگر ارز فیات باشد، False اگر رمزارز باشد
        """
        if currency_code not in Currency.SUPPORTED_CURRENCIES:
            return False
            
        return Currency.SUPPORTED_CURRENCIES[currency_code]["is_fiat"]
    
    def _get_fiat_rate(self, base_currency: str, quote_currency: str) -> Optional[CurrencyPair]:
        """
        دریافت نرخ تبدیل بین دو ارز فیات از API.
        
        Args:
            base_currency: ارز مبدأ
            quote_currency: ارز مقصد
            
        Returns:
            Optional[CurrencyPair]: جفت ارز و نرخ تبدیل یا None در صورت عدم دسترسی
        """
        # بررسی تنظیمات API
        provider_config = self.api_providers.get("exchangerate-api")
        if not provider_config or not provider_config["enabled"] or not provider_config["api_key"]:
            logger.error("API ارز فیات تنظیم نشده است")
            return None
            
        # بررسی پشتیبانی ارزها
        if base_currency not in provider_config["supported_currencies"] or quote_currency not in provider_config["supported_currencies"]:
            logger.error(f"یکی از ارزهای {base_currency} یا {quote_currency} توسط API پشتیبانی نمی‌شود")
            return None
            
        try:
            # ساخت URL درخواست
            url = provider_config["base_url"].format(api_key=provider_config["api_key"], base_currency=base_currency)
            
            # ارسال درخواست
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # بررسی موفقیت درخواست
            if data.get("result") != "success":
                logger.error(f"خطا در درخواست API: {data.get('error')}")
                return None
                
            # دریافت نرخ تبدیل
            rates = data.get("conversion_rates", {})
            if quote_currency not in rates:
                logger.error(f"نرخ تبدیل برای {quote_currency} یافت نشد")
                return None
                
            rate = rates[quote_currency]
            
            # ساخت آبجکت جفت ارز
            return CurrencyPair(
                base_currency=base_currency,
                quote_currency=quote_currency,
                rate=rate,
                timestamp=get_current_datetime(),
                source="exchangerate-api"
            )
            
        except Exception as e:
            logger.error(f"خطا در دریافت نرخ ارز فیات از API: {e}")
            return None
    
    def _get_crypto_to_fiat_rate(self, crypto_currency: str, fiat_currency: str) -> Optional[CurrencyPair]:
        """
        دریافت نرخ تبدیل رمزارز به ارز فیات از API.
        
        Args:
            crypto_currency: رمزارز
            fiat_currency: ارز فیات
            
        Returns:
            Optional[CurrencyPair]: جفت ارز و نرخ تبدیل یا None در صورت عدم دسترسی
        """
        # بررسی تنظیمات API
        provider_config = self.api_providers.get("coinmarketcap")
        if not provider_config or not provider_config["enabled"] or not provider_config["api_key"]:
            logger.error("API رمزارز تنظیم نشده است")
            return None
            
        # بررسی پشتیبانی ارزها
        if crypto_currency not in provider_config["supported_currencies"]:
            logger.error(f"رمزارز {crypto_currency} توسط API پشتیبانی نمی‌شود")
            return None
            
        try:
            # تنظیم پارامترهای درخواست
            params = {
                "symbol": crypto_currency,
                "convert": fiat_currency
            }
            
            headers = {
                "X-CMC_PRO_API_KEY": provider_config["api_key"],
                "Accept": "application/json"
            }
            
            # ارسال درخواست
            response = requests.get(provider_config["base_url"], params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # بررسی خطا
            if "status" not in data or data["status"]["error_code"] != 0:
                logger.error(f"خطا در درخواست API: {data.get('status', {}).get('error_message')}")
                return None
                
            # دریافت نرخ تبدیل
            if "data" not in data or crypto_currency not in data["data"]:
                logger.error(f"داده برای {crypto_currency} یافت نشد")
                return None
                
            quote_data = data["data"][crypto_currency]["quote"]
            if fiat_currency not in quote_data:
                logger.error(f"نرخ تبدیل برای {fiat_currency} یافت نشد")
                return None
                
            price = quote_data[fiat_currency]["price"]
            last_updated = quote_data[fiat_currency]["last_updated"]
            
            # تبدیل تاریخ به آبجکت datetime
            if isinstance(last_updated, str):
                timestamp = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            else:
                timestamp = get_current_datetime()
            
            # ساخت آبجکت جفت ارز
            return CurrencyPair(
                base_currency=crypto_currency,
                quote_currency=fiat_currency,
                rate=price,
                timestamp=timestamp,
                source="coinmarketcap"
            )
            
        except Exception as e:
            logger.error(f"خطا در دریافت نرخ رمزارز از API: {e}")
            return None
    
    def update_all_rates(self) -> Dict[str, bool]:
        """
        به‌روزرسانی تمام نرخ‌های ارز.
        
        Returns:
            Dict[str, bool]: وضعیت به‌روزرسانی هر ارز
        """
        result = {}
        
        # به‌روزرسانی ارزهای فیات
        fiat_currencies = [code for code, info in Currency.SUPPORTED_CURRENCIES.items() if info["is_fiat"]]
        crypto_currencies = [code for code, info in Currency.SUPPORTED_CURRENCIES.items() if not info["is_fiat"]]
        
        # به‌روزرسانی از USD به سایر ارزهای فیات
        usd_rates = self._get_fiat_rates_from_api("USD")
        if usd_rates:
            for currency, rate in usd_rates.items():
                if currency in fiat_currencies and currency != "USD":
                    currency_pair = CurrencyPair(
                        base_currency="USD",
                        quote_currency=currency,
                        rate=rate,
                        timestamp=get_current_datetime(),
                        source="exchangerate-api"
                    )
                    self._save_rate_to_db(currency_pair)
                    result[f"USD/{currency}"] = True
        
        # به‌روزرسانی از سایر ارزهای فیات به USD
        for fiat in fiat_currencies:
            if fiat != "USD":
                rate = self.get_rate(fiat, "USD")
                if rate:
                    result[f"{fiat}/USD"] = True
                else:
                    result[f"{fiat}/USD"] = False
        
        # به‌روزرسانی رمزارزها به USD
        for crypto in crypto_currencies:
            rate = self._get_crypto_to_fiat_rate(crypto, "USD")
            if rate:
                self._save_rate_to_db(rate)
                result[f"{crypto}/USD"] = True
            else:
                result[f"{crypto}/USD"] = False
        
        # پاکسازی کش
        exchange_rates_cache.clear()
        
        return result
    
    def _get_fiat_rates_from_api(self, base_currency: str) -> Dict[str, float]:
        """
        دریافت نرخ تبدیل یک ارز فیات به سایر ارزهای فیات از API.
        
        Args:
            base_currency: ارز مبدأ
            
        Returns:
            Dict[str, float]: دیکشنری از ارز مقصد به نرخ تبدیل
        """
        # بررسی تنظیمات API
        provider_config = self.api_providers.get("exchangerate-api")
        if not provider_config or not provider_config["enabled"] or not provider_config["api_key"]:
            logger.error("API ارز فیات تنظیم نشده است")
            return {}
            
        # بررسی پشتیبانی ارز مبدأ
        if base_currency not in provider_config["supported_currencies"]:
            logger.error(f"ارز {base_currency} توسط API پشتیبانی نمی‌شود")
            return {}
            
        try:
            # ساخت URL درخواست
            url = provider_config["base_url"].format(api_key=provider_config["api_key"], base_currency=base_currency)
            
            # ارسال درخواست
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # بررسی موفقیت درخواست
            if data.get("result") != "success":
                logger.error(f"خطا در درخواست API: {data.get('error')}")
                return {}
                
            # دریافت نرخ‌های تبدیل
            rates = data.get("conversion_rates", {})
            
            # فیلتر کردن ارزهای پشتیبانی شده 
            supported_rates = {}
            for currency, rate in rates.items():
                if currency in provider_config["supported_currencies"]:
                    supported_rates[currency] = rate
                    
            return supported_rates
            
        except Exception as e:
            logger.error(f"خطا در دریافت نرخ‌های ارز فیات از API: {e}")
            return {}