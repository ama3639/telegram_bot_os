#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول ابزارهای امنیتی

این ماژول شامل توابع و کلاس‌های مرتبط با امنیت داده‌ها، رمزنگاری، تولید و تایید توکن‌ها، و
سایر عملیات امنیتی است که در سراسر برنامه استفاده می‌شوند.
"""

import os
import re
import hmac
import uuid
import time
import base64
import hashlib
import secrets
import datetime
from typing import Dict, List, Optional, Union, Any, Tuple
import json
import jwt
import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import bleach

from src.core.config import Config
from src.utils.logger import get_logger

# تنظیم لاگر
logger = get_logger(__name__)


class SecurityManager:
    """
    کلاس مدیریت امنیت برای عملیات رمزنگاری و تایید
    """
    def __init__(self, config: Config):
        """
        مقداردهی اولیه
        
        :param config: شیء تنظیمات
        """
        self.config = config
         
        # کلید رمزنگاری Fernet
        self.encryption_key = config.get("ENCRYPTION_KEY", "")
        
        # اگر کلید موجود نباشد، یک کلید جدید تولید می‌کنیم
        if not self.encryption_key:
            self.encryption_key = self._generate_encryption_key()
        
        # آماده‌سازی شیء Fernet برای رمزنگاری متقارن
        self.fernet = Fernet(self.encryption_key.encode() if isinstance(self.encryption_key, str) else self.encryption_key)
        
        # کلید برای JWT
        self.jwt_secret = config.get("JWT_SECRET", "")
        if not self.jwt_secret:
            self.jwt_secret = secrets.token_hex(32)
            
        # کلید HMAC
        self.hmac_key = config.get("HMAC_KEY", "")
        if not self.hmac_key:
            self.hmac_key = secrets.token_hex(32)
            
        # مدت زمان اعتبار توکن (به ثانیه)
        self.token_expiry = int(config.get("TOKEN_EXPIRY", 3600))  # پیش‌فرض: 1 ساعت
        
        logger.info("مدیریت امنیت راه‌اندازی شد")
    
    def _generate_encryption_key(self) -> str:
        """
        تولید کلید رمزنگاری Fernet
        
        :return: کلید رمزنگاری به صورت رشته
        """
        key = Fernet.generate_key()
        return key.decode()
    
    def encrypt_data(self, data: Union[str, bytes, dict]) -> str:
        """
        رمزنگاری داده
        
        :param data: داده برای رمزنگاری (رشته، بایت یا دیکشنری)
        :return: داده رمزنگاری شده به صورت رشته
        """
        try:
            # تبدیل داده به بایت
            if isinstance(data, dict):
                data = json.dumps(data).encode()
            elif isinstance(data, str):
                data = data.encode()
            
            # رمزنگاری
            encrypted_data = self.fernet.encrypt(data)
            
            # تبدیل به رشته base64
            return base64.urlsafe_b64encode(encrypted_data).decode()
        
        except Exception as e:
            logger.error(f"خطا در رمزنگاری داده: {str(e)}")
            raise
    
    def decrypt_data(self, encrypted_data: str, as_dict: bool = False) -> Union[str, dict, bytes]:
        """
        رمزگشایی داده
        
        :param encrypted_data: داده رمزنگاری شده
        :param as_dict: آیا نتیجه به صورت دیکشنری بازگردانده شود
        :return: داده رمزگشایی شده
        """
        try:
            # تبدیل رشته به بایت
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data)
            
            # رمزگشایی
            decrypted_data = self.fernet.decrypt(encrypted_bytes)
            
            # تبدیل به خروجی مناسب
            if as_dict:
                return json.loads(decrypted_data.decode())
            
            return decrypted_data.decode()
        
        except InvalidToken:
            logger.error("توکن رمزنگاری نامعتبر است")
            raise ValueError("داده رمزنگاری شده نامعتبر است")
        
        except json.JSONDecodeError:
            logger.error("داده رمزگشایی شده قابل تبدیل به JSON نیست")
            if as_dict:
                return {}
            return decrypted_data
        
        except Exception as e:
            logger.error(f"خطا در رمزگشایی داده: {str(e)}")
            raise
    
    def hash_password(self, password: str) -> str:
        """
        هش کردن رمز عبور با استفاده از bcrypt
        
        :param password: رمز عبور ساده
        :return: هش رمز عبور
        """
        try:
            # تولید salt و هش کردن رمز عبور
            password_bytes = password.encode()
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password_bytes, salt)
            
            return hashed.decode()
        
        except Exception as e:
            logger.error(f"خطا در هش کردن رمز عبور: {str(e)}")
            raise
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        تایید رمز عبور با مقایسه با هش
        
        :param plain_password: رمز عبور ساده
        :param hashed_password: هش رمز عبور
        :return: نتیجه تایید (درست/نادرست)
        """
        try:
            # تبدیل به بایت
            password_bytes = plain_password.encode()
            hashed_bytes = hashed_password.encode()
            
            # بررسی تطابق
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        
        except Exception as e:
            logger.error(f"خطا در تایید رمز عبور: {str(e)}")
            return False
    
    def generate_token(
        self, 
        user_id: int, 
        expiry_seconds: Optional[int] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        تولید توکن JWT
        
        :param user_id: شناسه کاربر
        :param expiry_seconds: زمان انقضا به ثانیه (اختیاری)
        :param additional_data: داده‌های اضافی برای ذخیره در توکن (اختیاری)
        :return: توکن JWT
        """
        try:
            # زمان انقضا
            if expiry_seconds is None:
                expiry_seconds = self.token_expiry
                
            expiry = datetime.datetime.utcnow() + datetime.timedelta(seconds=expiry_seconds)
            
            # داده‌های پایه
            payload = {
                'sub': str(user_id),
                'exp': expiry,
                'iat': datetime.datetime.utcnow(),
                'jti': str(uuid.uuid4())
            }
            
            # افزودن داده‌های اضافی
            if additional_data:
                for key, value in additional_data.items():
                    if key not in payload:
                        payload[key] = value
            
            # تولید توکن
            return jwt.encode(payload, self.jwt_secret, algorithm='HS256')
        
        except Exception as e:
            logger.error(f"خطا در تولید توکن: {str(e)}")
            raise
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        بررسی اعتبار و رمزگشایی توکن JWT
        
        :param token: توکن JWT
        :return: محتوای توکن یا خطا
        """
        try:
            # رمزگشایی و بررسی توکن
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            
            return {
                'valid': True,
                'user_id': int(payload['sub']),
                'data': payload
            }
        
        except jwt.ExpiredSignatureError:
            logger.warning("توکن منقضی شده است")
            return {
                'valid': False,
                'error': 'token_expired',
                'message': 'توکن منقضی شده است'
            }
        
        except jwt.InvalidTokenError as e:
            logger.warning(f"توکن نامعتبر است: {str(e)}")
            return {
                'valid': False,
                'error': 'invalid_token',
                'message': 'توکن نامعتبر است'
            }
        
        except Exception as e:
            logger.error(f"خطا در بررسی توکن: {str(e)}")
            return {
                'valid': False,
                'error': 'token_error',
                'message': str(e)
            }
    
    def generate_hmac(self, data: Union[str, bytes, dict], key: Optional[str] = None) -> str:
        """
        تولید HMAC برای تایید یکپارچگی داده
        
        :param data: داده برای تولید HMAC
        :param key: کلید HMAC (اختیاری، در صورت عدم ارائه از کلید پیش‌فرض استفاده می‌شود)
        :return: HMAC به صورت رشته هگزادسیمال
        """
        try:
            # استفاده از کلید ارائه شده یا کلید پیش‌فرض
            hmac_key = key.encode() if key else self.hmac_key.encode()
            
            # تبدیل داده به بایت
            if isinstance(data, dict):
                data = json.dumps(data, sort_keys=True).encode()
            elif isinstance(data, str):
                data = data.encode()
            
            # تولید HMAC
            signature = hmac.new(hmac_key, data, hashlib.sha256).hexdigest()
            
            return signature
        
        except Exception as e:
            logger.error(f"خطا در تولید HMAC: {str(e)}")
            raise
    
    def verify_hmac(
        self, 
        data: Union[str, bytes, dict],
        signature: str,
        key: Optional[str] = None
    ) -> bool:
        """
        تایید HMAC برای بررسی یکپارچگی داده
        
        :param data: داده اصلی
        :param signature: امضای HMAC
        :param key: کلید HMAC (اختیاری، در صورت عدم ارائه از کلید پیش‌فرض استفاده می‌شود)
        :return: نتیجه تایید (درست/نادرست)
        """
        try:
            # تولید HMAC جدید
            calculated_signature = self.generate_hmac(data, key)
            
            # مقایسه با امضای ارائه شده
            return hmac.compare_digest(calculated_signature, signature)
        
        except Exception as e:
            logger.error(f"خطا در تایید HMAC: {str(e)}")
            return False


# نمونه منفرد از مدیریت امنیت
_security_manager = None


def get_security_manager(config: Optional[Config] = None) -> SecurityManager:
    """
    دریافت نمونه منفرد از مدیریت امنیت
    
    :param config: شیء تنظیمات (اختیاری)
    :return: نمونه SecurityManager
    """
    global _security_manager
    
    if _security_manager is None:
        if config is None:
            from core.config import Config
            config = Config()
            
        _security_manager = SecurityManager(config)
        
    return _security_manager


# توابع کمکی
def encrypt_data(data: Union[str, bytes, dict], config: Optional[Config] = None) -> str:
    """
    رمزنگاری داده
    
    :param data: داده برای رمزنگاری
    :param config: شیء تنظیمات (اختیاری)
    :return: داده رمزنگاری شده
    """
    return get_security_manager(config).encrypt_data(data)


def decrypt_data(encrypted_data: str, as_dict: bool = False, config: Optional[Config] = None) -> Union[str, dict, bytes]:
    """
    رمزگشایی داده
    
    :param encrypted_data: داده رمزنگاری شده
    :param as_dict: آیا نتیجه به صورت دیکشنری بازگردانده شود
    :param config: شیء تنظیمات (اختیاری)
    :return: داده رمزگشایی شده
    """
    return get_security_manager(config).decrypt_data(encrypted_data, as_dict)


# توابع اضافه شده برای پشتیبانی از رابط encrypt_sensitive_data و decrypt_sensitive_data
def encrypt_sensitive_data(data: Union[str, bytes, dict], config: Optional[Config] = None) -> str:
    """
    رمزنگاری داده‌های حساس
    
    :param data: داده حساس برای رمزنگاری
    :param config: شیء تنظیمات (اختیاری)
    :return: داده رمزنگاری شده
    """
    return encrypt_data(data, config)


def decrypt_sensitive_data(encrypted_data: str, as_dict: bool = False, config: Optional[Config] = None) -> Union[str, dict, bytes]:
    """
    رمزگشایی داده‌های حساس
    
    :param encrypted_data: داده رمزنگاری شده
    :param as_dict: آیا نتیجه به صورت دیکشنری بازگردانده شود
    :param config: شیء تنظیمات (اختیاری)
    :return: داده رمزگشایی شده
    """
    return decrypt_data(encrypted_data, as_dict, config)


def hash_password(password: str, config: Optional[Config] = None) -> str:
    """
    هش کردن رمز عبور
    
    :param password: رمز عبور ساده
    :param config: شیء تنظیمات (اختیاری)
    :return: هش رمز عبور
    """
    return get_security_manager(config).hash_password(password)


def verify_password(plain_password: str, hashed_password: str, config: Optional[Config] = None) -> bool:
    """
    تایید رمز عبور
    
    :param plain_password: رمز عبور ساده
    :param hashed_password: هش رمز عبور
    :param config: شیء تنظیمات (اختیاری)
    :return: نتیجه تایید
    """
    return get_security_manager(config).verify_password(plain_password, hashed_password)


def generate_token(
    user_id: int,
    expiry_seconds: Optional[int] = None,
    additional_data: Optional[Dict[str, Any]] = None,
    config: Optional[Config] = None
) -> str:
    """
    تولید توکن JWT
    
    :param user_id: شناسه کاربر
    :param expiry_seconds: زمان انقضا به ثانیه (اختیاری)
    :param additional_data: داده‌های اضافی برای ذخیره در توکن (اختیاری)
    :param config: شیء تنظیمات (اختیاری)
    :return: توکن JWT
    """
    return get_security_manager(config).generate_token(user_id, expiry_seconds, additional_data)


def verify_token(token: str, config: Optional[Config] = None) -> Dict[str, Any]:
    """
    بررسی اعتبار و رمزگشایی توکن JWT
    
    :param token: توکن JWT
    :param config: شیء تنظیمات (اختیاری)
    :return: محتوای توکن یا خطا
    """
    return get_security_manager(config).verify_token(token)


def generate_hmac(data: Union[str, bytes, dict], key: Optional[str] = None, config: Optional[Config] = None) -> str:
    """
    تولید HMAC برای تایید یکپارچگی داده
    
    :param data: داده برای تولید HMAC
    :param key: کلید HMAC (اختیاری)
    :param config: شیء تنظیمات (اختیاری)
    :return: HMAC به صورت رشته هگزادسیمال
    """
    return get_security_manager(config).generate_hmac(data, key)


def verify_hmac(
    data: Union[str, bytes, dict],
    signature: str,
    key: Optional[str] = None,
    config: Optional[Config] = None
) -> bool:
    """
    تایید HMAC برای بررسی یکپارچگی داده
    
    :param data: داده اصلی
    :param signature: امضای HMAC
    :param key: کلید HMAC (اختیاری)
    :param config: شیء تنظیمات (اختیاری)
    :return: نتیجه تایید
    """
    return get_security_manager(config).verify_hmac(data, signature, key)


def sanitize_input(input_str: str, allow_html: bool = False) -> str:
    """
    پاکسازی ورودی کاربر برای جلوگیری از حملات XSS
    
    :param input_str: رشته ورودی
    :param allow_html: آیا تگ‌های HTML مجاز هستند
    :return: رشته پاکسازی شده
    """
    if not input_str:
        return ""
    
    if allow_html:
        # تگ‌های مجاز و ویژگی‌های آنها
        allowed_tags = [
            'a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
            'em', 'i', 'li', 'ol', 'strong', 'ul', 'p', 'br',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'span'
        ]
        
        allowed_attrs = {
            'a': ['href', 'title', 'target'],
            'abbr': ['title'],
            'acronym': ['title'],
            'span': ['style', 'class']
        }
        
        # پاکسازی HTML
        return bleach.clean(
            input_str,
            tags=allowed_tags,
            attributes=allowed_attrs,
            strip=True
        )
    else:
        # حذف همه تگ‌های HTML
        return bleach.clean(input_str, tags=[], strip=True)


def generate_secure_filename(filename: str) -> str:
    """
    تولید نام فایل امن برای جلوگیری از آسیب‌پذیری‌های مرتبط با فایل
    
    :param filename: نام فایل اصلی
    :return: نام فایل امن
    """
    # حذف کاراکترهای خطرناک
    filename = re.sub(r'[^\w\.-]', '_', filename)
    
    # افزودن یک مقدار تصادفی برای جلوگیری از تداخل
    random_suffix = secrets.token_hex(4)
    
    # جدا کردن نام و پسوند فایل
    name, ext = os.path.splitext(filename)
    
    # ترکیب با مقدار تصادفی
    secure_name = f"{name}_{random_suffix}{ext}"
    
    return secure_name


def generate_random_password(length: int = 12) -> str:
    """
    تولید رمز عبور تصادفی با ترکیب مناسبی از کاراکترها
    
    :param length: طول رمز عبور
    :return: رمز عبور تصادفی
    """
    if length < 8:
        length = 8  # حداقل طول برای امنیت
    
    # مجموعه کاراکترها
    lowercase = 'abcdefghijklmnopqrstuvwxyz'
    uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    digits = '0123456789'
    special = '!@#$%^&*()-_=+[]{}|;:,.<>?'
    
    # انتخاب حداقل یک کاراکتر از هر مجموعه
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    
    # تکمیل باقی رمز عبور
    all_chars = lowercase + uppercase + digits + special
    password.extend(secrets.choice(all_chars) for _ in range(length - 4))
    
    # مخلوط کردن کاراکترها
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)


def check_password_strength(password: str) -> Dict[str, Any]:
    """
    بررسی قدرت رمز عبور
    
    :param password: رمز عبور
    :return: نتیجه بررسی
    """
    # بررسی طول
    length_ok = len(password) >= 8
    
    # بررسی وجود حروف کوچک
    has_lower = bool(re.search(r'[a-z]', password))
    
    # بررسی وجود حروف بزرگ
    has_upper = bool(re.search(r'[A-Z]', password))
    
    # بررسی وجود اعداد
    has_digit = bool(re.search(r'\d', password))
    
    # بررسی وجود کاراکترهای ویژه
    has_special = bool(re.search(r'[!@#$%^&*()_\-+={\[\]}\|:;"\'<>,.?/]', password))
    
    # محاسبه امتیاز (از 5)
    score = sum([length_ok, has_lower, has_upper, has_digit, has_special])
    
    # تعیین سطح قدرت
    strength_levels = {
        0: 'بسیار ضعیف',
        1: 'ضعیف',
        2: 'متوسط',
        3: 'خوب',
        4: 'قوی',
        5: 'بسیار قوی'
    }
    
    strength = strength_levels[score]
    
    # پیشنهادات بهبود
    suggestions = []
    if not length_ok:
        suggestions.append('رمز عبور باید حداقل 8 کاراکتر باشد.')
    if not has_lower:
        suggestions.append('از حروف کوچک استفاده کنید.')
    if not has_upper:
        suggestions.append('از حروف بزرگ استفاده کنید.')
    if not has_digit:
        suggestions.append('از اعداد استفاده کنید.')
    if not has_special:
        suggestions.append('از کاراکترهای ویژه (!@#$% و غیره) استفاده کنید.')
    
    return {
        'score': score,
        'max_score': 5,
        'strength': strength,
        'is_strong': score >= 4,
        'suggestions': suggestions,
        'checks': {
            'length': length_ok,
            'lowercase': has_lower,
            'uppercase': has_upper,
            'digits': has_digit,
            'special': has_special
        }
    }


def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """
    مشتق کردن کلید رمزنگاری از رمز عبور
    
    :param password: رمز عبور
    :param salt: نمک (اختیاری، در صورت عدم ارائه تولید می‌شود)
    :return: تاپل (کلید، نمک)
    """
    if salt is None:
        salt = os.urandom(16)
    
    # تبدیل رمز عبور به بایت
    password_bytes = password.encode()
    
    # تنظیم PBKDF2
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000
    )
    
    # مشتق کردن کلید
    key = kdf.derive(password_bytes)
    
    return key, salt