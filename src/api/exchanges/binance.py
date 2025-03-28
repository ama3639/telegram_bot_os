#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول ارتباط با API صرافی بایننس.

این ماژول امکان ارتباط با API بایننس برای دریافت قیمت‌های ارزهای دیجیتال،
انجام معاملات و دیگر عملیات مربوط به صرافی را فراهم می‌کند.

تاریخ ایجاد: ۱۴۰۴/۰۱/۰۷
"""

import logging
import time
import hmac
import hashlib
from typing import Dict, Any, List, Optional, Union, Tuple
import json

from api.base import BaseAPI, APIError, api_error_handler, APIMetrics

logger = logging.getLogger(__name__)

class BinanceAPI(BaseAPI):
    """ 
    کلاس ارتباط با API صرافی بایننس.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, 
                testnet: bool = False, **kwargs):
        """
        مقداردهی اولیه کلاس API بایننس.
        
        پارامترها:
            api_key: کلید API بایننس (برای درخواست‌های خصوصی)
            api_secret: رمز API بایننس (برای درخواست‌های خصوصی)
            testnet: آیا از شبکه تست استفاده شود؟
            **kwargs: سایر پارامترها برای کلاس پایه
        """
        # تعیین URL پایه بر اساس testnet
        base_url = "https://testnet.binance.vision/api" if testnet else "https://api.binance.com/api"
        
        # مقداردهی کلاس پایه
        super().__init__(base_url, **kwargs)
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # تنظیم هدرها اگر api_key موجود باشد
        if api_key:
            self.default_headers['X-MBX-APIKEY'] = api_key
        
        # ایجاد شیء متریک‌ها
        self.metrics = APIMetrics()
        
        logger.info(f"API بایننس {'(testnet)' if testnet else ''} راه‌اندازی شد.")
    
    def _generate_signature(self, query_string: str) -> str:
        """
        تولید امضا برای درخواست‌های خصوصی.
        
        پارامترها:
            query_string: رشته پارامترهای کوئری
            
        بازگشت:
            str: امضای تولید شده
        """
        if not self.api_secret:
            raise APIError("برای درخواست‌های خصوصی، api_secret باید تنظیم شود.")
        
        # تولید امضا با HMAC-SHA256
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _add_signature(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        افزودن زمان و امضا به پارامترها.
        
        پارامترها:
            params: پارامترهای درخواست
            
        بازگشت:
            Dict[str, Any]: پارامترهای همراه با زمان و امضا
        """
        # کپی پارامترها برای جلوگیری از تغییر پارامتر اصلی
        params = params.copy()
        
        # افزودن زمان
        params['timestamp'] = int(time.time() * 1000)
        
        # ساخت رشته کوئری
        query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params.keys())])
        
        # تولید و افزودن امضا
        params['signature'] = self._generate_signature(query_string)
        
        return params
    
    @api_error_handler
    async def get_server_time(self) -> Dict[str, Any]:
        """
        دریافت زمان سرور بایننس.
        
        بازگشت:
            Dict[str, Any]: زمان سرور
        """
        start_time = time.time()
        response = await self.get('/v3/time')
        
        # ثبت متریک
        self.metrics.record_request(
            endpoint='/v3/time',
            method='GET',
            response_time=time.time() - start_time,
            success=True
        )
        
        return response
    
    @api_error_handler
    async def get_exchange_info(self) -> Dict[str, Any]:
        """
        دریافت اطلاعات صرافی.
        
        بازگشت:
            Dict[str, Any]: اطلاعات صرافی
        """
        start_time = time.time()
        response = await self.get('/v3/exchangeInfo')
        
        # ثبت متریک
        self.metrics.record_request(
            endpoint='/v3/exchangeInfo',
            method='GET',
            response_time=time.time() - start_time,
            success=True
        )
        
        return response
    
    @api_error_handler
    async def get_ticker_price(self, symbol: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        دریافت قیمت لحظه‌ای یک یا چند ارز.
        
        پارامترها:
            symbol: نماد ارز (مثلاً "BTCUSDT") یا None برای دریافت همه نمادها
            
        بازگشت:
            Dict[str, Any] یا List[Dict[str, Any]]: قیمت‌های لحظه‌ای
        """
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        start_time = time.time()
        response = await self.get('/v3/ticker/price', params=params)
        
        # ثبت متریک
        self.metrics.record_request(
            endpoint='/v3/ticker/price',
            method='GET',
            response_time=time.time() - start_time,
            success=True
        )
        
        return response
    
    @api_error_handler
    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """
        دریافت دفتر سفارشات یک ارز.
        
        پارامترها:
            symbol: نماد ارز (مثلاً "BTCUSDT")
            limit: تعداد سفارشات (حداکثر 5000)
            
        بازگشت:
            Dict[str, Any]: دفتر سفارشات
        """
        params = {
            'symbol': symbol,
            'limit': limit
        }
        
        start_time = time.time()
        response = await self.get('/v3/depth', params=params)
        
        # ثبت متریک
        self.metrics.record_request(
            endpoint='/v3/depth',
            method='GET',
            response_time=time.time() - start_time,
            success=True
        )
        
        return response
    
    @api_error_handler
    async def get_klines(self, symbol: str, interval: str, 
                       start_time: Optional[int] = None,
                       end_time: Optional[int] = None,
                       limit: int = 500) -> List[List[Any]]:
        """
        دریافت داده‌های کندل (نمودار قیمت).
        
        پارامترها:
            symbol: نماد ارز (مثلاً "BTCUSDT")
            interval: بازه زمانی (مثلاً "1m", "1h", "1d")
            start_time: زمان شروع به میلی‌ثانیه (اختیاری)
            end_time: زمان پایان به میلی‌ثانیه (اختیاری)
            limit: تعداد کندل‌ها (حداکثر 1000)
            
        بازگشت:
            List[List[Any]]: داده‌های کندل
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        if start_time:
            params['startTime'] = start_time
        
        if end_time:
            params['endTime'] = end_time
        
        start_time_request = time.time()
        response = await self.get('/v3/klines', params=params)
        
        # ثبت متریک
        self.metrics.record_request(
            endpoint='/v3/klines',
            method='GET',
            response_time=time.time() - start_time_request,
            success=True
        )
        
        return response
    
    @api_error_handler
    async def get_account_info(self) -> Dict[str, Any]:
        """
        دریافت اطلاعات حساب کاربری.
        
        بازگشت:
            Dict[str, Any]: اطلاعات حساب
            
        استثناها:
            APIError: اگر api_key یا api_secret تنظیم نشده باشد
        """
        if not self.api_key or not self.api_secret:
            raise APIError("برای دریافت اطلاعات حساب، api_key و api_secret باید تنظیم شوند.")
        
        # ساخت پارامترها با امضا
        params = self._add_signature({})
        
        start_time = time.time()
        response = await self.get('/v3/account', params=params)
        
        # ثبت متریک
        self.metrics.record_request(
            endpoint='/v3/account',
            method='GET',
            response_time=time.time() - start_time,
            success=True
        )
        
        return response
    
    @api_error_handler
    async def create_order(self, symbol: str, side: str, order_type: str,
                         quantity: Optional[float] = None,
                         quote_order_qty: Optional[float] = None,
                         price: Optional[float] = None,
                         time_in_force: Optional[str] = None,
                         **kwargs) -> Dict[str, Any]:
        """
        ایجاد سفارش جدید.
        
        پارامترها:
            symbol: نماد ارز (مثلاً "BTCUSDT")
            side: جهت معامله ("BUY" یا "SELL")
            order_type: نوع سفارش ("LIMIT", "MARKET", "STOP_LOSS", ...)
            quantity: مقدار ارز پایه (برای MARKET خرید روی USDT نیاز نیست)
            quote_order_qty: مقدار ارز نقل (فقط برای MARKET روی USDT)
            price: قیمت (فقط برای LIMIT)
            time_in_force: مدت اعتبار (فقط برای LIMIT، مثلاً "GTC", "IOC", "FOK")
            **kwargs: سایر پارامترهای اختیاری
            
        بازگشت:
            Dict[str, Any]: اطلاعات سفارش ایجاد شده
            
        استثناها:
            APIError: اگر پارامترهای لازم وارد نشده باشند یا api_key/api_secret تنظیم نشده باشند
        """
        if not self.api_key or not self.api_secret:
            raise APIError("برای ایجاد سفارش، api_key و api_secret باید تنظیم شوند.")
        
        # ساخت پارامترهای پایه
        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type
        }
        
        # افزودن پارامترهای اختیاری
        if quantity is not None:
            params['quantity'] = quantity
        
        if quote_order_qty is not None:
            params['quoteOrderQty'] = quote_order_qty
        
        if price is not None:
            params['price'] = price
        
        if time_in_force is not None:
            params['timeInForce'] = time_in_force
        
        # افزودن سایر پارامترها
        params.update(kwargs)
        
        # ساخت پارامترها با امضا
        params = self._add_signature(params)
        
        start_time = time.time()
        response = await self.post('/v3/order', params=params)
        
        # ثبت متریک
        self.metrics.record_request(
            endpoint='/v3/order',
            method='POST',
            response_time=time.time() - start_time,
            success=True
        )
        
        return response
    
    @api_error_handler
    async def cancel_order(self, symbol: str, order_id: Optional[int] = None,
                         orig_client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """
        لغو یک سفارش.
        
        پارامترها:
            symbol: نماد ارز (مثلاً "BTCUSDT")
            order_id: شناسه سفارش (اختیاری)
            orig_client_order_id: شناسه سفارش مشتری (اختیاری)
            
        بازگشت:
            Dict[str, Any]: اطلاعات سفارش لغو شده
            
        استثناها:
            APIError: اگر پارامترهای لازم وارد نشده باشند یا api_key/api_secret تنظیم نشده باشند
        """
        if not self.api_key or not self.api_secret:
            raise APIError("برای لغو سفارش، api_key و api_secret باید تنظیم شوند.")
        
        if not order_id and not orig_client_order_id:
            raise APIError("حداقل یکی از پارامترهای order_id یا orig_client_order_id باید وارد شود.")
        
        # ساخت پارامترهای پایه
        params = {
            'symbol': symbol
        }
        
        # افزودن شناسه سفارش
        if order_id:
            params['orderId'] = order_id
        
        if orig_client_order_id:
            params['origClientOrderId'] = orig_client_order_id
        
        # ساخت پارامترها با امضا
        params = self._add_signature(params)
        
        start_time = time.time()
        response = await self.delete('/v3/order', params=params)
        
        # ثبت متریک
        self.metrics.record_request(
            endpoint='/v3/order',
            method='DELETE',
            response_time=time.time() - start_time,
            success=True
        )
        
        return response
    
    @api_error_handler
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        دریافت لیست سفارشات باز.
        
        پارامترها:
            symbol: نماد ارز (مثلاً "BTCUSDT") یا None برای دریافت همه نمادها
            
        بازگشت:
            List[Dict[str, Any]]: لیست سفارشات باز
            
        استثناها:
            APIError: اگر api_key یا api_secret تنظیم نشده باشد
        """
        if not self.api_key or not self.api_secret:
            raise APIError("برای دریافت سفارشات باز، api_key و api_secret باید تنظیم شوند.")
        
        # ساخت پارامترهای پایه
        params = {}
        
        if symbol:
            params['symbol'] = symbol
        
        # ساخت پارامترها با امضا
        params = self._add_signature(params)
        
        start_time = time.time()
        response = await self.get('/v3/openOrders', params=params)
        
        # ثبت متریک
        self.metrics.record_request(
            endpoint='/v3/openOrders',
            method='GET',
            response_time=time.time() - start_time,
            success=True
        )
        
        return response
    
    @api_error_handler
    async def get_order(self, symbol: str, order_id: Optional[int] = None,
                      orig_client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """
        دریافت اطلاعات یک سفارش.
        
        پارامترها:
            symbol: نماد ارز (مثلاً "BTCUSDT")
            order_id: شناسه سفارش (اختیاری)
            orig_client_order_id: شناسه سفارش مشتری (اختیاری)
            
        بازگشت:
            Dict[str, Any]: اطلاعات سفارش
            
        استثناها:
            APIError: اگر پارامترهای لازم وارد نشده باشند یا api_key/api_secret تنظیم نشده باشند
        """
        if not self.api_key or not self.api_secret:
            raise APIError("برای دریافت اطلاعات سفارش، api_key و api_secret باید تنظیم شوند.")
        
        if not order_id and not orig_client_order_id:
            raise APIError("حداقل یکی از پارامترهای order_id یا orig_client_order_id باید وارد شود.")
        
        # ساخت پارامترهای پایه
        params = {
            'symbol': symbol
        }
        
        # افزودن شناسه سفارش
        if order_id:
            params['orderId'] = order_id
        
        if orig_client_order_id:
            params['origClientOrderId'] = orig_client_order_id
        
        # ساخت پارامترها با امضا
        params = self._add_signature(params)
        
        start_time = time.time()
        response = await self.get('/v3/order', params=params)
        
        # ثبت متریک
        self.metrics.record_request(
            endpoint='/v3/order',
            method='GET',
            response_time=time.time() - start_time,
            success=True
        )
        
        return response
    
    @api_error_handler
    async def get_historical_trades(self, symbol: str, limit: int = 500,
                               from_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        دریافت معاملات تاریخی یک ارز.
        
        پارامترها:
            symbol: نماد ارز (مثلاً "BTCUSDT")
            limit: تعداد معاملات (حداکثر 1000)
            from_id: شناسه شروع (اختیاری)
            
        بازگشت:
            List[Dict[str, Any]]: لیست معاملات
        """
        params = {
            'symbol': symbol,
            'limit': limit
        }
        
        if from_id:
            params['fromId'] = from_id
        
        # افزودن هدر API Key اگر موجود باشد
        headers = {'X-MBX-APIKEY': self.api_key} if self.api_key else None
        
        start_time = time.time()
        response = await self.get('/v3/historicalTrades', params=params, headers=headers)
        
        # ثبت متریک
        self.metrics.record_request(
            endpoint='/v3/historicalTrades',
            method='GET',
            response_time=time.time() - start_time,
            success=True
        )
        
        return response
    
    @api_error_handler
    async def get_aggregate_trades(self, symbol: str, limit: int = 500,
                             start_time: Optional[int] = None,
                             end_time: Optional[int] = None,
                             from_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        دریافت معاملات تجمیع شده یک ارز.
        
        پارامترها:
            symbol: نماد ارز (مثلاً "BTCUSDT")
            limit: تعداد معاملات (حداکثر 1000)
            start_time: زمان شروع به میلی‌ثانیه (اختیاری)
            end_time: زمان پایان به میلی‌ثانیه (اختیاری)
            from_id: شناسه شروع (اختیاری)
            
        بازگشت:
            List[Dict[str, Any]]: لیست معاملات تجمیع شده
        """
        params = {
            'symbol': symbol,
            'limit': limit
        }
        
        if start_time:
            params['startTime'] = start_time
        
        if end_time:
            params['endTime'] = end_time
        
        if from_id:
            params['fromId'] = from_id
        
        start_time_request = time.time()
        response = await self.get('/v3/aggTrades', params=params)
        
        # ثبت متریک
        self.metrics.record_request(
            endpoint='/v3/aggTrades',
            method='GET',
            response_time=time.time() - start_time_request,
            success=True
        )
        
        return response
    
    @api_error_handler
    async def get_recent_trades(self, symbol: str, limit: int = 500) -> List[Dict[str, Any]]:
        """
        دریافت معاملات اخیر یک ارز.
        
        پارامترها:
            symbol: نماد ارز (مثلاً "BTCUSDT")
            limit: تعداد معاملات (حداکثر 1000)
            
        بازگشت:
            List[Dict[str, Any]]: لیست معاملات اخیر
        """
        params = {
            'symbol': symbol,
            'limit': limit
        }
        
        start_time = time.time()
        response = await self.get('/v3/trades', params=params)
        
        # ثبت متریک
        self.metrics.record_request(
            endpoint='/v3/trades',
            method='GET',
            response_time=time.time() - start_time,
            success=True
        )
        
        return response
    
    async def get_all_tickers(self) -> List[Dict[str, Any]]:
        """
        دریافت قیمت لحظه‌ای تمام ارزها.
        
        بازگشت:
            List[Dict[str, Any]]: لیست قیمت‌های لحظه‌ای
        """
        return await self.get_ticker_price()
    
    async def get_price(self, symbol: str) -> float:
        """
        دریافت قیمت لحظه‌ای یک ارز به صورت عدد.
        
        پارامترها:
            symbol: نماد ارز (مثلاً "BTCUSDT")
            
        بازگشت:
            float: قیمت لحظه‌ای
            
        استثناها:
            APIError: اگر نماد یافت نشود
        """
        ticker = await self.get_ticker_price(symbol)
        
        if isinstance(ticker, dict) and 'price' in ticker:
            return float(ticker['price'])
        
        raise APIError(f"قیمت برای نماد {symbol} یافت نشد.")
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        دریافت متریک‌های API بایننس.
        
        بازگشت:
            Dict[str, Any]: متریک‌ها
        """
        return self.metrics.get_statistics()
    
    def reset_metrics(self) -> None:
        """
        بازنشانی متریک‌های API بایننس.
        """
        self.metrics.reset_statistics()