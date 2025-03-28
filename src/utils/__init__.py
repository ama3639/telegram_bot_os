#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول توابع کمکی (utils)

این ماژول شامل مجموعه‌ای از توابع و کلاس‌های کمکی است که در سرتاسر پروژه مورد استفاده قرار می‌گیرند.
"""

# وارد کردن صحیح از مسیر داخلی
from src.utils.timezone_utils import get_current_datetime

# نمایش تغییر مسیر واردسازی از قبلی به جدید
from src.utils.accounting import (
    format_currency, calculate_fee, verify_payment_amount,
    prepare_invoice, calculate_discount
)

# استفاده از واردسازی با مسیر مطلق
from src.utils.cache import (
    Cache, CacheExpiry, MemoryCache, DiskCache
)

from src.utils.chart_generator import (
    generate_line_chart, generate_bar_chart, generate_pie_chart,
    generate_candlestick_chart, save_chart_to_file, generate_stacked_bar_chart
)

from src.utils.crypto_payment import (
    generate_wallet_address, verify_crypto_transaction,
    get_crypto_payment_status, get_current_exchange_rate
)

from src.utils.localization import (
    get_message, set_language, get_available_languages,
    format_number, translate_error
)
 
from src.utils.logger import (
    get_logger, setup_logger, log_exception,
    enable_debug_logging, disable_debug_logging
)

from src.utils.notification import (
    send_telegram_notification, send_email_notification,
    register_for_notifications, unregister_from_notifications
)

from src.utils.security import (
    encrypt_data, decrypt_data, hash_password,
    verify_password, generate_token, verify_token,
    sanitize_input, generate_hmac
)

from src.utils.validators import (
    validate_email, validate_phone, validate_username,
    validate_password, validate_amount, validate_wallet_address,
    sanitize_string, is_valid_json 
)

from src.utils.timezone_utils import (
    get_current_datetime, convert_timezone, format_datetime,
    parse_datetime_string, get_timezone_difference,
    get_user_timezone, is_same_day
)

__all__ = [
    # accounting.py
    'format_currency', 'calculate_fee', 'verify_payment_amount',
    'prepare_invoice', 'calculate_discount',
    
    # cache.py
    'Cache', 'CacheExpiry', 'MemoryCache', 'DiskCache',
    
    # chart_generator.py
    'generate_line_chart', 'generate_bar_chart', 'generate_pie_chart',
    'generate_candlestick_chart', 'save_chart_to_file', 'generate_stacked_bar_chart',
    
    # crypto_payment.py
    'generate_wallet_address', 'verify_crypto_transaction',
    'get_crypto_payment_status', 'get_current_exchange_rate',
    
    # localization.py
    'get_message', 'set_language', 'get_available_languages',
    'format_number', 'translate_error',
    
    # logger.py
    'get_logger', 'setup_logger', 'log_exception',
    'enable_debug_logging', 'disable_debug_logging',
    
    # notification.py
    'send_telegram_notification', 'send_email_notification',
    'register_for_notifications', 'unregister_from_notifications',
    
    # security.py
    'encrypt_data', 'decrypt_data', 'hash_password',
    'verify_password', 'generate_token', 'verify_token',
    'sanitize_input', 'generate_hmac',
    
    # validators.py
    'validate_email', 'validate_phone', 'validate_username',
    'validate_password', 'validate_amount', 'validate_wallet_address',
    'sanitize_string', 'is_valid_json',
    
    # timezone_utils.py
    'get_current_datetime', 'convert_timezone', 'format_datetime',
    'parse_datetime_string', 'get_timezone_difference',
    'get_user_timezone', 'is_same_day'
]