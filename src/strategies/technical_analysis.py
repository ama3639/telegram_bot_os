 #!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول تحلیل تکنیکال.

این ماژول شامل توابع و کلاس‌های مورد نیاز برای تحلیل تکنیکال بازار ارزهای دیجیتال است.
استراتژی‌های مختلف تحلیل تکنیکال و اتصال به API‌های خارجی را مدیریت می‌کند.

تاریخ ایجاد: ۱۴۰۴/۰۸/۰۱
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Union, Tuple
import requests
import json
import time
from datetime import datetime, timedelta

from src.utils.timezone_utils import get_current_datetime
from src.api.exchanges.binance import BinanceAPI
from src.api.exchanges.kucoin import KucoinAPI
from src.core.config import Config

logger = logging.getLogger('strategies.technical_analysis')


class TechnicalAnalysis:
    """
    کلاس اصلی تحلیل تکنیکال.
    
    این کلاس الگوریتم‌های تحلیل تکنیکال را پیاده‌سازی می‌کند و
    با API‌های صرافی‌ها و سرویس‌های خارجی ارتباط برقرار می‌کند.
    """
    
    def __init__(self, config: Config):
        """
        مقداردهی اولیه کلاس تحلیل تکنیکال.
        
        Args:
            config (Config): تنظیمات برنامه
        """
        self.config = config
        
        # اتصال به API صرافی‌ها
        binance_api_key = self.config.get('BINANCE_API_KEY')
        binance_secret_key = self.config.get('BINANCE_SECRET_KEY')
        binance_testnet = self.config.get_bool('BINANCE_TESTNET', False)
        
        kucoin_api_key = self.config.get('KUCOIN_API_KEY')
        kucoin_secret_key = self.config.get('KUCOIN_SECRET_KEY')
        kucoin_passphrase = self.config.get('KUCOIN_PASSPHRASE')
        
        # ایجاد اتصال‌های API در صورت وجود کلیدها
        self.binance_api = None
        self.kucoin_api = None
        
        if binance_api_key and binance_secret_key:
            self.binance_api = BinanceAPI(
                api_key=binance_api_key,
                api_secret=binance_secret_key,
                testnet=binance_testnet
            )
        
        if kucoin_api_key and kucoin_secret_key and kucoin_passphrase:
            self.kucoin_api = KucoinAPI(
                api_key=kucoin_api_key,
                api_secret=kucoin_secret_key,
                passphrase=kucoin_passphrase
            )
        
        logger.info("کلاس تحلیل تکنیکال با موفقیت مقداردهی شد")
    
    # ==== استراتژی‌های تحلیل تکنیکال ====
    
    def analyze_market(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> Dict[str, Any]:
        """
        تحلیل بازار برای یک ارز دیجیتال.
        
        Args:
            symbol: نماد ارز (مثلا 'BTCUSDT')
            timeframe: بازه زمانی (مثلا '1h', '4h', '1d')
            limit: تعداد کندل‌های تاریخی
            
        Returns:
            Dict[str, Any]: نتایج تحلیل شامل اندیکاتورها و سیگنال‌ها
        """
        try:
            # دریافت داده‌های تاریخی
            historical_data = self.get_historical_data(symbol, timeframe, limit)
            if not historical_data or len(historical_data) < limit:
                return {'status': 'error', 'message': 'داده‌های کافی برای تحلیل وجود ندارد'}
            
            # تبدیل به دیتافریم
            df = pd.DataFrame(historical_data)
            
            # محاسبه اندیکاتورها
            df = self.calculate_indicators(df)
            
            # تحلیل الگوهای قیمتی
            patterns = self.analyze_price_patterns(df)
            
            # تحلیل حمایت و مقاومت
            support_resistance = self.find_support_resistance(df)
            
            # تشخیص روند
            trend = self.detect_trend(df)
            
            # تولید سیگنال خرید/فروش
            signal = self.generate_signal(df, trend, patterns)
            
            # قیمت فعلی
            current_price = df.iloc[-1]['close']
            
            # نتایج تحلیل
            analysis_result = {
                'status': 'success',
                'symbol': symbol,
                'timeframe': timeframe,
                'current_price': current_price,
                'trend': trend,
                'patterns': patterns,
                'support_resistance': support_resistance,
                'indicators': {
                    'rsi': df.iloc[-1].get('rsi', None),
                    'macd': {
                        'macd': df.iloc[-1].get('macd', None),
                        'signal': df.iloc[-1].get('macd_signal', None),
                        'histogram': df.iloc[-1].get('macd_hist', None)
                    },
                    'bb': {
                        'upper': df.iloc[-1].get('bb_upper', None),
                        'middle': df.iloc[-1].get('bb_middle', None),
                        'lower': df.iloc[-1].get('bb_lower', None)
                    },
                    'ma': {
                        'ma20': df.iloc[-1].get('ma20', None),
                        'ma50': df.iloc[-1].get('ma50', None),
                        'ma200': df.iloc[-1].get('ma200', None)
                    }
                },
                'signal': signal,
                'timestamp': get_current_datetime().isoformat()
            }
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"خطا در تحلیل بازار برای {symbol}: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def get_historical_data(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List[Dict[str, Any]]:
        """
        دریافت داده‌های تاریخی از صرافی.
        
        Args:
            symbol: نماد ارز (مثلا 'BTCUSDT')
            timeframe: بازه زمانی (مثلا '1h', '4h', '1d')
            limit: تعداد کندل‌های تاریخی
            
        Returns:
            List[Dict[str, Any]]: لیست کندل‌های تاریخی
        """
        try:
            # تلاش برای استفاده از API بایننس
            if self.binance_api:
                raw_data = self.binance_api.get_klines(symbol, timeframe, limit)
                if raw_data:
                    # تبدیل داده‌های خام به فرمت استاندارد
                    standardized_data = []
                    for candle in raw_data:
                        standardized_data.append({
                            'timestamp': candle[0],
                            'datetime': datetime.fromtimestamp(candle[0] / 1000).isoformat(),
                            'open': float(candle[1]),
                            'high': float(candle[2]),
                            'low': float(candle[3]),
                            'close': float(candle[4]),
                            'volume': float(candle[5])
                        })
                    return standardized_data
            
            # اگر بایننس موفق نبود، از کوکوین استفاده می‌کنیم
            if self.kucoin_api:
                raw_data = self.kucoin_api.get_klines(symbol, timeframe, limit)
                if raw_data:
                    # تبدیل داده‌های خام به فرمت استاندارد
                    standardized_data = []
                    for candle in raw_data:
                        standardized_data.append({
                            'timestamp': candle[0],
                            'datetime': datetime.fromtimestamp(candle[0] / 1000).isoformat(),
                            'open': float(candle[1]),
                            'high': float(candle[2]),
                            'low': float(candle[3]),
                            'close': float(candle[4]),
                            'volume': float(candle[5])
                        })
                    return standardized_data
            
            # اگر هیچ API در دسترس نباشد
            logger.warning(f"هیچ اتصال API برای دریافت داده‌های تاریخی {symbol} وجود ندارد")
            return []
            
        except Exception as e:
            logger.error(f"خطا در دریافت داده‌های تاریخی برای {symbol}: {str(e)}")
            return []
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        محاسبه اندیکاتورهای تکنیکال روی دیتافریم.
        
        Args:
            df: دیتافریم حاوی داده‌های قیمت
            
        Returns:
            pd.DataFrame: دیتافریم با اندیکاتورهای اضافه شده
        """
        # اطمینان از وجود داده‌های کافی
        if len(df) < 200:
            logger.warning("تعداد داده‌ها برای محاسبه همه اندیکاتورها کافی نیست")
        
        # کپی دیتافریم برای جلوگیری از تغییر اصل داده‌ها
        df_result = df.copy()
        
        # محاسبه RSI
        delta = df_result['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df_result['rsi'] = 100 - (100 / (1 + rs))
        
        # محاسبه میانگین متحرک
        df_result['ma20'] = df_result['close'].rolling(window=20).mean()
        df_result['ma50'] = df_result['close'].rolling(window=50).mean()
        df_result['ma200'] = df_result['close'].rolling(window=200).mean()
        
        # محاسبه باندهای بولینگر
        df_result['bb_middle'] = df_result['close'].rolling(window=20).mean()
        df_result['bb_std'] = df_result['close'].rolling(window=20).std()
        df_result['bb_upper'] = df_result['bb_middle'] + (df_result['bb_std'] * 2)
        df_result['bb_lower'] = df_result['bb_middle'] - (df_result['bb_std'] * 2)
        
        # محاسبه MACD
        ema12 = df_result['close'].ewm(span=12, adjust=False).mean()
        ema26 = df_result['close'].ewm(span=26, adjust=False).mean()
        df_result['macd'] = ema12 - ema26
        df_result['macd_signal'] = df_result['macd'].ewm(span=9, adjust=False).mean()
        df_result['macd_hist'] = df_result['macd'] - df_result['macd_signal']
        
        # محاسبه Stochastic
        low_14 = df_result['low'].rolling(window=14).min()
        high_14 = df_result['high'].rolling(window=14).max()
        df_result['stoch_k'] = 100 * ((df_result['close'] - low_14) / (high_14 - low_14))
        df_result['stoch_d'] = df_result['stoch_k'].rolling(window=3).mean()
        
        return df_result
    
    def detect_trend(self, df: pd.DataFrame) -> str:
        """
        تشخیص روند قیمت (صعودی، نزولی، نوسانی).
        
        Args:
            df: دیتافریم حاوی داده‌های قیمت و اندیکاتورها
            
        Returns:
            str: نوع روند ('صعودی'، 'نزولی'، 'نوسانی')
        """
        # بررسی میانگین متحرک‌ها
        last_index = -1
        try:
            # روند بر اساس میانگین متحرک
            ma20 = df.iloc[last_index]['ma20']
            ma50 = df.iloc[last_index]['ma50']
            ma200 = df.iloc[last_index]['ma200']
            
            current_price = df.iloc[last_index]['close']
            
            # روند صعودی: قیمت بالای MA200 و MA50 بالای MA200
            if current_price > ma200 and ma50 > ma200:
                return 'صعودی'
            
            # روند نزولی: قیمت زیر MA200 و MA50 زیر MA200
            elif current_price < ma200 and ma50 < ma200:
                return 'نزولی'
            
            # تحلیل RSI
            rsi = df.iloc[last_index]['rsi']
            if rsi > 70:
                return 'اشباع خرید'
            elif rsi < 30:
                return 'اشباع فروش'
            
            # در غیر این صورت، روند نوسانی
            return 'نوسانی'
        
        except (KeyError, IndexError):
            # اگر اندیکاتورها هنوز محاسبه نشده‌اند
            return 'نامشخص'
    
    def analyze_price_patterns(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        تحلیل الگوهای قیمتی.
        
        Args:
            df: دیتافریم حاوی داده‌های قیمت
            
        Returns:
            List[Dict[str, Any]]: لیست الگوهای شناسایی شده
        """
        patterns = []
        
        try:
            # الگوی سر و شانه
            # الگوی مثلث
            # الگوی دابل تاپ/باتم
            # پیاده‌سازی کامل الگوها نیاز به کدنویسی پیچیده‌تری دارد
            
            # نمونه ساده: شناسایی دابل تاپ/باتم
            highs = df['high'].rolling(window=5, center=True).max()
            lows = df['low'].rolling(window=5, center=True).min()
            
            # یافتن نقاط اوج محلی
            peak_indices = []
            for i in range(2, len(df) - 2):
                if df.iloc[i]['high'] == highs.iloc[i] and df.iloc[i]['high'] > df.iloc[i-1]['high'] and df.iloc[i]['high'] > df.iloc[i+1]['high']:
                    peak_indices.append(i)
            
            # یافتن نقاط کف محلی
            bottom_indices = []
            for i in range(2, len(df) - 2):
                if df.iloc[i]['low'] == lows.iloc[i] and df.iloc[i]['low'] < df.iloc[i-1]['low'] and df.iloc[i]['low'] < df.iloc[i+1]['low']:
                    bottom_indices.append(i)
            
            # شناسایی دابل تاپ
            for i in range(len(peak_indices) - 1):
                peak1 = peak_indices[i]
                peak2 = peak_indices[i + 1]
                
                # اگر فاصله بین دو اوج معقول باشد و اختلاف قیمت کم باشد
                if 5 <= peak2 - peak1 <= 20:
                    price_diff = abs(df.iloc[peak1]['high'] - df.iloc[peak2]['high'])
                    avg_price = (df.iloc[peak1]['high'] + df.iloc[peak2]['high']) / 2
                    
                    if price_diff / avg_price < 0.03:  # اختلاف کمتر از 3٪
                        patterns.append({
                            'type': 'دابل تاپ',
                            'position1': peak1,
                            'position2': peak2,
                            'price1': df.iloc[peak1]['high'],
                            'price2': df.iloc[peak2]['high'],
                            'strength': 'متوسط'
                        })
            
            # شناسایی دابل باتم
            for i in range(len(bottom_indices) - 1):
                bottom1 = bottom_indices[i]
                bottom2 = bottom_indices[i + 1]
                
                # اگر فاصله بین دو کف معقول باشد و اختلاف قیمت کم باشد
                if 5 <= bottom2 - bottom1 <= 20:
                    price_diff = abs(df.iloc[bottom1]['low'] - df.iloc[bottom2]['low'])
                    avg_price = (df.iloc[bottom1]['low'] + df.iloc[bottom2]['low']) / 2
                    
                    if price_diff / avg_price < 0.03:  # اختلاف کمتر از 3٪
                        patterns.append({
                            'type': 'دابل باتم',
                            'position1': bottom1,
                            'position2': bottom2,
                            'price1': df.iloc[bottom1]['low'],
                            'price2': df.iloc[bottom2]['low'],
                            'strength': 'متوسط'
                        })
            
            return patterns
            
        except Exception as e:
            logger.error(f"خطا در تحلیل الگوهای قیمتی: {str(e)}")
            return []
    
    def find_support_resistance(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        """
        یافتن سطوح حمایت و مقاومت.
        
        Args:
            df: دیتافریم حاوی داده‌های قیمت
            
        Returns:
            Dict[str, List[float]]: سطوح حمایت و مقاومت
        """
        try:
            # تعداد نقاط برای تحلیل
            lookback = min(100, len(df))
            
            # یافتن نقاط اوج و کف محلی
            highs = []
            lows = []
            
            for i in range(5, lookback - 5):
                # اوج محلی
                if df.iloc[i]['high'] > df.iloc[i-1]['high'] and \
                   df.iloc[i]['high'] > df.iloc[i-2]['high'] and \
                   df.iloc[i]['high'] > df.iloc[i+1]['high'] and \
                   df.iloc[i]['high'] > df.iloc[i+2]['high']:
                    highs.append(df.iloc[i]['high'])
                
                # کف محلی
                if df.iloc[i]['low'] < df.iloc[i-1]['low'] and \
                   df.iloc[i]['low'] < df.iloc[i-2]['low'] and \
                   df.iloc[i]['low'] < df.iloc[i+1]['low'] and \
                   df.iloc[i]['low'] < df.iloc[i+2]['low']:
                    lows.append(df.iloc[i]['low'])
            
            # گروه‌بندی نقاط نزدیک به هم
            tolerance = 0.01  # تلورانس 1٪
            
            # گروه‌بندی نقاط مقاومت
            resistance_levels = []
            for high in sorted(highs):
                if not resistance_levels:
                    resistance_levels.append(high)
                else:
                    # بررسی نزدیکی به سطوح موجود
                    is_close = False
                    for i, level in enumerate(resistance_levels):
                        if abs(high - level) / level < tolerance:
                            # میانگین‌گیری
                            resistance_levels[i] = (level + high) / 2
                            is_close = True
                            break
                    
                    if not is_close:
                        resistance_levels.append(high)
            
            # گروه‌بندی نقاط حمایت
            support_levels = []
            for low in sorted(lows):
                if not support_levels:
                    support_levels.append(low)
                else:
                    # بررسی نزدیکی به سطوح موجود
                    is_close = False
                    for i, level in enumerate(support_levels):
                        if abs(low - level) / level < tolerance:
                            # میانگین‌گیری
                            support_levels[i] = (level + low) / 2
                            is_close = True
                            break
                    
                    if not is_close:
                        support_levels.append(low)
            
            # مرتب‌سازی نزولی برای مقاومت و صعودی برای حمایت
            resistance_levels.sort(reverse=True)
            support_levels.sort()
            
            # فیلتر کردن سطوح دور از قیمت فعلی
            current_price = df.iloc[-1]['close']
            
            filtered_resistance = [r for r in resistance_levels if r > current_price]
            filtered_support = [s for s in support_levels if s < current_price]
            
            # محدود کردن تعداد سطوح
            filtered_resistance = filtered_resistance[:3]
            filtered_support = filtered_support[:3]
            
            return {
                'resistance': filtered_resistance,
                'support': filtered_support
            }
        
        except Exception as e:
            logger.error(f"خطا در یافتن سطوح حمایت و مقاومت: {str(e)}")
            return {'resistance': [], 'support': []}
    
    def generate_signal(self, df: pd.DataFrame, trend: str, patterns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        تولید سیگنال خرید/فروش بر اساس تحلیل‌های انجام شده.
        
        Args:
            df: دیتافریم حاوی داده‌های قیمت و اندیکاتورها
            trend: روند تشخیص داده شده
            patterns: الگوهای قیمتی شناسایی شده
            
        Returns:
            Dict[str, Any]: سیگنال خرید/فروش
        """
        # بررسی RSI
        rsi = df.iloc[-1].get('rsi', 50)
        
        # بررسی MACD
        macd = df.iloc[-1].get('macd', 0)
        macd_signal = df.iloc[-1].get('macd_signal', 0)
        macd_hist = df.iloc[-1].get('macd_hist', 0)
        
        # بررسی میانگین متحرک
        ma20 = df.iloc[-1].get('ma20', 0)
        ma50 = df.iloc[-1].get('ma50', 0)
        current_price = df.iloc[-1]['close']
        
        # امتیازدهی به سیگنال‌ها
        buy_score = 0
        sell_score = 0
        
        # امتیاز RSI
        if rsi < 30:
            buy_score += 2
        elif rsi < 40:
            buy_score += 1
        elif rsi > 70:
            sell_score += 2
        elif rsi > 60:
            sell_score += 1
        
        # امتیاز MACD
        if macd > macd_signal and macd_hist > 0:
            buy_score += 1
        elif macd < macd_signal and macd_hist < 0:
            sell_score += 1
        
        # امتیاز میانگین متحرک
        if current_price > ma20 and ma20 > ma50:
            buy_score += 1
        elif current_price < ma20 and ma20 < ma50:
            sell_score += 1
        
        # امتیاز روند
        if trend == 'صعودی':
            buy_score += 1
        elif trend == 'نزولی':
            sell_score += 1
        elif trend == 'اشباع خرید':
            sell_score += 1
        elif trend == 'اشباع فروش':
            buy_score += 1
        
        # امتیاز الگوها
        for pattern in patterns:
            if pattern['type'] == 'دابل تاپ':
                sell_score += 1
            elif pattern['type'] == 'دابل باتم':
                buy_score += 1
        
        # تعیین سیگنال نهایی
        signal_type = 'خنثی'
        strength = 'ضعیف'
        
        if buy_score >= 3 and buy_score > sell_score:
            signal_type = 'خرید'
            if buy_score >= 5:
                strength = 'قوی'
            else:
                strength = 'متوسط'
        elif sell_score >= 3 and sell_score > buy_score:
            signal_type = 'فروش'
            if sell_score >= 5:
                strength = 'قوی'
            else:
                strength = 'متوسط'
        
        return {
            'type': signal_type,
            'strength': strength,
            'buy_score': buy_score,
            'sell_score': sell_score,
            'timestamp': get_current_datetime().isoformat()
        }
    
    def get_price_alerts(self, user_id: int) -> List[Dict[str, Any]]:
        """
        دریافت هشدارهای قیمتی برای کاربر.
        
        Args:
            user_id: شناسه کاربر
            
        Returns:
            List[Dict[str, Any]]: لیست هشدارهای فعال
        """
        try:
            # پیاده‌سازی این تابع بستگی به ساختار دیتابیس شما دارد
            # می‌توانید آن را با توجه به نیازهای خود تغییر دهید
            pass
        except Exception as e:
            logger.error(f"خطا در دریافت هشدارهای قیمتی برای کاربر {user_id}: {str(e)}")
            return []
    
    def set_price_alert(self, user_id: int, symbol: str, price: float, alert_type: str) -> Dict[str, Any]:
        """
        تنظیم هشدار قیمتی جدید.
        
        Args:
            user_id: شناسه کاربر
            symbol: نماد ارز
            price: قیمت هشدار
            alert_type: نوع هشدار ('بالاتر از', 'پایین‌تر از')
            
        Returns:
            Dict[str, Any]: نتیجه تنظیم هشدار
        """
        try:
            # پیاده‌سازی این تابع بستگی به ساختار دیتابیس شما دارد
            # می‌توانید آن را با توجه به نیازهای خود تغییر دهید
            pass
        except Exception as e:
            logger.error(f"خطا در تنظیم هشدار قیمتی برای کاربر {user_id}: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def remove_price_alert(self, alert_id: int) -> Dict[str, Any]:
        """
        حذف هشدار قیمتی.
        
        Args:
            alert_id: شناسه هشدار
            
        Returns:
            Dict[str, Any]: نتیجه حذف هشدار
        """
        try:
            # پیاده‌سازی این تابع بستگی به ساختار دیتابیس شما دارد
            # می‌توانید آن را با توجه به نیازهای خود تغییر دهید
            pass
        except Exception as e:
            logger.error(f"خطا در حذف هشدار قیمتی {alert_id}: {str(e)}")
            return {'status': 'error', 'message': str(e)}


class StrategyManager:
    """
    مدیریت استراتژی‌های معاملاتی.
    
    این کلاس استراتژی‌های مختلف معاملاتی را مدیریت می‌کند و
    امکان اجرای آن‌ها را فراهم می‌کند.
    """
    
    def __init__(self, config: Config, technical_analysis: TechnicalAnalysis):
        """
        مقداردهی اولیه مدیریت استراتژی.
        
        Args:
            config (Config): تنظیمات برنامه
            technical_analysis (TechnicalAnalysis): آبجکت تحلیل تکنیکال
        """
        self.config = config
        self.ta = technical_analysis
        
        # لیست استراتژی‌های فعال
        self.strategies = {
            'ma_crossover': self.ma_crossover_strategy,
            'rsi_oversold': self.rsi_oversold_strategy,
            'macd_signal': self.macd_signal_strategy,
            'bb_touch': self.bb_touch_strategy
        }
        
        logger.info("مدیریت استراتژی با موفقیت مقداردهی شد")
    
    def get_available_strategies(self) -> Dict[str, str]:
        """
        دریافت لیست استراتژی‌های موجود.
        
        Returns:
            Dict[str, str]: دیکشنری استراتژی‌ها (کلید: نام، مقدار: توضیحات)
        """
        return {
            'ma_crossover': 'استراتژی عبور میانگین متحرک',
            'rsi_oversold': 'استراتژی RSI اشباع فروش',
            'macd_signal': 'استراتژی سیگنال MACD',
            'bb_touch': 'استراتژی تماس باندهای بولینگر'
        }
    
    def execute_strategy(self, strategy_name: str, symbol: str, timeframe: str = '1h') -> Dict[str, Any]:
        """
        اجرای یک استراتژی مشخص.
        
        Args:
            strategy_name: نام استراتژی
            symbol: نماد ارز
            timeframe: بازه زمانی
            
        Returns:
            Dict[str, Any]: نتیجه اجرای استراتژی
        """
        try:
            if strategy_name not in self.strategies:
                return {'status': 'error', 'message': f"استراتژی {strategy_name} وجود ندارد"}
            
            # دریافت داده‌های تاریخی
            historical_data = self.ta.get_historical_data(symbol, timeframe, 100)
            if not historical_data:
                return {'status': 'error', 'message': 'داده‌های تاریخی دریافت نشد'}
            
            # تبدیل به دیتافریم
            df = pd.DataFrame(historical_data)
            
            # محاسبه اندیکاتورها
            df = self.ta.calculate_indicators(df)
            
            # اجرای استراتژی
            strategy_func = self.strategies[strategy_name]
            result = strategy_func(df, symbol, timeframe)
            
            return result
            
        except Exception as e:
            logger.error(f"خطا در اجرای استراتژی {strategy_name} برای {symbol}: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def ma_crossover_strategy(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Dict[str, Any]:
        """
        استراتژی عبور میانگین متحرک.
        
        Args:
            df: دیتافریم حاوی داده‌های قیمت و اندیکاتورها
            symbol: نماد ارز
            timeframe: بازه زمانی
            
        Returns:
            Dict[str, Any]: نتیجه اجرای استراتژی
        """
        try:
            # بررسی عبور میانگین متحرک‌ها از یکدیگر
            if 'ma20' not in df.columns or 'ma50' not in df.columns:
                return {'status': 'error', 'message': 'میانگین متحرک محاسبه نشده است'}
            
            # بررسی عبور از بالا به پایین
            golden_cross = False
            death_cross = False
            
            if df['ma20'].iloc[-2] < df['ma50'].iloc[-2] and df['ma20'].iloc[-1] >= df['ma50'].iloc[-1]:
                golden_cross = True
            elif df['ma20'].iloc[-2] > df['ma50'].iloc[-2] and df['ma20'].iloc[-1] <= df['ma50'].iloc[-1]:
                death_cross = True
            
            # تولید سیگنال
            if golden_cross:
                signal = 'خرید'
                message = f"عبور صعودی میانگین متحرک 20 از میانگین متحرک 50 برای {symbol}"
            elif death_cross:
                signal = 'فروش'
                message = f"عبور نزولی میانگین متحرک 20 از میانگین متحرک 50 برای {symbol}"
            else:
                signal = 'خنثی'
                message = f"بدون عبور میانگین متحرک برای {symbol}"
            
            return {
                'status': 'success',
                'strategy': 'ma_crossover',
                'symbol': symbol,
                'timeframe': timeframe,
                'signal': signal,
                'message': message,
                'timestamp': get_current_datetime().isoformat()
            }
            
        except Exception as e:
            logger.error(f"خطا در اجرای استراتژی ma_crossover برای {symbol}: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def rsi_oversold_strategy(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Dict[str, Any]:
        """
        استراتژی RSI اشباع فروش.
        
        Args:
            df: دیتافریم حاوی داده‌های قیمت و اندیکاتورها
            symbol: نماد ارز
            timeframe: بازه زمانی
            
        Returns:
            Dict[str, Any]: نتیجه اجرای استراتژی
        """
        try:
            # بررسی RSI
            if 'rsi' not in df.columns:
                return {'status': 'error', 'message': 'RSI محاسبه نشده است'}
            
            # دریافت مقادیر RSI
            rsi_values = df['rsi'].tail(5)
            
            # بررسی اشباع خرید و فروش
            oversold = False
            overbought = False
            
            for i in range(len(rsi_values) - 1):
                if rsi_values.iloc[i] < 30 and rsi_values.iloc[i+1] >= 30:
                    oversold = True
                    break
                elif rsi_values.iloc[i] > 70 and rsi_values.iloc[i+1] <= 70:
                    overbought = True
                    break
            
            # تولید سیگنال
            if oversold:
                signal = 'خرید'
                message = f"خروج RSI از منطقه اشباع فروش برای {symbol}"
            elif overbought:
                signal = 'فروش'
                message = f"خروج RSI از منطقه اشباع خرید برای {symbol}"
            else:
                signal = 'خنثی'
                message = f"RSI در منطقه خنثی برای {symbol}"
            
            return {
                'status': 'success',
                'strategy': 'rsi_oversold',
                'symbol': symbol,
                'timeframe': timeframe,
                'signal': signal,
                'message': message,
                'current_rsi': rsi_values.iloc[-1],
                'timestamp': get_current_datetime().isoformat()
            }
            
        except Exception as e:
            logger.error(f"خطا در اجرای استراتژی rsi_oversold برای {symbol}: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def macd_signal_strategy(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Dict[str, Any]:
        """
        استراتژی سیگنال MACD.
        
        Args:
            df: دیتافریم حاوی داده‌های قیمت و اندیکاتورها
            symbol: نماد ارز
            timeframe: بازه زمانی
            
        Returns:
            Dict[str, Any]: نتیجه اجرای استراتژی
        """
        try:
            # بررسی MACD
            required_columns = ['macd', 'macd_signal', 'macd_hist']
            for col in required_columns:
                if col not in df.columns:
                    return {'status': 'error', 'message': f"{col} محاسبه نشده است"}
            
            # دریافت مقادیر MACD
            macd_values = df['macd'].tail(3)
            signal_values = df['macd_signal'].tail(3)
            hist_values = df['macd_hist'].tail(3)
            
            # بررسی عبور MACD از خط سیگنال
            bullish_cross = False
            bearish_cross = False
            
            if hist_values.iloc[-3] < 0 and hist_values.iloc[-2] < 0 and hist_values.iloc[-1] > 0:
                bullish_cross = True
            elif hist_values.iloc[-3] > 0 and hist_values.iloc[-2] > 0 and hist_values.iloc[-1] < 0:
                bearish_cross = True
            
            # تولید سیگنال
            if bullish_cross:
                signal = 'خرید'
                message = f"عبور صعودی MACD از خط سیگنال برای {symbol}"
            elif bearish_cross:
                signal = 'فروش'
                message = f"عبور نزولی MACD از خط سیگنال برای {symbol}"
            else:
                signal = 'خنثی'
                message = f"بدون عبور MACD از خط سیگنال برای {symbol}"
            
            return {
                'status': 'success',
                'strategy': 'macd_signal',
                'symbol': symbol,
                'timeframe': timeframe,
                'signal': signal,
                'message': message,
                'current_macd': macd_values.iloc[-1],
                'current_signal': signal_values.iloc[-1],
                'current_hist': hist_values.iloc[-1],
                'timestamp': get_current_datetime().isoformat()
            }
            
        except Exception as e:
            logger.error(f"خطا در اجرای استراتژی macd_signal برای {symbol}: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def bb_touch_strategy(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Dict[str, Any]:
        """
        استراتژی تماس باندهای بولینگر.
        
        Args:
            df: دیتافریم حاوی داده‌های قیمت و اندیکاتورها
            symbol: نماد ارز
            timeframe: بازه زمانی
            
        Returns:
            Dict[str, Any]: نتیجه اجرای استراتژی
        """
        try:
            # بررسی باندهای بولینگر
            required_columns = ['bb_upper', 'bb_middle', 'bb_lower']
            for col in required_columns:
                if col not in df.columns:
                    return {'status': 'error', 'message': f"{col} محاسبه نشده است"}
            
            # دریافت مقادیر باندهای بولینگر
            price_values = df['close'].tail(5)
            upper_values = df['bb_upper'].tail(5)
            lower_values = df['bb_lower'].tail(5)
            
            # بررسی تماس با باندها
            upper_touch = False
            lower_touch = False
            
            for i in range(len(price_values) - 1):
                if price_values.iloc[i] >= upper_values.iloc[i] and price_values.iloc[i+1] < upper_values.iloc[i+1]:
                    upper_touch = True
                    break
                elif price_values.iloc[i] <= lower_values.iloc[i] and price_values.iloc[i+1] > lower_values.iloc[i+1]:
                    lower_touch = True
                    break
            
            # تولید سیگنال
            if upper_touch:
                signal = 'فروش'
                message = f"تماس با باند بالایی بولینگر برای {symbol}"
            elif lower_touch:
                signal = 'خرید'
                message = f"تماس با باند پایینی بولینگر برای {symbol}"
            else:
                signal = 'خنثی'
                message = f"بدون تماس با باندهای بولینگر برای {symbol}"
            
            return {
                'status': 'success',
                'strategy': 'bb_touch',
                'symbol': symbol,
                'timeframe': timeframe,
                'signal': signal,
                'message': message,
                'current_price': price_values.iloc[-1],
                'current_upper': upper_values.iloc[-1],
                'current_lower': lower_values.iloc[-1],
                'timestamp': get_current_datetime().isoformat()
            }
            
        except Exception as e:
            logger.error(f"خطا در اجرای استراتژی bb_touch برای {symbol}: {str(e)}")
            return {'status': 'error', 'message': str(e)}