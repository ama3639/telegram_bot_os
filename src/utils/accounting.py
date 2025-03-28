#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول توابع کمکی حسابداری

این ماژول شامل توابع مفید برای محاسبات مالی، فرمت‌بندی واحدهای پولی و
عملیات مرتبط با حسابداری است.
"""

import locale
import decimal
import re
from typing import Dict, Any, Optional, Tuple, Union, List
from decimal import Decimal
import json
import uuid
import datetime
from src.utils.timezone_utils import get_current_datetime

from src.core.config import Config

# تنظیم دقت محاسبات اعشاری
decimal.getcontext().prec = 10


def format_currency(
    amount: Union[float, Decimal, str],
    currency: str,
    locale_str: str = "en_US",
    show_symbol: bool = True,
    decimal_places: int = 2
) -> str:
    """
    فرمت‌بندی مقدار پولی با قالب مناسب و نماد ارز
    
    :param amount: مقدار پولی
    :param currency: کد ارز (مانند USD, EUR, BTC)
    :param locale_str: تنظیمات محلی برای فرمت‌بندی اعداد
    :param show_symbol: نمایش نماد ارز
    :param decimal_places: تعداد ارقام اعشار
    :return: رشته فرمت‌بندی شده
    """
    # تبدیل مقدار به Decimal برای دقت بیشتر
    if isinstance(amount, str):
        amount = Decimal(amount)
    elif isinstance(amount, float):
        amount = Decimal(str(amount))
        
    # گرد کردن به تعداد رقم اعشار مورد نظر
    amount = amount.quantize(Decimal(f'0.{"0" * decimal_places}'))
    
    # برای واحدهای رمز ارز، فرمت خاص استفاده می‌کنیم
    crypto_currencies = ["BTC", "ETH", "LTC", "XRP", "BCH", "BNB", "USDT", "USDC", "DOT", "ADA"]
    
    if currency.upper() in crypto_currencies:
        # رمز ارزها معمولاً با 8 رقم اعشار نمایش داده می‌شوند
        if currency.upper() == "BTC":
            symbol = "₿" if show_symbol else ""
            decimal_places = max(decimal_places, 8)
            formatted = f"{amount:.{decimal_places}f}"
            return f"{symbol}{formatted}"
        else:
            # سایر رمز ارزها
            formatted = f"{amount:.{decimal_places}f}"
            symbol = f" {currency}" if show_symbol else ""
            return f"{formatted}{symbol}"
    
    # برای ارزهای فیات از امکانات locale استفاده می‌کنیم
    try:
        locale.setlocale(locale.LC_ALL, locale_str)
        if locale_str.startswith("fa") or locale_str.startswith("ar"):
            # برای زبان‌های راست به چپ
            formatter = locale.format_string(f'%.{decimal_places}f', float(amount), grouping=True)
            if show_symbol:
                currency_symbols = {
                    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
                    "IRR": "ریال", "IRT": "تومان", "AED": "د.إ",
                    "SAR": "ر.س", "TRY": "₺"
                }
                symbol = currency_symbols.get(currency.upper(), currency)
                return f"{formatter} {symbol}"
            return formatter
        else:
            if show_symbol:
                return locale.currency(float(amount), symbol=True, grouping=True)
            else:
                return locale.format_string(f'%.{decimal_places}f', float(amount), grouping=True)
    except (locale.Error, TypeError):
        # اگر مشکلی در تنظیم locale باشد، از روش ساده استفاده می‌کنیم
        formatted = f"{amount:.{decimal_places}f}"
        if "." in formatted:
            integer_part, decimal_part = formatted.split(".")
            integer_part = re.sub(r'(\d)(?=(\d{3})+(?!\d))', r'\1,', integer_part)
            formatted = f"{integer_part}.{decimal_part}"
            
        if show_symbol:
            currency_symbols = {
                "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
                "IRR": "ریال", "IRT": "تومان", "AED": "د.إ",
                "SAR": "ر.س", "TRY": "₺"
            }
            symbol = currency_symbols.get(currency.upper(), currency)
            
            # قرار دادن نماد در محل مناسب
            if currency.upper() in ["IRR", "IRT", "SAR", "AED"]:
                return f"{formatted} {symbol}"
            else:
                return f"{symbol}{formatted}"
        
        return formatted


def calculate_fee(
    amount: Union[float, Decimal, str],
    fee_percentage: Union[float, Decimal, str],
    min_fee: Optional[Union[float, Decimal, str]] = None,
    max_fee: Optional[Union[float, Decimal, str]] = None
) -> Decimal:
    """
    محاسبه کارمزد بر اساس درصد و با در نظر گرفتن حداقل و حداکثر کارمزد
    
    :param amount: مقدار اصلی تراکنش
    :param fee_percentage: درصد کارمزد
    :param min_fee: حداقل کارمزد (اختیاری)
    :param max_fee: حداکثر کارمزد (اختیاری)
    :return: مقدار کارمزد
    """
    # تبدیل همه مقادیر به Decimal
    if isinstance(amount, str):
        amount = Decimal(amount)
    elif isinstance(amount, float):
        amount = Decimal(str(amount))
        
    if isinstance(fee_percentage, str):
        fee_percentage = Decimal(fee_percentage)
    elif isinstance(fee_percentage, float):
        fee_percentage = Decimal(str(fee_percentage))
        
    # محاسبه کارمزد اولیه
    fee = amount * (fee_percentage / Decimal("100.0"))
    
    # اعمال حداقل کارمزد
    if min_fee is not None:
        if isinstance(min_fee, str):
            min_fee = Decimal(min_fee)
        elif isinstance(min_fee, float):
            min_fee = Decimal(str(min_fee))
            
        fee = max(fee, min_fee)
    
    # اعمال حداکثر کارمزد
    if max_fee is not None:
        if isinstance(max_fee, str):
            max_fee = Decimal(max_fee)
        elif isinstance(max_fee, float):
            max_fee = Decimal(str(max_fee))
            
        fee = min(fee, max_fee)
    
    # گرد کردن به 2 رقم اعشار
    return fee.quantize(Decimal("0.01"))


def verify_payment_amount(
    expected_amount: Union[float, Decimal, str],
    actual_amount: Union[float, Decimal, str],
    tolerance_percentage: Union[float, Decimal, str] = "0.5"
) -> bool:
    """
    بررسی صحت مبلغ پرداختی با در نظر گرفتن خطای مجاز
    
    :param expected_amount: مبلغ مورد انتظار
    :param actual_amount: مبلغ واقعی پرداخت شده
    :param tolerance_percentage: درصد خطای مجاز
    :return: صحت مبلغ پرداختی
    """
    # تبدیل همه مقادیر به Decimal
    if isinstance(expected_amount, str):
        expected_amount = Decimal(expected_amount)
    elif isinstance(expected_amount, float):
        expected_amount = Decimal(str(expected_amount))
        
    if isinstance(actual_amount, str):
        actual_amount = Decimal(actual_amount)
    elif isinstance(actual_amount, float):
        actual_amount = Decimal(str(actual_amount))
        
    if isinstance(tolerance_percentage, str):
        tolerance_percentage = Decimal(tolerance_percentage)
    elif isinstance(tolerance_percentage, float):
        tolerance_percentage = Decimal(str(tolerance_percentage))
    
    # محاسبه حداقل و حداکثر مبلغ قابل قبول
    tolerance = expected_amount * (tolerance_percentage / Decimal("100.0"))
    min_acceptable = expected_amount - tolerance
    max_acceptable = expected_amount + tolerance
    
    # بررسی قرار داشتن مبلغ واقعی در محدوده مجاز
    return min_acceptable <= actual_amount <= max_acceptable


def prepare_invoice(
    items: List[Dict[str, Any]],
    user_id: int,
    currency: str = "USD",
    discount_code: Optional[str] = None,
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    آماده‌سازی فاکتور برای پرداخت
    
    :param items: لیست آیتم‌های فاکتور (هر آیتم شامل name, quantity, unit_price)
    :param user_id: شناسه کاربر
    :param currency: واحد ارزی
    :param discount_code: کد تخفیف (اختیاری)
    :param config: تنظیمات سیستم (اختیاری)
    :return: دیکشنری اطلاعات فاکتور
    """
    if config is None:
        from ..core.config import Config
        config = Config()
    
    # تاریخ و زمان صدور فاکتور
    now = datetime.get_current_datetime()
    
    # محاسبه مجموع مبلغ آیتم‌ها
    subtotal = Decimal("0.0")
    invoice_items = []
    
    for item in items:
        name = item.get("name", "")
        quantity = Decimal(str(item.get("quantity", 1)))
        unit_price = Decimal(str(item.get("unit_price", 0)))
        total_price = quantity * unit_price
        
        invoice_items.append({
            "name": name,
            "description": item.get("description", ""),
            "quantity": int(quantity),
            "unit_price": float(unit_price),
            "total_price": float(total_price)
        })
        
        subtotal += total_price
    
    # اعمال تخفیف (اگر کد تخفیف وجود داشته باشد)
    discount_amount = Decimal("0.0")
    discount_percentage = Decimal("0.0")
    
    if discount_code:
        discount_info = validate_discount_code(discount_code, user_id, subtotal, config)
        if discount_info["valid"]:
            discount_percentage = Decimal(str(discount_info["percentage"]))
            discount_amount = subtotal * (discount_percentage / Decimal("100.0"))
    
    # محاسبه مالیات
    tax_percentage = Decimal(str(config.get("TAX_PERCENTAGE", "0.0")))
    tax_amount = (subtotal - discount_amount) * (tax_percentage / Decimal("100.0"))
    
    # محاسبه کارمزد پردازش پرداخت
    payment_fee_percentage = Decimal(str(config.get("PAYMENT_FEE_PERCENTAGE", "0.0")))
    payment_fee_min = config.get("PAYMENT_FEE_MIN", None)
    payment_fee_max = config.get("PAYMENT_FEE_MAX", None)
    
    if payment_fee_min:
        payment_fee_min = Decimal(str(payment_fee_min))
    if payment_fee_max:
        payment_fee_max = Decimal(str(payment_fee_max))
    
    payment_fee = calculate_fee(
        subtotal - discount_amount,
        payment_fee_percentage,
        payment_fee_min,
        payment_fee_max
    )
    
    # محاسبه مبلغ کل
    total_amount = subtotal - discount_amount + tax_amount + payment_fee
    
    # ایجاد شناسه منحصر به فرد برای فاکتور
    invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}-{now.strftime('%Y%m%d')}"
    
    # ساخت دیکشنری فاکتور
    invoice = {
        "invoice_id": invoice_id,
        "user_id": user_id,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "currency": currency,
        "items": invoice_items,
        "subtotal": float(subtotal),
        "discount_code": discount_code if discount_code else None,
        "discount_percentage": float(discount_percentage),
        "discount_amount": float(discount_amount),
        "tax_percentage": float(tax_percentage),
        "tax_amount": float(tax_amount),
        "payment_fee": float(payment_fee),
        "total_amount": float(total_amount),
        "status": "pending",
        "due_date": (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
        "notes": config.get("INVOICE_NOTES", ""),
        "terms": config.get("INVOICE_TERMS", "")
    }
    
    return invoice


def validate_discount_code(
    code: str,
    user_id: int,
    amount: Union[float, Decimal, str],
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    اعتبارسنجی کد تخفیف و بازگرداندن اطلاعات مربوط به آن
    
    :param code: کد تخفیف وارد شده
    :param user_id: شناسه کاربر
    :param amount: مبلغ کل سفارش
    :param config: تنظیمات سیستم (اختیاری)
    :return: دیکشنری حاوی اطلاعات اعتبارسنجی
    """
    if config is None:
        from ..core.config import Config
        config = Config()
    
    # تبدیل مبلغ به Decimal
    if isinstance(amount, str):
        amount = Decimal(amount)
    elif isinstance(amount, float):
        amount = Decimal(str(amount))
    
    # دریافت لیست کدهای تخفیف از تنظیمات
    discount_codes_str = config.get("DISCOUNT_CODES", "{}")
    
    try:
        discount_codes = json.loads(discount_codes_str)
    except json.JSONDecodeError:
        discount_codes = {}
    
    # اگر کد تخفیف در لیست وجود نداشته باشد
    code = code.upper().strip()
    if code not in discount_codes:
        return {
            "valid": False,
            "message": "کد تخفیف نامعتبر است.",
            "percentage": 0
        }
    
    code_info = discount_codes[code]
    
    # بررسی تاریخ انقضای کد تخفیف
    if "expiry_date" in code_info:
        expiry_date = datetime.datetime.strptime(code_info["expiry_date"], "%Y-%m-%d")
        if datetime.get_current_datetime() > expiry_date:
            return {
                "valid": False,
                "message": "کد تخفیف منقضی شده است.",
                "percentage": 0
            }
    
    # بررسی محدودیت تعداد استفاده
    if "max_uses" in code_info and "current_uses" in code_info:
        if code_info["current_uses"] >= code_info["max_uses"]:
            return {
                "valid": False,
                "message": "کد تخفیف به حداکثر تعداد استفاده رسیده است.",
                "percentage": 0
            }
    
    # بررسی حداقل مبلغ سفارش
    if "min_amount" in code_info:
        min_amount = Decimal(str(code_info["min_amount"]))
        if amount < min_amount:
            return {
                "valid": False,
                "message": f"حداقل مبلغ سفارش برای استفاده از این کد تخفیف {min_amount} است.",
                "percentage": 0
            }
    
    # بررسی محدودیت کاربران خاص
    if "allowed_users" in code_info:
        if user_id not in code_info["allowed_users"]:
            return {
                "valid": False,
                "message": "این کد تخفیف برای شما قابل استفاده نیست.",
                "percentage": 0
            }
    
    # کد تخفیف معتبر است
    return {
        "valid": True,
        "message": "کد تخفیف اعمال شد.",
        "percentage": code_info.get("percentage", 0),
        "code_info": code_info
    }


def calculate_discount(
    amount: Union[float, Decimal, str],
    discount_percentage: Union[float, Decimal, str]
) -> Decimal:
    """
    محاسبه مبلغ تخفیف بر اساس درصد
    
    :param amount: مبلغ اصلی
    :param discount_percentage: درصد تخفیف
    :return: مبلغ تخفیف
    """
    # تبدیل مقادیر به Decimal
    if isinstance(amount, str):
        amount = Decimal(amount)
    elif isinstance(amount, float):
        amount = Decimal(str(amount))
        
    if isinstance(discount_percentage, str):
        discount_percentage = Decimal(discount_percentage)
    elif isinstance(discount_percentage, float):
        discount_percentage = Decimal(str(discount_percentage))
    
    # محاسبه مبلغ تخفیف
    discount_amount = amount * (discount_percentage / Decimal("100.0"))
    
    # گرد کردن به 2 رقم اعشار
    return discount_amount.quantize(Decimal("0.01"))


def convert_currency_amounts(
    amounts: Dict[str, Union[float, Decimal, str]],
    target_currency: str,
    exchange_rates: Dict[str, float]
) -> Dict[str, Decimal]:
    """
    تبدیل مبالغ چند ارز به یک ارز هدف
    
    :param amounts: دیکشنری مبالغ به تفکیک ارز
    :param target_currency: ارز هدف
    :param exchange_rates: دیکشنری نرخ‌های تبدیل ارز نسبت به ارز هدف
    :return: دیکشنری مبالغ تبدیل شده به ارز هدف
    """
    result = {}
    
    for currency, amount in amounts.items():
        # تبدیل مبلغ به Decimal
        if isinstance(amount, str):
            amount = Decimal(amount)
        elif isinstance(amount, float):
            amount = Decimal(str(amount))
        
        # اگر ارز مبدا و مقصد یکسان باشد
        if currency == target_currency:
            result[currency] = amount
            continue
        
        # بررسی وجود نرخ تبدیل
        if currency not in exchange_rates:
            continue
        
        # تبدیل ارز
        rate = Decimal(str(exchange_rates[currency]))
        converted_amount = amount * rate
        
        # گرد کردن به 2 رقم اعشار
        result[currency] = converted_amount.quantize(Decimal("0.01"))
    
    return result