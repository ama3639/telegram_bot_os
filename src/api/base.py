#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
کلاس پایه برای ارتباط با API‌ها.

این ماژول شامل کلاس پایه برای ارتباط با API‌های مختلف است و امکانات مشترک
مانند مدیریت خطاها، کش‌گذاری و مدیریت نشست را فراهم می‌کند.

تاریخ ایجاد: ۱۴۰۴/۰۱/۰۷
"""


from typing import AsyncGenerator
import logging
import json
import time
import asyncio
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
import hashlib
import aiohttp
from aiohttp import ClientSession, ClientResponse, ClientError

from utils.cache import Cache
from utils.security import encrypt_data, decrypt_data

logger = logging.getLogger(__name__)

class APIError(Exception): 
    """
    کلاس خطای API برای خطاهای رخ داده در ارتباط با API‌ها.
    """
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                response_data: Optional[Dict[str, Any]] = None):
        """
        مقداردهی اولیه خطای API.
        
        پارامترها:
            message: پیام خطا
            status_code: کد وضعیت HTTP (اختیاری)
            response_data: داده‌های پاسخ (اختیاری)
        """
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        
        super().__init__(self.message)
    
    def __str__(self) -> str:
        """
        تبدیل به رشته برای نمایش.
        
        بازگشت:
            str: نمایش رشته‌ای خطا
        """
        result = f"APIError: {self.message}"
        
        if self.status_code:
            result += f" (Status: {self.status_code})"
        
        if self.response_data:
            result += f"\nResponse: {json.dumps(self.response_data, ensure_ascii=False, indent=2)}"
        
        return result

class RateLimitExceededError(APIError):
    """
    خطای محدودیت نرخ درخواست.
    """
    
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        """
        مقداردهی اولیه خطای محدودیت نرخ.
        
        پارامترها:
            message: پیام خطا
            retry_after: زمان توصیه شده برای تلاش مجدد (ثانیه)
            **kwargs: سایر پارامترها برای کلاس پایه
        """
        self.retry_after = retry_after
        super().__init__(message, **kwargs)
    
    def __str__(self) -> str:
        """
        تبدیل به رشته برای نمایش.
        
        بازگشت:
            str: نمایش رشته‌ای خطا
        """
        result = super().__str__()
        
        if self.retry_after:
            result += f"\nRetry after: {self.retry_after} seconds"
        
        return result

class AuthenticationError(APIError):
    """
    خطای احراز هویت.
    """
    pass

class BaseAPI:
    """
    کلاس پایه برای ارتباط با API‌ها.
    این کلاس امکانات مشترک برای تمام API‌ها را فراهم می‌کند.
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, 
                timeout: int = 30, cache: Optional[Cache] = None,
                cache_ttl: int = 300):
        """
        مقداردهی اولیه کلاس API.
        
        پارامترها:
            base_url: آدرس پایه API
            api_key: کلید API (اختیاری)
            timeout: حداکثر زمان انتظار برای درخواست (ثانیه)
            cache: شیء کش برای ذخیره پاسخ‌ها (اختیاری)
            cache_ttl: زمان نگهداری کش (ثانیه)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.cache = cache or Cache()
        self.cache_ttl = cache_ttl
        self.session: Optional[ClientSession] = None
        self.retry_count = 3  # تعداد تلاش‌های مجدد در صورت خطا
        self.retry_delay = 1  # تأخیر اولیه بین تلاش‌ها (ثانیه)
        
        # تنظیم هدرهای پیش‌فرض
        self.default_headers = {
            'Accept': 'application/json',
            'User-Agent': 'TelegramBot/1.0'
        }
        
        if api_key:
            self.default_headers['Authorization'] = f"Bearer {api_key}"
        
        logger.debug(f"کلاس API برای {base_url} ایجاد شد.")
    
    async def __aenter__(self):
        """
        ورود به بلوک async with.
        """
        await self.create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        خروج از بلوک async with.
        """
        await self.close_session()
    
    async def create_session(self) -> None:
        """
        ایجاد نشست HTTP.
        """
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers=self.default_headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
            logger.debug("نشست HTTP جدید ایجاد شد.")
    
    async def close_session(self) -> None:
        """
        بستن نشست HTTP.
        """
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("نشست HTTP بسته شد.")
    
    def _get_cache_key(self, method: str, url: str, params: Optional[Dict[str, Any]] = None, 
                     data: Optional[Dict[str, Any]] = None) -> str:
        """
        ایجاد کلید کش برای یک درخواست.
        
        پارامترها:
            method: روش HTTP (GET, POST, ...)
            url: آدرس درخواست
            params: پارامترهای کوئری (اختیاری)
            data: داده‌های ارسالی (اختیاری)
            
        بازگشت:
            str: کلید کش
        """
        # ساخت رشته یکتا از پارامترهای درخواست
        key_parts = [method.upper(), url]
        
        if params:
            # مرتب‌سازی پارامترها برای ایجاد کلید ثابت
            key_parts.append(json.dumps(params, sort_keys=True))
        
        if data:
            # مرتب‌سازی داده‌ها برای ایجاد کلید ثابت
            key_parts.append(json.dumps(data, sort_keys=True))
        
        # ایجاد هش SHA-256 از رشته یکتا
        key_string = "||".join(key_parts)
        cache_key = hashlib.sha256(key_string.encode()).hexdigest()
        
        return f"api:{cache_key}"
    
    async def _make_request(self, method: str, endpoint: str, 
                          params: Optional[Dict[str, Any]] = None,
                          data: Optional[Dict[str, Any]] = None,
                          headers: Optional[Dict[str, str]] = None,
                          use_cache: bool = True,
                          cache_ttl: Optional[int] = None) -> Dict[str, Any]:
        """
        انجام درخواست HTTP به API.
        
        پارامترها:
            method: روش HTTP (GET, POST, ...)
            endpoint: مسیر انتهایی API
            params: پارامترهای کوئری (اختیاری)
            data: داده‌های ارسالی (اختیاری)
            headers: هدرهای سفارشی (اختیاری)
            use_cache: آیا از کش استفاده شود؟
            cache_ttl: زمان نگهداری کش (اختیاری)
            
        بازگشت:
            Dict[str, Any]: پاسخ API
            
        استثناها:
            APIError: در صورت خطا در API
            RateLimitExceededError: در صورت فراتر رفتن از محدودیت نرخ
            AuthenticationError: در صورت خطای احراز هویت
        """
        # اطمینان از وجود نشست
        await self.create_session()
        
        # ساخت URL کامل
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # ترکیب هدرهای پیش‌فرض و سفارشی
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)
        
        # بررسی کش
        cache_key = None
        if use_cache and method.upper() == 'GET':
            cache_key = self._get_cache_key(method, url, params, data)
            cached_data = self.cache.get(cache_key)
            
            if cached_data:
                logger.debug(f"داده‌های کش شده برای {url} یافت شد.")
                return cached_data
        
        # آماده‌سازی داده‌ها
        json_data = None
        if data:
            json_data = data
        
        # استراتژی تلاش مجدد با تأخیر نمایی
        retry_delay = self.retry_delay
        
        for attempt in range(self.retry_count + 1):
            try:
                logger.debug(f"ارسال درخواست {method} به {url} (تلاش {attempt + 1}/{self.retry_count + 1})")
                
                async with getattr(self.session, method.lower())(
                    url,
                    params=params,
                    json=json_data,
                    headers=request_headers
                ) as response:
                    # خواندن پاسخ
                    try:
                        response_data = await response.json()
                    except:
                        # اگر پاسخ JSON نیست
                        response_text = await response.text()
                        try:
                            # تلاش برای تبدیل متن به JSON
                            response_data = json.loads(response_text)
                        except:
                            # اگر تبدیل به JSON ممکن نیست
                            response_data = {"text": response_text}
                    
                    # بررسی کد وضعیت
                    if response.status >= 200 and response.status < 300:
                        # موفقیت
                        if cache_key and use_cache and method.upper() == 'GET':
                            # ذخیره در کش
                            self.cache.set(cache_key, response_data, ttl=cache_ttl or self.cache_ttl)
                            logger.debug(f"پاسخ برای {url} در کش ذخیره شد.")
                        
                        return response_data
                    
                    elif response.status == 401 or response.status == 403:
                        # خطای احراز هویت
                        raise AuthenticationError(
                            f"خطای احراز هویت: {response_data.get('message', 'خطای نامشخص')}",
                            status_code=response.status,
                            response_data=response_data
                        )
                    
                    elif response.status == 429:
                        # محدودیت نرخ
                        retry_after = response.headers.get('Retry-After')
                        if retry_after:
                            try:
                                retry_after = int(retry_after)
                            except ValueError:
                                retry_after = 60  # مقدار پیش‌فرض
                        else:
                            retry_after = 60  # مقدار پیش‌فرض
                        
                        raise RateLimitExceededError(
                            "محدودیت نرخ درخواست فراتر رفته است.",
                            retry_after=retry_after,
                            status_code=response.status,
                            response_data=response_data
                        )
                    
                    else:
                        # سایر خطاها
                        error_message = response_data.get('message', 'خطای نامشخص')
                        raise APIError(
                            f"خطای {response.status}: {error_message}",
                            status_code=response.status,
                            response_data=response_data
                        )
            
            except (RateLimitExceededError, AuthenticationError) as e:
                # خطاهایی که نیاز به برخورد خاص دارند
                raise
            
            except (ClientError, asyncio.TimeoutError) as e:
                # خطاهای شبکه یا زمان انتظار
                if attempt < self.retry_count:
                    # تأخیر قبل از تلاش مجدد
                    await asyncio.sleep(retry_delay)
                    
                    # افزایش تأخیر برای تلاش بعدی (تأخیر نمایی)
                    retry_delay *= 2
                    
                    logger.warning(f"خطا در درخواست به {url}: {str(e)}. تلاش مجدد در {retry_delay} ثانیه...")
                    continue
                
                # آخرین تلاش ناموفق بود
                raise APIError(f"خطا در ارتباط با API: {str(e)}")
            
            except Exception as e:
                # سایر خطاها
                if attempt < self.retry_count:
                    # تأخیر قبل از تلاش مجدد
                    await asyncio.sleep(retry_delay)
                    
                    # افزایش تأخیر برای تلاش بعدی (تأخیر نمایی)
                    retry_delay *= 2
                    
                    logger.warning(f"خطای نامشخص در درخواست به {url}: {str(e)}. تلاش مجدد در {retry_delay} ثانیه...")
                    continue
                
                # آخرین تلاش ناموفق بود
                raise APIError(f"خطای نامشخص: {str(e)}")
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None,
                headers: Optional[Dict[str, str]] = None,
                use_cache: bool = True,
                cache_ttl: Optional[int] = None) -> Dict[str, Any]:
        """
        انجام درخواست GET.
        
        پارامترها:
            endpoint: مسیر انتهایی API
            params: پارامترهای کوئری (اختیاری)
            headers: هدرهای سفارشی (اختیاری)
            use_cache: آیا از کش استفاده شود؟
            cache_ttl: زمان نگهداری کش (اختیاری)
            
        بازگشت:
            Dict[str, Any]: پاسخ API
        """
        return await self._make_request(
            'GET', endpoint, params=params, headers=headers, 
            use_cache=use_cache, cache_ttl=cache_ttl
        )
    
    async def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None,
                 params: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None,
                 use_cache: bool = False) -> Dict[str, Any]:
        """
        انجام درخواست POST.
        
        پارامترها:
            endpoint: مسیر انتهایی API
            data: داده‌های ارسالی (اختیاری)
            params: پارامترهای کوئری (اختیاری)
            headers: هدرهای سفارشی (اختیاری)
            use_cache: آیا از کش استفاده شود؟
            
        بازگشت:
            Dict[str, Any]: پاسخ API
        """
        return await self._make_request(
            'POST', endpoint, params=params, data=data, headers=headers, 
            use_cache=use_cache
        )
    
    async def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None,
               params: Optional[Dict[str, Any]] = None,
               headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        انجام درخواست PUT.
        
        پارامترها:
            endpoint: مسیر انتهایی API
            data: داده‌های ارسالی (اختیاری)
            params: پارامترهای کوئری (اختیاری)
            headers: هدرهای سفارشی (اختیاری)
            
        بازگشت:
            Dict[str, Any]: پاسخ API
        """
        return await self._make_request(
            'PUT', endpoint, params=params, data=data, headers=headers, 
            use_cache=False
        )
    
    async def delete(self, endpoint: str, params: Optional[Dict[str, Any]] = None,
                  headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        انجام درخواست DELETE.
        
        پارامترها:
            endpoint: مسیر انتهایی API
            params: پارامترهای کوئری (اختیاری)
            headers: هدرهای سفارشی (اختیاری)
            
        بازگشت:
            Dict[str, Any]: پاسخ API
        """
        return await self._make_request(
            'DELETE', endpoint, params=params, headers=headers, 
            use_cache=False
        )
    
    def clear_cache(self, endpoint: Optional[str] = None, 
                  params: Optional[Dict[str, Any]] = None) -> None:
        """
        پاکسازی کش مربوط به یک API خاص.
        
        پارامترها:
            endpoint: مسیر انتهایی API (اختیاری، برای پاکسازی کل کش None وارد کنید)
            params: پارامترهای کوئری (اختیاری)
        """
        if endpoint:
            # ساخت کلید کش
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            cache_key = self._get_cache_key('GET', url, params)
            
            # حذف از کش
            self.cache.delete(cache_key)
            logger.debug(f"کش برای {url} پاکسازی شد.")
        else:
            # پاکسازی تمام کش
            # توجه: این کار همه کش‌ها را پاک می‌کند، نه فقط کش‌های مربوط به این API
            self.cache.clear()
            logger.debug("تمام کش‌ها پاکسازی شدند.")
    
    @staticmethod
    def handle_error(func: Callable) -> Callable:
        """
        دکوراتور برای مدیریت خطاهای API.
        
        پارامترها:
            func: تابعی که باید خطاهای آن مدیریت شود
            
        بازگشت:
            Callable: تابع wrapper
        """
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except AuthenticationError as e:
                logger.error(f"خطای احراز هویت: {str(e)}")
                # اینجا می‌توانید کد مربوط به تلاش مجدد برای احراز هویت را قرار دهید
                raise
            except RateLimitExceededError as e:
                logger.warning(f"محدودیت نرخ درخواست: {str(e)}")
                # اینجا می‌توانید کد مربوط به تأخیر و تلاش مجدد را قرار دهید
                if e.retry_after:
                    logger.info(f"انتظار به مدت {e.retry_after} ثانیه...")
                    await asyncio.sleep(e.retry_after)
                    # تلاش مجدد
                    return await func(*args, **kwargs)
                raise
            except APIError as e:
                logger.error(f"خطای API: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"خطای نامشخص: {str(e)}")
                raise APIError(f"خطای نامشخص: {str(e)}")
        
        return wrapper

    async def upload_file(self, endpoint: str, file_path: str, 
                         field_name: str = 'file',
                         params: Optional[Dict[str, Any]] = None,
                         headers: Optional[Dict[str, str]] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        آپلود فایل به API.
        
        پارامترها:
            endpoint: مسیر انتهایی API
            file_path: مسیر فایل برای آپلود
            field_name: نام فیلد فایل در فرم
            params: پارامترهای کوئری (اختیاری)
            headers: هدرهای سفارشی (اختیاری)
            metadata: اطلاعات اضافی برای ارسال همراه با فایل (اختیاری)
            
        بازگشت:
            Dict[str, Any]: پاسخ API
            
        استثناها:
            APIError: در صورت خطا در API
            FileNotFoundError: اگر فایل یافت نشود
        """
        import os
        from aiohttp import FormData
        
        # بررسی وجود فایل
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"فایل مورد نظر یافت نشد: {file_path}")
        
        # اطمینان از وجود نشست
        await self.create_session()
        
        # ساخت URL کامل
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # ترکیب هدرهای پیش‌فرض و سفارشی
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)
        
        # حذف هدر Content-Type اگر وجود دارد (اجازه دهید aiohttp آن را تنظیم کند)
        if 'Content-Type' in request_headers:
            del request_headers['Content-Type']
        
        # ساخت فرم چندبخشی
        form = FormData()
        
        # افزودن فایل به فرم
        with open(file_path, 'r') as f:
            filename = os.path.basename(file_path)
            form.add_field(field_name, f, filename=filename)
        
        # Ø§ÙØ²ÙØ¯Ù ÙØªØ§Ø¯ÛØªØ§ Ø¨Ù ÙØ±Ù
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (dict, list)):
                    form.add_field(key, json.dumps(value), content_type='application/json')
                else:
                    form.add_field(key, str(value))
        
        # استراتژی تلاش مجدد با تأخیر نمایی
        retry_delay = self.retry_delay
        
        for attempt in range(self.retry_count + 1):
            try:
                logger.debug(f"آپلود فایل به {url} (تلاش {attempt + 1}/{self.retry_count + 1})")
                
                async with self.session.post(
                    url,
                    params=params,
                    data=form,
                    headers=request_headers
                ) as response:
                    # خواندن پاسخ
                    try:
                        response_data = await response.json()
                    except:
                        # اگر پاسخ JSON نیست
                        response_text = await response.text()
                        try:
                            # تلاش برای تبدیل متن به JSON
                            response_data = json.loads(response_text)
                        except:
                            # اگر تبدیل به JSON ممکن نیست
                            response_data = {"text": response_text}
                    
                    # بررسی کد وضعیت
                    if response.status >= 200 and response.status < 300:
                        # موفقیت
                        return response_data
                    
                    # مدیریت خطاها (مشابه _make_request)
                    elif response.status == 401 or response.status == 403:
                        # خطای احراز هویت
                        raise AuthenticationError(
                            f"خطای احراز هویت: {response_data.get('message', 'خطای نامشخص')}",
                            status_code=response.status,
                            response_data=response_data
                        )
                    
                    elif response.status == 429:
                        # محدودیت نرخ
                        retry_after = response.headers.get('Retry-After')
                        if retry_after:
                            try:
                                retry_after = int(retry_after)
                            except ValueError:
                                retry_after = 60
                        else:
                            retry_after = 60
                        
                        raise RateLimitExceededError(
                            "محدودیت نرخ درخواست فراتر رفته است.",
                            retry_after=retry_after,
                            status_code=response.status,
                            response_data=response_data
                        )
                    
                    else:
                        # سایر خطاها
                        error_message = response_data.get('message', 'خطای نامشخص')
                        raise APIError(
                            f"خطای {response.status}: {error_message}",
                            status_code=response.status,
                            response_data=response_data
                        )
            
            except (RateLimitExceededError, AuthenticationError) as e:
                # خطاهایی که نیاز به برخورد خاص دارند
                raise
            
            except Exception as e:
                # سایر خطاها
                if attempt < self.retry_count:
                    # تأخیر قبل از تلاش مجدد
                    await asyncio.sleep(retry_delay)
                    
                    # افزایش تأخیر برای تلاش بعدی (تأخیر نمایی)
                    retry_delay *= 2
                    
                    logger.warning(f"خطا در آپلود فایل به {url}: {str(e)}. تلاش مجدد در {retry_delay} ثانیه...")
                    continue
                
                # آخرین تلاش ناموفق بود
                raise APIError(f"خطا در آپلود فایل: {str(e)}")
    
    async def download_file(self, endpoint: str, save_path: str,
                          params: Optional[Dict[str, Any]] = None,
                          headers: Optional[Dict[str, str]] = None) -> str:
        """
        دانلود فایل از API.
        
        پارامترها:
            endpoint: مسیر انتهایی API
            save_path: مسیر ذخیره فایل
            params: پارامترهای کوئری (اختیاری)
            headers: هدرهای سفارشی (اختیاری)
            
        بازگشت:
            str: مسیر کامل فایل ذخیره شده
            
        استثناها:
            APIError: در صورت خطا در API
        """
        import os
        
        # اطمینان از وجود نشست
        await self.create_session()
        
        # ساخت URL کامل
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # ترکیب هدرهای پیش‌فرض و سفارشی
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)
        
        # اطمینان از وجود دایرکتوری مقصد
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        
        # استراتژی تلاش مجدد با تأخیر نمایی
        retry_delay = self.retry_delay
        
        for attempt in range(self.retry_count + 1):
            try:
                logger.debug(f"دانلود فایل از {url} (تلاش {attempt + 1}/{self.retry_count + 1})")
                
                async with self.session.get(
                    url,
                    params=params,
                    headers=request_headers
                ) as response:
                    # بررسی کد وضعیت
                    if response.status >= 200 and response.status < 300:
                        # دریافت نام فایل از هدر Content-Disposition
                        filename = None
                        if 'Content-Disposition' in response.headers:
                            content_disposition = response.headers['Content-Disposition']
                            import re
                            filename_match = re.search(r'filename="?([^";]+)"?', content_disposition)
                            if filename_match:
                                filename = filename_match.group(1)
                        
                        # اگر مسیر ذخیره یک دایرکتوری است، از نام فایل دریافتی استفاده شود
                        if os.path.isdir(save_path):
                            if filename:
                                save_path = os.path.join(save_path, filename)
                            else:
                                # استفاده از نام تصادفی
                                import uuid
                                save_path = os.path.join(save_path, f"file_{uuid.uuid4()}")
                        
                        # ذخیره فایل
                        with open(save_path, 'w') as f:
                            chunk_size = 8192  # 8 Ú©ÛÙÙØ¨Ø§ÛØª
                            while True:
                                chunk = await response.content.read(chunk_size)
                                if not chunk:
                                    break
                                f.write(chunk)
                        
                        logger.debug(f"ÙØ§ÛÙ Ø¨Ø§ ÙÙÙÙÛØª Ø¯Ø± {save_path} Ø°Ø®ÛØ±Ù Ø´Ø¯.")
                        return save_path
                    
                    # ÙØ¯ÛØ±ÛØª Ø®Ø·Ø§ÙØ§ (ÙØ´Ø§Ø¨Ù _make_request)
                    elif response.status == 401 or response.status == 403:
                        # Ø®Ø·Ø§Û Ø§Ø­Ø±Ø§Ø² ÙÙÛØª
                        response_text = await response.text()
                        try:
                            response_data = json.loads(response_text)
                        except:
                            response_data = {"text": response_text}
                            
                        raise AuthenticationError(
                            f"Ø®Ø·Ø§Û Ø§Ø­Ø±Ø§Ø² ÙÙÛØª: {response_data.get('message', 'خطای نامشخص')}",
                            status_code=response.status,
                            response_data=response_data
                        )
                    
                    elif response.status == 429:
                        # محدودیت نرخ
                        retry_after = response.headers.get('Retry-After')
                        if retry_after:
                            try:
                                retry_after = int(retry_after)
                            except ValueError:
                                retry_after = 60
                        else:
                            retry_after = 60
                        
                        response_text = await response.text()
                        try:
                            response_data = json.loads(response_text)
                        except:
                            response_data = {"text": response_text}
                            
                        raise RateLimitExceededError(
                            "محدودیت نرخ درخواست فراتر رفته است.",
                            retry_after=retry_after,
                            status_code=response.status,
                            response_data=response_data
                        )
                    
                    else:
                        # سایر خطاها
                        response_text = await response.text()
                        try:
                            response_data = json.loads(response_text)
                            error_message = response_data.get('message', 'خطای نامشخص')
                        except:
                            response_data = {"text": response_text}
                            error_message = "خطای نامشخص"
                            
                        raise APIError(
                            f"خطای {response.status}: {error_message}",
                            status_code=response.status,
                            response_data=response_data
                        )
            
            except (RateLimitExceededError, AuthenticationError) as e:
                # خطاهایی که نیاز به برخورد خاص دارند
                raise
            
            except Exception as e:
                # سایر خطاها
                if attempt < self.retry_count:
                    # تأخیر قبل از تلاش مجدد
                    await asyncio.sleep(retry_delay)
                    
                    # افزایش تأخیر برای تلاش بعدی (تأخیر نمایی)
                    retry_delay *= 2
                    
                    logger.warning(f"خطا در دانلود فایل از {url}: {str(e)}. تلاش مجدد در {retry_delay} ثانیه...")
                    continue
                
                # آخرین تلاش ناموفق بود
                raise APIError(f"خطا در دانلود فایل: {str(e)}")
    
    async def paginate(self, endpoint: str, 
                      params: Optional[Dict[str, Any]] = None,
                      headers: Optional[Dict[str, str]] = None,
                      page_param: str = 'page',
                      limit_param: str = 'limit',
                      limit: int = 100,
                      max_pages: Optional[int] = None,
                      data_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        دریافت داده‌های صفحه‌بندی شده از API.
        
        پارامترها:
            endpoint: مسیر انتهایی API
            params: پارامترهای کوئری (اختیاری)
            headers: هدرهای سفارشی (اختیاری)
            page_param: نام پارامتر صفحه در API
            limit_param: نام پارامتر محدودیت تعداد در API
            limit: تعداد آیتم‌ها در هر صفحه
            max_pages: حداکثر تعداد صفحات برای دریافت (None برای دریافت همه)
            data_key: کلید آرایه داده‌ها در پاسخ API (None اگر خود پاسخ آرایه است)
            
        بازگشت:
            List[Dict[str, Any]]: لیست تمام آیتم‌های دریافتی
            
        استثناها:
            APIError: در صورت خطا در API
        """
        all_items = []
        current_page = 1
        
        # کپی پارامترها برای جلوگیری از تغییر پارامتر اصلی
        params = params.copy() if params else {}
        
        while True:
            # تنظیم پارامترهای صفحه‌بندی
            params[page_param] = current_page
            params[limit_param] = limit
            
            # دریافت داده‌های صفحه فعلی
            response = await self.get(endpoint, params=params, headers=headers)
            
            # استخراج آیتم‌ها از پاسخ
            items = response.get(data_key, []) if data_key else response
            
            # اگر آیتمی وجود ندارد یا پاسخ آرایه نیست، پایان صفحه‌بندی
            if not isinstance(items, list) or not items:
                break
            
            # افزودن آیتم‌ها به لیست کل
            all_items.extend(items)
            
            # بررسی پایان صفحه‌بندی
            if len(items) < limit:  # آخرین صفحه
                break
            
            # بررسی محدودیت تعداد صفحات
            if max_pages and current_page >= max_pages:
                break
            
            # رفتن به صفحه بعدی
            current_page += 1
        
        return all_items
    
    async def stream_response(self, method: str, endpoint: str, 
                            params: Optional[Dict[str, Any]] = None,
                            data: Optional[Dict[str, Any]] = None,
                            headers: Optional[Dict[str, str]] = None,
                            chunk_size: int = 1024) -> AsyncGenerator[bytes, None]:
        """
        دریافت پاسخ به صورت جریانی (مناسب برای فایل‌های بزرگ یا پاسخ‌های طولانی).
        
        پارامترها:
            method: روش HTTP (GET, POST, ...)
            endpoint: مسیر انتهایی API
            params: پارامترهای کوئری (اختیاری)
            data: داده‌های ارسالی (اختیاری)
            headers: هدرهای سفارشی (اختیاری)
            chunk_size: اندازه هر بخش داده (بایت)
            
        بازگشت:
            AsyncGenerator[bytes, None]: جنریتور برای دریافت داده‌ها به صورت جریانی
            
        استثناها:
            APIError: در صورت خطا در API
        """
        # اطمینان از وجود نشست
        await self.create_session()
        
        # ساخت URL کامل
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # ترکیب هدرهای پیش‌فرض و سفارشی
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)
        
        # آماده‌سازی داده‌ها
        json_data = None
        if data:
            json_data = data
        
        # استراتژی تلاش مجدد با تأخیر نمایی
        retry_delay = self.retry_delay
        
        for attempt in range(self.retry_count + 1):
            try:
                logger.debug(f"ارسال درخواست {method} جریانی به {url} (تلاش {attempt + 1}/{self.retry_count + 1})")
                
                async with getattr(self.session, method.lower())(
                    url,
                    params=params,
                    json=json_data,
                    headers=request_headers
                ) as response:
                    # بررسی کد وضعیت
                    if response.status >= 200 and response.status < 300:
                        # خواندن داده‌ها به صورت جریانی
                        while True:
                            chunk = await response.content.read(chunk_size)
                            if not chunk:
                                break
                            yield chunk
                        return
                    
                    # مدیریت خطاها (مشابه _make_request)
                    elif response.status == 401 or response.status == 403:
                        # خطای احراز هویت
                        response_text = await response.text()
                        try:
                            response_data = json.loads(response_text)
                        except:
                            response_data = {"text": response_text}
                            
                        raise AuthenticationError(
                            f"خطای احراز هویت: {response_data.get('message', 'خطای نامشخص')}",
                            status_code=response.status,
                            response_data=response_data
                        )
                    
                    # سایر خطاها مشابه _make_request
                    else:
                        response_text = await response.text()
                        try:
                            response_data = json.loads(response_text)
                            error_message = response_data.get('message', 'خطای نامشخص')
                        except:
                            response_data = {"text": response_text}
                            error_message = "خطای نامشخص"
                            
                        raise APIError(
                            f"خطای {response.status}: {error_message}",
                            status_code=response.status,
                            response_data=response_data
                        )
            
            except (RateLimitExceededError, AuthenticationError) as e:
                # خطاهایی که نیاز به برخورد خاص دارند
                raise
            
            except Exception as e:
                # سایر خطاها
                if attempt < self.retry_count:
                    # تأخیر قبل از تلاش مجدد
                    await asyncio.sleep(retry_delay)
                    
                    # افزایش تأخیر برای تلاش بعدی (تأخیر نمایی)
                    retry_delay *= 2
                    
                    logger.warning(f"خطا در درخواست جریانی به {url}: {str(e)}. تلاش مجدد در {retry_delay} ثانیه...")
                    continue
                
                # آخرین تلاش ناموفق بود
                raise APIError(f"خطا در دریافت پاسخ جریانی: {str(e)}")


class OAuth2API(BaseAPI):
    """
    کلاس API با پشتیبانی از OAuth2.
    این کلاس برای ارتباط با API‌هایی که از OAuth2 استفاده می‌کنند، مناسب است.
    """
    
    def __init__(self, base_url: str, client_id: str, client_secret: str, 
                token_url: str, scope: Optional[str] = None, **kwargs):
        """
        مقداردهی اولیه کلاس OAuth2API.
        
        پارامترها:
            base_url: آدرس پایه API
            client_id: شناسه کلاینت OAuth2
            client_secret: رمز کلاینت OAuth2
            token_url: آدرس دریافت توکن
            scope: محدوده دسترسی (اختیاری)
            **kwargs: سایر پارامترها برای کلاس پایه
        """
        super().__init__(base_url, **kwargs)
        
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.scope = scope
        
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = 0  # زمان انقضای توکن (timestamp)
        
        # حذف هدر Authorization پیش‌فرض
        if 'Authorization' in self.default_headers:
            del self.default_headers['Authorization']
    
    async def fetch_token(self, username: Optional[str] = None, 
                        password: Optional[str] = None,
                        refresh_token: Optional[str] = None) -> Dict[str, Any]:
        """
        دریافت توکن OAuth2.
        
        پارامترها:
            username: نام کاربری (برای روش password)
            password: رمز عبور (برای روش password)
            refresh_token: توکن تازه‌سازی (برای روش refresh_token)
            
        بازگشت:
            Dict[str, Any]: اطلاعات توکن
            
        استثناها:
            AuthenticationError: در صورت خطا در احراز هویت
        """
        # اطمینان از وجود نشست
        await self.create_session()
        
        # تعیین روش احراز هویت
        if refresh_token or self.refresh_token:
            grant_type = 'refresh_token'
            token_data = {
                'grant_type': grant_type,
                'refresh_token': refresh_token or self.refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
        elif username and password:
            grant_type = 'password'
            token_data = {
                'grant_type': grant_type,
                'username': username,
                'password': password,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
        else:
            grant_type = 'client_credentials'
            token_data = {
                'grant_type': grant_type,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
        
        # اضافه کردن محدوده دسترسی
        if self.scope:
            token_data['scope'] = self.scope
        
        try:
            # درخواست توکن (عدم استفاده از self._make_request برای جلوگیری از چرخه)
            async with self.session.post(self.token_url, data=token_data) as response:
                response_status = response.status
                response_data = await response.json()
                
                # بررسی کد وضعیت
                if response_status >= 200 and response_status < 300:
                    # موفقیت
                    self.access_token = response_data.get('access_token')
                    self.refresh_token = response_data.get('refresh_token', self.refresh_token)
                    
                    # محاسبه زمان انقضا
                    expires_in = response_data.get('expires_in', 3600)  # پیش‌فرض: 1 ساعت
                    self.token_expiry = time.time() + expires_in
                    
                    # تنظیم هدر Authorization
                    self.default_headers['Authorization'] = f"Bearer {self.access_token}"
                    
                    logger.info(f"توکن OAuth2 با موفقیت دریافت شد (روش: {grant_type}).")
                    return response_data
                else:
                    # خطا
                    error_message = response_data.get('error_description', response_data.get('error', 'خطای نامشخص'))
                    raise AuthenticationError(
                        f"خطا در دریافت توکن OAuth2: {error_message}",
                        status_code=response_status,
                        response_data=response_data
                    )
                    
        except ClientError as e:
            raise AuthenticationError(f"خطا در ارتباط با سرور توکن: {str(e)}")
        except json.JSONDecodeError:
            raise AuthenticationError("پاسخ نامعتبر از سرور توکن")
        except Exception as e:
            raise AuthenticationError(f"خطای نامشخص در دریافت توکن: {str(e)}")
    
    async def ensure_token(self) -> None:
        """
        اطمینان از معتبر بودن توکن و تازه‌سازی آن در صورت نیاز.
        
        استثناها:
            AuthenticationError: در صورت خطا در احراز هویت
        """
        # بررسی وجود توکن
        if not self.access_token:
            await self.fetch_token()
            return
        
        # بررسی انقضای توکن (با حاشیه امنیت 30 ثانیه)
        if time.time() > self.token_expiry - 30:
            if self.refresh_token:
                try:
                    # تلاش برای تازه‌سازی توکن
                    await self.fetch_token()
                    return
                except AuthenticationError:
                    # اگر تازه‌سازی ناموفق بود، دریافت توکن جدید
                    await self.fetch_token()
            else:
                # بدون توکن تازه‌سازی، دریافت توکن جدید
                await self.fetch_token()
    
    async def _make_request(self, *args, **kwargs) -> Dict[str, Any]:
        """
        انجام درخواست HTTP با اطمینان از معتبر بودن توکن.
        
        بازگشت:
            Dict[str, Any]: پاسخ API
            
        استثناها:
            AuthenticationError: در صورت خطا در احراز هویت
        """
        # اطمینان از معتبر بودن توکن
        await self.ensure_token()
        
        try:
            # انجام درخواست
            return await super()._make_request(*args, **kwargs)
        except AuthenticationError:
            # اگر خطای احراز هویت رخ داد، تلاش برای دریافت توکن جدید
            await self.fetch_token()
            
            # تلاش مجدد با توکن جدید
            return await super()._make_request(*args, **kwargs)


class APIMetrics:
    """
    کلاس جمع‌آوری آمار و متریک‌های API.
    """
    
    def __init__(self):
        """
        مقداردهی اولیه کلاس متریک‌ها.
        """
        self.requests_count = 0
        self.requests_success = 0
        self.requests_failed = 0
        self.requests_by_endpoint = {}
        self.response_times = []
        self.start_time = time.time()
    
    def record_request(self, endpoint: str, method: str, 
                      response_time: float, success: bool,
                      status_code: Optional[int] = None) -> None:
        """
        ثبت یک درخواست در آمار.
        
        پارامترها:
            endpoint: مسیر انتهایی API
            method: روش HTTP
            response_time: زمان پاسخ (ثانیه)
            success: آیا درخواست موفق بوده است؟
            status_code: کد وضعیت HTTP (اختیاری)
        """
        # ثبت تعداد کل درخواست‌ها
        self.requests_count += 1
        
        # ثبت نتیجه درخواست
        if success:
            self.requests_success += 1
        else:
            self.requests_failed += 1
        
        # ثبت زمان پاسخ
        self.response_times.append(response_time)
        
        # ثبت آمار بر اساس endpoint
        endpoint_key = f"{method} {endpoint}"
        if endpoint_key not in self.requests_by_endpoint:
            self.requests_by_endpoint[endpoint_key] = {
                'count': 0,
                'success': 0,
                'failed': 0,
                'response_times': []
            }
        
        endpoint_stats = self.requests_by_endpoint[endpoint_key]
        endpoint_stats['count'] += 1
        endpoint_stats['response_times'].append(response_time)
        
        if success:
            endpoint_stats['success'] += 1
        else:
            endpoint_stats['failed'] += 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        دریافت آمار و متریک‌های API.
        
        بازگشت:
            Dict[str, Any]: آمار و متریک‌ها
        """
        # محاسبه آمار کلی
        uptime = time.time() - self.start_time
        success_rate = (self.requests_success / self.requests_count * 100) if self.requests_count > 0 else 0
        
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        max_response_time = max(self.response_times) if self.response_times else 0
        min_response_time = min(self.response_times) if self.response_times else 0
        
        # محاسبه آمار هر endpoint
        endpoints_stats = {}
        for endpoint, stats in self.requests_by_endpoint.items():
            endpoint_avg_time = sum(stats['response_times']) / len(stats['response_times']) if stats['response_times'] else 0
            endpoint_success_rate = (stats['success'] / stats['count'] * 100) if stats['count'] > 0 else 0
            
            endpoints_stats[endpoint] = {
                'count': stats['count'],
                'success': stats['success'],
                'failed': stats['failed'],
                'success_rate': endpoint_success_rate,
                'avg_response_time': endpoint_avg_time
            }
        
        # بازگرداندن آمار
        return {
            'uptime': uptime,
            'requests': {
                'total': self.requests_count,
                'success': self.requests_success,
                'failed': self.requests_failed,
                'success_rate': success_rate
            },
            'response_time': {
                'average': avg_response_time,
                'max': max_response_time,
                'min': min_response_time
            },
            'endpoints': endpoints_stats
        }
    
    def reset_statistics(self) -> None:
        """
        بازنشانی آمار و متریک‌ها.
        """
        self.requests_count = 0
        self.requests_success = 0
        self.requests_failed = 0
        self.requests_by_endpoint = {}
        self.response_times = []
        self.start_time = time.time()


class APIMetricsMiddleware:
    """
    میان‌افزار ثبت متریک‌های API.
    """
    
    def __init__(self, metrics: APIMetrics):
        """
        مقداردهی اولیه میان‌افزار.
        
        پارامترها:
            metrics: شیء متریک‌ها
        """
        self.metrics = metrics
    
    async def process_request(self, method: str, endpoint: str):
        """
        پردازش درخواست قبل از ارسال.
        
        پارامترها:
            method: روش HTTP
            endpoint: مسیر انتهایی API
            
        بازگشت:
            float: زمان شروع درخواست
        """
        return time.time()
    
    async def process_response(self, method: str, endpoint: str, 
                             start_time: float, status_code: int,
                             success: bool):
        """
        پردازش پاسخ پس از دریافت.
        
        پارامترها:
            method: روش HTTP
            endpoint: مسیر انتهایی API
            start_time: زمان شروع درخواست
            status_code: کد وضعیت HTTP
            success: آیا درخواست موفق بوده است؟
        """
        # محاسبه زمان پاسخ
        response_time = time.time() - start_time
        
        # ثبت در متریک‌ها
        self.metrics.record_request(
            endpoint=endpoint,
            method=method,
            response_time=response_time,
            success=success,
            status_code=status_code
        )


class WebhookHandler:
    """
    کلاس مدیریت وب‌هوک‌ها.
    """
    
    def __init__(self, secret_key: Optional[str] = None):
        """
        مقداردهی اولیه کلاس وب‌هوک.
        
        پارامترها:
            secret_key: کلید مخفی برای تأیید امضای وب‌هوک (اختیاری)
        """
        self.secret_key = secret_key
        self.handlers = {}
    
    def register_handler(self, event_type: str, handler: Callable) -> None:
        """
        ثبت یک هندلر برای یک نوع رویداد.
        
        پارامترها:
            event_type: نوع رویداد
            handler: تابع پردازش رویداد
        """
        self.handlers[event_type] = handler
        logger.debug(f"هندلر برای رویداد '{event_type}' ثبت شد.")
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        تأیید امضای وب‌هوک.
        
        پارامترها:
            payload: محتوای درخواست
            signature: امضای دریافت شده
            
        بازگشت:
            bool: True اگر امضا معتبر باشد، False در غیر این صورت
        """
        if not self.secret_key:
            return True  # اگر کلید مخفی تنظیم نشده، همیشه تأیید شود
        
        import hmac
        import hashlib
        
        # محاسبه امضا
        computed_signature = hmac.new(
            self.secret_key.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # مقایسه با امضای دریافت شده
        return hmac.compare_digest(computed_signature, signature)
    
    async def process_webhook(self, payload: Dict[str, Any], 
                            headers: Dict[str, str]) -> Dict[str, Any]:
        """
        پردازش درخواست وب‌هوک.
        
        پارامترها:
            payload: محتوای درخواست
            headers: هدرهای درخواست
            
        بازگشت:
            Dict[str, Any]: نتیجه پردازش
            
        استثناها:
            ValueError: اگر امضا نامعتبر باشد یا نوع رویداد یافت نشود
        """
        # بررسی امضا (اگر وجود دارد)
        signature_header = headers.get('X-Webhook-Signature')
        if self.secret_key and signature_header:
            payload_bytes = json.dumps(payload).encode()
            if not self.verify_signature(payload_bytes, signature_header):
                raise ValueError("امضای نامعتبر")
        
        # استخراج نوع رویداد
        event_type = payload.get('event')
        if not event_type:
            # بررسی سایر فیلدهای متداول برای نوع رویداد
            event_type = payload.get('type') or payload.get('event_type')
        
        if not event_type:
            raise ValueError("نوع رویداد یافت نشد")
        
        # فراخوانی هندلر مناسب
        handler = self.handlers.get(event_type)
        if handler:
            logger.info(f"پردازش وب‌هوک برای رویداد '{event_type}'")
            return await handler(payload)
        else:
            logger.warning(f"هندلر برای رویداد '{event_type}' یافت نشد")
            return {"status": "ignored", "reason": f"No handler for event type: {event_type}"}


# استفاده از decorator برای مدیریت خطاها در توابع API
def api_error_handler(func):
    """
    دکوراتور برای مدیریت خطاهای API در توابع.
    
    پارامترها:
        func: تابع هدف
        
    بازگشت:
        Callable: تابع wrapper
    """
    return BaseAPI.handle_error(func)