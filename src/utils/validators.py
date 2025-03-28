#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول اعتبارسنجی‌ها

این ماژول شامل توابع متنوعی برای اعتبارسنجی ورودی‌ها و داده‌های مختلف است،
از جمله اعتبارسنجی ایمیل، شماره تلفن، نام کاربری، مبالغ و غیره.
"""

import re
import json
import uuid
import ipaddress
from typing import Dict, List, Optional, Union, Any, Tuple
import datetime
import unicodedata

from src.utils.logger import get_logger

# تنظیم لاگر
logger = get_logger(__name__)


def validate_email(email: str) -> Dict[str, Any]:
    """
    اعتبارسنجی آدرس ایمیل
    
    :param email: آدرس ایمیل
    :return: نتیجه اعتبارسنجی
    """
    # الگوی عمومی آدرس ایمیل
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    
    # بررسی الگو
    if not re.match(pattern, email):
        return {
            'valid': False,
            'message': 'فرمت آدرس ایمیل نامعتبر است'
        }
    
    # بررسی طول
    if len(email) > 254:
        return {
            'valid': False,
            'message': 'آدرس ایمیل بیش از حد طولانی است'
        }
    
    # بررسی بخش‌های مختلف
    local_part, domain = email.rsplit('@', 1)
    
    # بررسی بخش محلی
    if len(local_part) > 64:
        return {
            'valid': False,
            'message': 'بخش محلی آدرس ایمیل بیش از حد طولانی است'
        }
    
    # بررسی دامنه
    if not re.match(r'^[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$', domain):
        return {
            'valid': False,
            'message': 'دامنه آدرس ایمیل نامعتبر است'
        }
    
    return {
        'valid': True,
        'email': email.lower(),
        'local_part': local_part,
        'domain': domain
    }


def validate_phone(
    phone: str,
    country_code: Optional[str] = None,
    allow_spaces: bool = False
) -> Dict[str, Any]:
    """
    اعتبارسنجی شماره تلفن
    
    :param phone: شماره تلفن
    :param country_code: کد کشور (اختیاری)
    :param allow_spaces: آیا فاصله در شماره تلفن مجاز است
    :return: نتیجه اعتبارسنجی
    """
    # حذف کاراکترهای اضافی
    cleaned = phone.strip()
    
    # جایگزینی فاصله‌ها اگر مجاز نباشند
    if not allow_spaces:
        cleaned = cleaned.replace(' ', '')
    
    # حذف کاراکترهای خاص مجاز
    cleaned = cleaned.replace('-', '').replace('(', '').replace(')', '').replace('+', '')
    
    # بررسی عددی بودن
    if not cleaned.isdigit():
        return {
            'valid': False,
            'message': 'شماره تلفن باید فقط شامل اعداد، فاصله و کاراکترهای مجاز باشد'
        }
    
    # بررسی طول
    if len(cleaned) < 8 or len(cleaned) > 15:
        return {
            'valid': False,
            'message': 'طول شماره تلفن نامعتبر است (باید بین 8 تا 15 رقم باشد)'
        }
    
    # اگر کد کشور ارائه شده باشد، بررسی کد کشور
    if country_code:
        country_code = country_code.strip().replace('+', '')
        
        # بررسی ایران
        if country_code == '98':
            # بررسی شماره تلفن ایران (فرمت: 9xxxxxxxxx)
            if not (cleaned.startswith('9') and len(cleaned) == 10):
                return {
                    'valid': False,
                    'message': 'فرمت شماره تلفن ایران نامعتبر است (باید با 9 شروع شود و 10 رقم باشد)'
                }
        
        # بررسی کشورهای دیگر را می‌توان اضافه کرد
    
    # تنظیم فرمت
    if cleaned.startswith('00'):
        formatted = '+' + cleaned[2:]
    elif country_code and not phone.startswith('+'):
        formatted = f'+{country_code}{cleaned}'
    elif not phone.startswith('+') and len(cleaned) == 10 and cleaned.startswith('9'):
        # احتمالاً شماره ایران است
        formatted = f'+98{cleaned}'
    else:
        formatted = phone
    
    return {
        'valid': True,
        'phone': cleaned,
        'formatted': formatted,
        'country_code': country_code
    }


# تابع validate_phone_number به عنوان نام مستعار برای validate_phone اضافه شده است
def validate_phone_number(
    phone: str,
    country_code: Optional[str] = None,
    allow_spaces: bool = False
) -> Dict[str, Any]:
    """
    اعتبارسنجی شماره تلفن (نام مستعار برای validate_phone)
    
    :param phone: شماره تلفن
    :param country_code: کد کشور (اختیاری)
    :param allow_spaces: آیا فاصله در شماره تلفن مجاز است
    :return: نتیجه اعتبارسنجی
    """
    return validate_phone(phone, country_code, allow_spaces)


def validate_username(username: str, min_length: int = 3, max_length: int = 32) -> Dict[str, Any]:
    """
    اعتبارسنجی نام کاربری
    
    :param username: نام کاربری
    :param min_length: حداقل طول
    :param max_length: حداکثر طول
    :return: نتیجه اعتبارسنجی
    """
    # بررسی طول
    if len(username) < min_length:
        return {
            'valid': False,
            'message': f'نام کاربری باید حداقل {min_length} کاراکتر باشد'
        }
    
    if len(username) > max_length:
        return {
            'valid': False,
            'message': f'نام کاربری نباید بیشتر از {max_length} کاراکتر باشد'
        }
    
    # بررسی کاراکترهای مجاز
    if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
        return {
            'valid': False,
            'message': 'نام کاربری فقط می‌تواند شامل حروف انگلیسی، اعداد، نقطه، خط تیره و زیرخط باشد'
        }
    
    # بررسی شروع با حرف یا عدد
    if not re.match(r'^[a-zA-Z0-9]', username):
        return {
            'valid': False,
            'message': 'نام کاربری باید با حرف یا عدد شروع شود'
        }
    
    return {
        'valid': True,
        'username': username.lower()
    }


def validate_password(
    password: str,
    min_length: int = 8,
    require_uppercase: bool = True,
    require_lowercase: bool = True,
    require_digit: bool = True,
    require_special: bool = False
) -> Dict[str, Any]:
    """
    اعتبارسنجی رمز عبور
    
    :param password: رمز عبور
    :param min_length: حداقل طول
    :param require_uppercase: نیاز به حروف بزرگ
    :param require_lowercase: نیاز به حروف کوچک
    :param require_digit: نیاز به اعداد
    :param require_special: نیاز به کاراکترهای ویژه
    :return: نتیجه اعتبارسنجی
    """
    issues = []
    
    # بررسی طول
    if len(password) < min_length:
        issues.append(f'رمز عبور باید حداقل {min_length} کاراکتر باشد')
    
    # بررسی حروف بزرگ
    if require_uppercase and not re.search(r'[A-Z]', password):
        issues.append('رمز عبور باید شامل حداقل یک حرف بزرگ باشد')
    
    # بررسی حروف کوچک
    if require_lowercase and not re.search(r'[a-z]', password):
        issues.append('رمز عبور باید شامل حداقل یک حرف کوچک باشد')
    
    # بررسی اعداد
    if require_digit and not re.search(r'\d', password):
        issues.append('رمز عبور باید شامل حداقل یک عدد باشد')
    
    # بررسی کاراکترهای ویژه
    if require_special and not re.search(r'[!@#$%^&*()_\-+={\[\]}\|:;"\'<>,.?/]', password):
        issues.append('رمز عبور باید شامل حداقل یک کاراکتر ویژه باشد')
    
    # بررسی فضای خالی
    if re.search(r'\s', password):
        issues.append('رمز عبور نباید شامل فضای خالی باشد')
    
    if issues:
        return {
            'valid': False,
            'message': ' '.join(issues),
            'issues': issues
        }
    
    return {
        'valid': True
    }


def validate_amount(
    amount: Union[str, int, float],
    min_value: float = 0.0,
    max_value: Optional[float] = None,
    decimal_places: Optional[int] = None
) -> Dict[str, Any]:
    """
    اعتبارسنجی مبلغ
    
    :param amount: مبلغ
    :param min_value: حداقل مقدار مجاز
    :param max_value: حداکثر مقدار مجاز (اختیاری)
    :param decimal_places: تعداد رقم اعشار (اختیاری)
    :return: نتیجه اعتبارسنجی
    """
    try:
        # تبدیل به float
        if isinstance(amount, str):
            # پاکسازی کاراکترهای اضافی
            amount = amount.strip().replace(',', '')
            
            # تبدیل ممیز فارسی به انگلیسی
            amount = amount.replace('٫', '.')
            
            # تبدیل اعداد فارسی به انگلیسی
            persian_nums = '۰۱۲۳۴۵۶۷۸۹'
            english_nums = '0123456789'
            translation_table = str.maketrans(persian_nums, english_nums)
            amount = amount.translate(translation_table)
        
        amount_float = float(amount)
        
        # بررسی حداقل مقدار
        if amount_float < min_value:
            return {
                'valid': False,
                'message': f'مبلغ نباید کمتر از {min_value} باشد'
            }
        
        # بررسی حداکثر مقدار
        if max_value is not None and amount_float > max_value:
            return {
                'valid': False,
                'message': f'مبلغ نباید بیشتر از {max_value} باشد'
            }
        
        # بررسی تعداد رقم اعشار
        if decimal_places is not None:
            str_amount = str(amount_float)
            if '.' in str_amount:
                _, decimal_part = str_amount.split('.')
                if len(decimal_part) > decimal_places:
                    return {
                        'valid': False,
                        'message': f'مبلغ نباید بیش از {decimal_places} رقم اعشار داشته باشد'
                    }
        
        return {
            'valid': True,
            'amount': amount_float
        }
    
    except ValueError:
        return {
            'valid': False,
            'message': 'مبلغ باید عدد باشد'
        }
    
    except Exception as e:
        logger.error(f"خطا در اعتبارسنجی مبلغ: {str(e)}")
        return {
            'valid': False,
            'message': 'خطا در اعتبارسنجی مبلغ'
        }


def validate_wallet_address(wallet_address: str, currency: str) -> Dict[str, Any]:
    """
    اعتبارسنجی آدرس کیف پول رمزارز
    
    :param wallet_address: آدرس کیف پول
    :param currency: نوع رمزارز
    :return: نتیجه اعتبارسنجی
    """
    currency = currency.upper()
    wallet_address = wallet_address.strip()
    
    # بررسی خالی نبودن
    if not wallet_address:
        return {
            'valid': False,
            'message': 'آدرس کیف پول نمی‌تواند خالی باشد'
        }
    
    # الگوهای مختلف برای رمزارزهای مختلف
    patterns = {
        'BTC': r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}$',  # بیت‌کوین
        'ETH': r'^0x[a-fA-F0-9]{40}$',  # اتریوم و توکن‌های ERC-20
        'LTC': r'^[LM][a-km-zA-HJ-NP-Z1-9]{26,33}$',  # لایت‌کوین
        'XRP': r'^r[0-9a-zA-Z]{24,34}$',  # ریپل
        'BCH': r'^[13][a-km-zA-HJ-NP-Z1-9]{33}$|^(bitcoincash:)?(q|p)[a-z0-9]{41}$',  # بیت‌کوین کش
        'DOGE': r'^D{1}[5-9A-HJ-NP-U]{1}[1-9A-HJ-NP-Za-km-z]{32}$',  # دوج‌کوین
        'TRX': r'^T[a-zA-Z0-9]{33}$',  # ترون
        'BSC': r'^0x[a-fA-F0-9]{40}$',  # بایننس اسمارت چین
        'BNB': r'^bnb1[a-z0-9]{38}$',  # بایننس چین
        'USDT': r'^0x[a-fA-F0-9]{40}$|^T[a-zA-Z0-9]{33}$',  # تتر (ERC-20 یا TRC-20)
        'ADA': r'^addr1[a-z0-9]{98}$|^Ae2[a-zA-Z0-9]{56}$',  # کاردانو
        'SOL': r'^[1-9A-HJ-NP-Za-km-z]{32,44}$'  # سولانا
    }
    
    # بررسی الگوی آدرس بر اساس نوع رمزارز
    if currency in patterns:
        pattern = patterns[currency]
        if not re.match(pattern, wallet_address):
            return {
                'valid': False,
                'message': f'فرمت آدرس {currency} نامعتبر است'
            }
    else:
        # برای رمزارزهایی که الگوی خاصی ندارند، فقط بررسی کلی
        if len(wallet_address) < 26 or len(wallet_address) > 100:
            return {
                'valid': False,
                'message': 'طول آدرس کیف پول نامعتبر است'
            }
    
    return {
        'valid': True,
        'wallet_address': wallet_address,
        'currency': currency
    }


def validate_url(url: str, allowed_schemes: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    اعتبارسنجی URL
    
    :param url: آدرس URL
    :param allowed_schemes: طرح‌های مجاز (http, https, و غیره)
    :return: نتیجه اعتبارسنجی
    """
    # تنظیم طرح‌های مجاز
    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']
    
    # الگوی عمومی URL
    pattern = r'^(?:(?:' + '|'.join(allowed_schemes) + r'):\/\/)(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?|localhost|(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?))(?::\d{1,5})?(?:\/[^\s]*)?$'
    
    # بررسی الگو
    if not re.match(pattern, url):
        return {
            'valid': False,
            'message': 'فرمت URL نامعتبر است'
        }
    
    # استخراج طرح (scheme)
    match = re.match(r'^(https?):\/\/', url)
    if match:
        scheme = match.group(1)
    else:
        scheme = ''
    
    # بررسی طرح
    if scheme not in allowed_schemes:
        return {
            'valid': False,
            'message': f'طرح URL باید یکی از {", ".join(allowed_schemes)} باشد'
        }
    
    return {
        'valid': True,
        'url': url,
        'scheme': scheme
    }


def validate_ip_address(ip: str, allowed_types: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    اعتبارسنجی آدرس IP
    
    :param ip: آدرس IP
    :param allowed_types: انواع مجاز ('ipv4', 'ipv6')
    :return: نتیجه اعتبارسنجی
    """
    # تنظیم انواع مجاز
    if allowed_types is None:
        allowed_types = ['ipv4', 'ipv6']
    
    try:
        # تلاش برای تبدیل به شیء آدرس IP
        ip_obj = ipaddress.ip_address(ip)
        
        # تعیین نوع
        ip_type = 'ipv6' if ip_obj.version == 6 else 'ipv4'
        
        # بررسی نوع مجاز
        if ip_type not in allowed_types:
            return {
                'valid': False,
                'message': f'نوع آدرس IP باید یکی از {", ".join(allowed_types)} باشد'
            }
        
        return {
            'valid': True,
            'ip': ip,
            'type': ip_type,
            'is_private': ip_obj.is_private,
            'is_loopback': ip_obj.is_loopback
        }
    
    except ValueError:
        return {
            'valid': False,
            'message': 'آدرس IP نامعتبر است'
        }


def validate_uuid(uuid_str: str) -> Dict[str, Any]:
    """
    اعتبارسنجی UUID
    
    :param uuid_str: رشته UUID
    :return: نتیجه اعتبارسنجی
    """
    try:
        # تلاش برای تبدیل به شیء UUID
        uuid_obj = uuid.UUID(uuid_str)
        
        return {
            'valid': True,
            'uuid': str(uuid_obj),
            'version': uuid_obj.version
        }
    
    except (ValueError, AttributeError):
        return {
            'valid': False,
            'message': 'فرمت UUID نامعتبر است'
        }


def validate_date(
    date_str: str,
    date_format: str = '%Y-%m-%d',
    min_date: Optional[Union[str, datetime.date]] = None,
    max_date: Optional[Union[str, datetime.date]] = None
) -> Dict[str, Any]:
    """
    اعتبارسنجی تاریخ
    
    :param date_str: رشته تاریخ
    :param date_format: قالب تاریخ
    :param min_date: حداقل تاریخ مجاز (اختیاری)
    :param max_date: حداکثر تاریخ مجاز (اختیاری)
    :return: نتیجه اعتبارسنجی
    """
    try:
        # تبدیل به شیء تاریخ
        date_obj = datetime.datetime.strptime(date_str, date_format).date()
        
        # تبدیل min_date و max_date به شیء تاریخ اگر رشته باشند
        if min_date and isinstance(min_date, str):
            min_date = datetime.datetime.strptime(min_date, date_format).date()
        
        if max_date and isinstance(max_date, str):
            max_date = datetime.datetime.strptime(max_date, date_format).date()
        
        # بررسی محدوده
        if min_date and date_obj < min_date:
            return {
                'valid': False,
                'message': f'تاریخ نباید قبل از {min_date.strftime(date_format)} باشد'
            }
        
        if max_date and date_obj > max_date:
            return {
                'valid': False,
                'message': f'تاریخ نباید بعد از {max_date.strftime(date_format)} باشد'
            }
        
        return {
            'valid': True,
            'date': date_obj,
            'formatted': date_obj.strftime(date_format)
        }
    
    except ValueError:
        return {
            'valid': False,
            'message': f'فرمت تاریخ نامعتبر است. فرمت صحیح: {date_format}'
        }


def validate_time(
    time_str: str,
    time_format: str = '%H:%M',
    min_time: Optional[Union[str, datetime.time]] = None,
    max_time: Optional[Union[str, datetime.time]] = None
) -> Dict[str, Any]:
    """
    اعتبارسنجی زمان
    
    :param time_str: رشته زمان
    :param time_format: قالب زمان
    :param min_time: حداقل زمان مجاز (اختیاری)
    :param max_time: حداکثر زمان مجاز (اختیاری)
    :return: نتیجه اعتبارسنجی
    """
    try:
        # تبدیل به شیء زمان
        time_obj = datetime.datetime.strptime(time_str, time_format).time()
        
        # تبدیل min_time و max_time به شیء زمان اگر رشته باشند
        if min_time and isinstance(min_time, str):
            min_time = datetime.datetime.strptime(min_time, time_format).time()
        
        if max_time and isinstance(max_time, str):
            max_time = datetime.datetime.strptime(max_time, time_format).time()
        
        # بررسی محدوده
        if min_time and time_obj < min_time:
            return {
                'valid': False,
                'message': f'زمان نباید قبل از {min_time.strftime(time_format)} باشد'
            }
        
        if max_time and time_obj > max_time:
            return {
                'valid': False,
                'message': f'زمان نباید بعد از {max_time.strftime(time_format)} باشد'
            }
        
        return {
            'valid': True,
            'time': time_obj,
            'formatted': time_obj.strftime(time_format)
        }
    
    except ValueError:
        return {
            'valid': False,
            'message': f'فرمت زمان نامعتبر است. فرمت صحیح: {time_format}'
        }


def validate_credit_card(card_number: str) -> Dict[str, Any]:
    """
    اعتبارسنجی شماره کارت اعتباری
    
    :param card_number: شماره کارت
    :return: نتیجه اعتبارسنجی
    """
    # حذف کاراکترهای اضافی
    card_number = re.sub(r'[^0-9]', '', card_number)
    
    # بررسی طول
    if len(card_number) < 13 or len(card_number) > 19:
        return {
            'valid': False,
            'message': 'طول شماره کارت نامعتبر است (باید بین 13 تا 19 رقم باشد)'
        }
    
    # بررسی الگوریتم Luhn
    # 1. معکوس کردن شماره کارت
    card_digits = [int(d) for d in card_number]
    card_digits.reverse()
    
    # 2. ضرب کردن ارقام با مضارب فرد در 2
    for i in range(1, len(card_digits), 2):
        card_digits[i] *= 2
        if card_digits[i] > 9:
            card_digits[i] -= 9
    
    # 3. جمع کردن همه ارقام
    total = sum(card_digits)
    
    # 4. بررسی بخش‌پذیری بر 10
    if total % 10 != 0:
        return {
            'valid': False,
            'message': 'شماره کارت نامعتبر است (الگوریتم Luhn)'
        }
    
    # تشخیص نوع کارت
    card_type = 'نامشخص'
    
    if re.match(r'^4[0-9]{12}(?:[0-9]{3})?$', card_number):
        card_type = 'Visa'
    elif re.match(r'^5[1-5][0-9]{14}$', card_number):
        card_type = 'MasterCard'
    elif re.match(r'^3[47][0-9]{13}$', card_number):
        card_type = 'American Express'
    elif re.match(r'^6(?:011|5[0-9]{2})[0-9]{12}$', card_number):
        card_type = 'Discover'
    elif re.match(r'^(?:2131|1800|35\d{3})\d{11}$', card_number):
        card_type = 'JCB'
    elif re.match(r'^62[0-9]{14,17}$', card_number):
        card_type = 'UnionPay'
    
    # بررسی شماره کارت‌های بانکی ایران (16 رقمی)
    if len(card_number) == 16 and card_number.startswith(('603799', '589210', '627412')):
        bank_codes = {
            '603799': 'بانک ملی ایران',
            '589210': 'بانک سپه',
            '627412': 'بانک اقتصاد نوین'
            # سایر بانک‌ها را می‌توان اضافه کرد
        }
        
        bank_code = card_number[:6]
        if bank_code in bank_codes:
            card_type = bank_codes[bank_code]
    
    return {
        'valid': True,
        'card_number': card_number,
        'type': card_type,
        'formatted': ' '.join([card_number[i:i+4] for i in range(0, len(card_number), 4)])
    }


def sanitize_string(
    input_str: str,
    max_length: Optional[int] = None,
    strip: bool = True,
    remove_html: bool = True
) -> str:
    """
    پاکسازی و تمیز کردن رشته ورودی
    
    :param input_str: رشته ورودی
    :param max_length: حداکثر طول مجاز (اختیاری)
    :param strip: حذف فضاهای خالی ابتدا و انتها
    :param remove_html: حذف تگ‌های HTML
    :return: رشته پاکسازی شده
    """
    if not input_str:
        return ""
    
    # استفاده از نوع رشته
    if not isinstance(input_str, str):
        input_str = str(input_str)
    
    # حذف فضاهای خالی ابتدا و انتها
    if strip:
        input_str = input_str.strip()
    
    # حذف تگ‌های HTML
    if remove_html:
        input_str = re.sub(r'<[^>]*>', '', input_str)
    
    # نرمال‌سازی کاراکترهای یونیکد
    input_str = unicodedata.normalize('NFKC', input_str)
    
    # محدود کردن طول
    if max_length is not None and len(input_str) > max_length:
        input_str = input_str[:max_length]
    
    return input_str


def is_valid_json(json_str: str) -> Dict[str, Any]:
    """
    بررسی اعتبار رشته JSON
    
    :param json_str: رشته JSON
    :return: نتیجه اعتبارسنجی
    """
    try:
        # تلاش برای تحلیل JSON
        json_data = json.loads(json_str)
        
        return {
            'valid': True,
            'data': json_data,
            'type': type(json_data).__name__
        }
    
    except json.JSONDecodeError as e:
        return {
            'valid': False,
            'message': f'رشته JSON نامعتبر است: {str(e)}',
            'error': str(e),
            'line': e.lineno,
            'column': e.colno
        }


def validate_national_id(national_id: str) -> Dict[str, Any]:
    """
    اعتبارسنجی کد ملی ایران
    
    :param national_id: کد ملی
    :return: نتیجه اعتبارسنجی
    """
    # حذف کاراکترهای اضافی
    national_id = re.sub(r'\D', '', national_id)
    
    # بررسی طول
    if len(national_id) != 10:
        return {
            'valid': False,
            'message': 'کد ملی باید 10 رقم باشد'
        }
    
    # بررسی الگو
    if re.match(r'^(\d)\1{9}$', national_id):
        return {
            'valid': False,
            'message': 'کد ملی نمی‌تواند شامل ارقام تکراری باشد'
        }
    
    # بررسی الگوریتم کد ملی
    check = int(national_id[9])
    
    sum_digits = sum(int(national_id[i]) * (10 - i) for i in range(9))
    remainder = sum_digits % 11
    
    if remainder < 2:
        valid_check = remainder
    else:
        valid_check = 11 - remainder
    
    if check != valid_check:
        return {
            'valid': False,
            'message': 'کد ملی نامعتبر است'
        }
    
    return {
        'valid': True,
        'national_id': national_id,
        'formatted': f'{national_id[:3]}-{national_id[3:6]}-{national_id[6:]}'
    }


def validate_sheba(sheba: str, country_code: str = 'IR') -> Dict[str, Any]:
    """
    اعتبارسنجی شماره شبا (IBAN)
    
    :param sheba: شماره شبا
    :param country_code: کد کشور (پیش‌فرض: IR)
    :return: نتیجه اعتبارسنجی
    """
    # حذف کاراکترهای اضافی
    sheba = re.sub(r'\s+', '', sheba.upper())
    
    # افزودن IR در صورت نبودن
    if len(sheba) == 24 and not sheba.startswith('IR'):
        sheba = 'IR' + sheba
    
    # اگر با IR شروع می‌شود ولی طول آن 26 نیست
    if sheba.startswith('IR') and len(sheba) != 26:
        return {
            'valid': False,
            'message': 'طول شماره شبای ایران باید 26 کاراکتر باشد (شامل IR)'
        }
    
    # بررسی الگو
    if not re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]{4}\d{16}$', sheba):
        return {
            'valid': False,
            'message': 'فرمت شماره شبا نامعتبر است'
        }
    
    # بررسی کد کشور
    if not sheba.startswith(country_code):
        return {
            'valid': False,
            'message': f'کد کشور شبا باید {country_code} باشد'
        }
    
    # بررسی الگوریتم شبا
    # 1. انتقال 4 کاراکتر اول به انتها
    rearranged = sheba[4:] + sheba[:4]
    
    # 2. تبدیل حروف به اعداد (A=10, B=11, ..., Z=35)
    numeric = ''
    for char in rearranged:
        if '0' <= char <= '9':
            numeric += char
        else:
            numeric += str(ord(char) - ord('A') + 10)
    
    # 3. بررسی باقیمانده بر 97
    if int(numeric) % 97 != 1:
        return {
            'valid': False,
            'message': 'شماره شبا نامعتبر است (الگوریتم بررسی)'
        }
    
    # شناسایی بانک برای شبای ایران
    bank_name = 'نامشخص'
    if sheba.startswith('IR'):
        bank_code = sheba[4:7]
        ir_banks = {
            '055': 'بانک اقتصاد نوین',
            '054': 'بانک پارسیان',
            '057': 'بانک پاسارگاد',
            '021': 'پست بانک ایران',
            '018': 'بانک تجارت',
            '051': 'موسسه اعتباری توسعه',
            '020': 'بانک توسعه صادرات',
            '013': 'بانک رفاه کارگران',
            '056': 'بانک سامان',
            '015': 'بانک سپه',
            '058': 'بانک سرمایه',
            '019': 'بانک صادرات ایران',
            '011': 'بانک صنعت و معدن',
            '053': 'بانک کارآفرین',
            '016': 'بانک کشاورزی',
            '010': 'بانک مرکزی',
            '014': 'بانک مسکن',
            '012': 'بانک ملت',
            '017': 'بانک ملی ایران'
        }
        
        if bank_code in ir_banks:
            bank_name = ir_banks[bank_code]
     
    return {
        'valid': True,
        'sheba': sheba,
        'country_code': sheba[:2],
        'check_digits': sheba[2:4],
        'bank_code': sheba[4:7] if sheba.startswith('IR') else None,
        'bank_name': bank_name if sheba.startswith('IR') else None,
        'formatted': ' '.join([sheba[i:i+4] for i in range(0, len(sheba), 4)])
    }