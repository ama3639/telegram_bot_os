#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول مدیریت منطقه زمانی.

این ماژول برای حل مشکلات مربوط به منطقه زمانی و استانداردسازی تاریخ و زمان
در کل برنامه طراحی شده است.

تاریخ ایجاد: ۱۴۰۴/۰۱/۰۷
"""


from datetime import timezone, timedelta
import logging
import time
import datetime
# from utils.timezone_utils import get_current_datetime
import pytz
import platform
from typing import Optional, Union, Tuple, Dict, Any
import os

logger = logging.getLogger(__name__)

# منطقه زمانی پیش‌فرض (تهران)
DEFAULT_TIMEZONE = 'Asia/Tehran'

# منطقه زمانی تنظیم شده
current_timezone = DEFAULT_TIMEZONE

def setup_timezone(timezone: str = DEFAULT_TIMEZONE) -> None:
    """
    تنظیم منطقه زمانی برنامه.
    
    پارامترها:
        timezone: منطقه زمانی (مثلاً 'Asia/Tehran')
    
    استثناها:
        ValueError: اگر منطقه زمانی نامعتبر باشد
    """
    global current_timezone
    
    # بررسی اعتبار منطقه زمانی
    try:
        tz = pytz.timezone(timezone)
        current_timezone = timezone
        logger.info(f"منطقه زمانی به '{timezone}' تنظیم شد.")
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(f"منطقه زمانی '{timezone}' نامعتبر است. استفاده از پیش‌فرض: {DEFAULT_TIMEZONE}")
        current_timezone = DEFAULT_TIMEZONE
        raise ValueError(f"منطقه زمانی '{timezone}' نامعتبر است.")
 
def get_current_timezone() -> str:
    """
    دریافت منطقه زمانی فعلی.
    
    بازگشت:
        str: منطقه زمانی فعلی
    """
    return current_timezone

def localize_datetime(dt: Optional[datetime.datetime] = None) -> datetime.datetime:
    """
    اضافه کردن اطلاعات منطقه زمانی به یک شیء datetime.
    
    پارامترها:
        dt: شیء datetime (اگر None باشد، زمان فعلی استفاده می‌شود)
        
    بازگشت:
        datetime.datetime: شیء datetime با منطقه زمانی
    """
    if dt is None:
        # اگر زمان ورودی None باشد، زمان فعلی را استفاده می‌کنیم
        dt = datetime.get_current_datetime()
    
    # اگر زمان دارای منطقه زمانی است، آن را به منطقه زمانی فعلی تبدیل می‌کنیم
    if dt.tzinfo is not None:
        tz = pytz.timezone(current_timezone)
        return dt.astimezone(tz)
    
    # اگر زمان بدون منطقه زمانی است، منطقه زمانی فعلی را اضافه می‌کنیم
    tz = pytz.timezone(current_timezone)
    return tz.localize(dt)

def now() -> datetime.datetime:
    """
    دریافت زمان فعلی با منطقه زمانی.
    
    بازگشت:
        datetime.datetime: زمان فعلی با منطقه زمانی
    """
    return localize_datetime(datetime.get_current_datetime())

def get_current_datetime() -> datetime.datetime:
    """
    دریافت زمان فعلی با منطقه زمانی.
    
    بازگشت:
        datetime.datetime: زمان فعلی با منطقه زمانی
    """
    return now()

def today() -> datetime.date:
    """
    دریافت تاریخ امروز.
    
    بازگشت:
        datetime.date: تاریخ امروز
    """
    return now().date()

def format_datetime(dt: Optional[datetime.datetime] = None, 
                   format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    قالب‌بندی یک شیء datetime به رشته.
    
    پارامترها:
        dt: شیء datetime (اگر None باشد، زمان فعلی استفاده می‌شود)
        format_str: قالب تاریخ و زمان
        
    بازگشت:
        str: رشته قالب‌بندی شده
    """
    if dt is None:
        dt = now()
    else:
        dt = localize_datetime(dt)
    
    return dt.strftime(format_str)

def parse_datetime(date_str: str, format_str: str = '%Y-%m-%d %H:%M:%S') -> datetime.datetime:
    """
    تبدیل یک رشته تاریخ و زمان به شیء datetime.
    
    پارامترها:
        date_str: رشته تاریخ و زمان
        format_str: قالب تاریخ و زمان
        
    بازگشت:
        datetime.datetime: شیء datetime با منطقه زمانی
        
    استثناها:
        ValueError: اگر رشته با قالب مطابقت نداشته باشد
    """
    dt = datetime.datetime.strptime(date_str, format_str)
    return localize_datetime(dt)

def parse_iso_datetime(date_str: str) -> datetime.datetime:
    """
    تبدیل یک رشته تاریخ و زمان ISO 8601 به شیء datetime.
    
    پارامترها:
        date_str: رشته تاریخ و زمان ISO 8601
        
    بازگشت:
        datetime.datetime: شیء datetime با منطقه زمانی
        
    استثناها:
        ValueError: اگر رشته با قالب مطابقت نداشته باشد
    """
    try:
        dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return localize_datetime(dt)
    except ValueError:
        # برای پشتیبانی از نسخه‌های قدیمی‌تر پایتون
        from dateutil import parser
        dt = parser.parse(date_str)
        return localize_datetime(dt)

def to_timestamp(dt: Optional[datetime.datetime] = None) -> float:
    """
    تبدیل یک شیء datetime به timestamp.
    
    پارامترها:
        dt: شیء datetime (اگر None باشد، زمان فعلی استفاده می‌شود)
        
    بازگشت:
        float: timestamp
    """
    if dt is None:
        dt = now()
    else:
        dt = localize_datetime(dt)
    
    return dt.timestamp()

def from_timestamp(timestamp: float) -> datetime.datetime:
    """
    تبدیل یک timestamp به شیء datetime.
    
    پارامترها:
        timestamp: timestamp
        
    بازگشت:
        datetime.datetime: شیء datetime با منطقه زمانی
    """
    dt = datetime.datetime.fromtimestamp(timestamp)
    return localize_datetime(dt)

def format_date_for_humans(dt: Optional[datetime.datetime] = None, 
                         locale: str = 'fa') -> str:
    """
    قالب‌بندی تاریخ به صورت خوانا برای انسان.
    
    پارامترها:
        dt: شیء datetime (اگر None باشد، زمان فعلی استفاده می‌شود)
        locale: زبان (fa/en)
        
    بازگشت:
        str: رشته قالب‌بندی شده
    """
    if dt is None:
        dt = now()
    else:
        dt = localize_datetime(dt)
    
    # فاصله زمانی از اکنون
    now_dt = now()
    delta = now_dt - dt
    
    # قالب‌بندی بر اساس زبان
    if locale == 'fa':
        # فارسی
        if delta.days == 0:
            # امروز
            if delta.seconds < 60:
                return "همین الان"
            elif delta.seconds < 3600:
                minutes = delta.seconds // 60
                return f"{minutes} دقیقه پیش"
            else:
                hours = delta.seconds // 3600
                return f"{hours} ساعت پیش"
        elif delta.days == 1:
            # دیروز
            return f"دیروز ساعت {dt.strftime('%H:%M')}"
        elif delta.days < 7:
            # این هفته
            return f"{delta.days} روز پیش"
        elif delta.days < 30:
            # این ماه
            weeks = delta.days // 7
            return f"{weeks} هفته پیش"
        elif delta.days < 365:
            # امسال
            months = delta.days // 30
            return f"{months} ماه پیش"
        else:
            # سال‌های گذشته
            return dt.strftime('%Y/%m/%d')
    else:
        # انگلیسی
        if delta.days == 0:
            # Today
            if delta.seconds < 60:
                return "Just now"
            elif delta.seconds < 3600:
                minutes = delta.seconds // 60
                return f"{minutes} minutes ago"
            else:
                hours = delta.seconds // 3600
                return f"{hours} hours ago"
        elif delta.days == 1:
            # Yesterday
            return f"Yesterday at {dt.strftime('%H:%M')}"
        elif delta.days < 7:
            # This week
            return f"{delta.days} days ago"
        elif delta.days < 30:
            # This month
            weeks = delta.days // 7
            return f"{weeks} weeks ago"
        elif delta.days < 365:
            # This year
            months = delta.days // 30
            return f"{months} months ago"
        else:
            # Past years
            return dt.strftime('%Y-%m-%d')

def jalali_to_gregorian(jy: int, jm: int, jd: int) -> Tuple[int, int, int]:
    """
    تبدیل تاریخ جلالی (شمسی) به میلادی.
    
    پارامترها:
        jy: سال جلالی
        jm: ماه جلالی
        jd: روز جلالی
        
    بازگشت:
        Tuple[int, int, int]: (سال، ماه، روز) میلادی
    """
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    
    gy = 400 * (days // 146097)
    days %= 146097
    
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        
        if days >= 365:
            days += 1
    
    gy += 4 * (days // 1461)
    days %= 1461
    
    if days > 365:
        gy += ((days - 1) // 365)
        days = (days - 1) % 365
    
    gd = days + 1
    
    if ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)):
        kab = 29
    else:
        kab = 28
    
    sal_a = [0, 31, kab, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    
    while gm < 13 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1
    
    return (gy, gm, gd)

def gregorian_to_jalali(gy: int, gm: int, gd: int) -> Tuple[int, int, int]:
    """
    تبدیل تاریخ میلادی به جلالی (شمسی).
    
    پارامترها:
        gy: سال میلادی
        gm: ماه میلادی
        gd: روز میلادی
        
    بازگشت:
        Tuple[int, int, int]: (سال، ماه، روز) جلالی
    """
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    
    if (gy > 1600):
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    
    gy2 = (gm > 2) and (gy + 1) or gy
    days = (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    
    jm = (days < 186) and 1 + (days // 31) or 7 + ((days - 186) // 30)
    jd = 1 + ((days < 186) and (days % 31) or ((days - 186) % 30))
    
    return (jy, jm, jd)

def format_jalali_date(dt: Optional[datetime.datetime] = None, 
                      format_str: str = '%Y/%m/%d') -> str:
    """
    قالب‌بندی یک شیء datetime به تاریخ جلالی (شمسی).
    
    پارامترها:
        dt: شیء datetime (اگر None باشد، زمان فعلی استفاده می‌شود)
        format_str: قالب تاریخ
        
    بازگشت:
        str: رشته قالب‌بندی شده به تاریخ جلالی
    """
    if dt is None:
        dt = now()
    else:
        dt = localize_datetime(dt)
    
    # تبدیل به جلالی
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    
    # جایگزینی فرمت‌های استاندارد
    result = format_str
    result = result.replace('%Y', f'{jy:04d}')
    result = result.replace('%y', f'{jy % 100:02d}')
    result = result.replace('%m', f'{jm:02d}')
    result = result.replace('%d', f'{jd:02d}')
    
    # اضافه کردن زمان اگر در قالب وجود دارد
    result = result.replace('%H', f'{dt.hour:02d}')
    result = result.replace('%M', f'{dt.minute:02d}')
    result = result.replace('%S', f'{dt.second:02d}')
    
    return result

def parse_jalali_date(date_str: str, format_str: str = '%Y/%m/%d') -> datetime.datetime:
    """
    تبدیل یک رشته تاریخ جلالی (شمسی) به شیء datetime.
    
    پارامترها:
        date_str: رشته تاریخ جلالی
        format_str: قالب تاریخ
        
    بازگشت:
        datetime.datetime: شیء datetime با منطقه زمانی
        
    استثناها:
        ValueError: اگر رشته با قالب مطابقت نداشته باشد
    """
    # پارس کردن تاریخ جلالی (پیاده‌سازی ساده)
    if format_str == '%Y/%m/%d':
        parts = date_str.split('/')
        if len(parts) != 3:
            raise ValueError("قالب تاریخ نامعتبر است. باید به صورت YYYY/MM/DD باشد.")
        
        try:
            jy = int(parts[0])
            jm = int(parts[1])
            jd = int(parts[2])
        except ValueError:
            raise ValueError("اجزای تاریخ باید عدد باشند.")
        
        # تبدیل به میلادی
        gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
        
        # ساخت شیء datetime
        dt = datetime.datetime(gy, gm, gd)
        return localize_datetime(dt)
    else:
        raise ValueError("قالب تاریخ پشتیبانی نمی‌شود.")

def get_utc_offset() -> str:
    """
    دریافت اختلاف زمانی با UTC.
    
    بازگشت:
        str: اختلاف زمانی (مثلاً '+03:30')
    """
    tz = pytz.timezone(current_timezone)
    offset = tz.utcoffset(datetime.get_current_datetime())
    
    # تبدیل به ساعت و دقیقه
    total_seconds = int(offset.total_seconds())
    hours, remainder = divmod(abs(total_seconds), 3600)
    minutes = remainder // 60
    
    # قالب‌بندی
    sign = '+' if total_seconds >= 0 else '-'
    return f"{sign}{hours:02d}:{minutes:02d}"

def fix_windows_timezone() -> None:
    """
    رفع مشکل منطقه زمانی در ویندوز.
    """
    if platform.system() == 'Windows':
        # در ویندوز، منطقه زمانی ایران به درستی پشتیبانی نمی‌شود
        # بنابراین باید به صورت دستی اصلاح شود
        if current_timezone == 'Asia/Tehran':
            os.environ['TZ'] = 'Asia/Tehran'
            logger.info("منطقه زمانی تهران در ویندوز اصلاح شد.")

def datetime_to_dict(dt: datetime.datetime) -> Dict[str, Any]:
    """
    تبدیل یک شیء datetime به دیکشنری.
    
    پارامترها:
        dt: شیء datetime
        
    بازگشت:
        Dict[str, Any]: دیکشنری حاوی اجزای تاریخ و زمان
    """
    dt = localize_datetime(dt)
    
    # تبدیل به جلالی
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    
    return {
        'gregorian': {
            'year': dt.year,
            'month': dt.month,
            'day': dt.day,
            'hour': dt.hour,
            'minute': dt.minute,
            'second': dt.second,
            'microsecond': dt.microsecond,
            'weekday': dt.weekday(),
            'weekday_name': dt.strftime('%A'),
            'month_name': dt.strftime('%B'),
            'iso': dt.isoformat(),
            'formatted': dt.strftime('%Y-%m-%d %H:%M:%S')
        },
        'jalali': {
            'year': jy,
            'month': jm,
            'day': jd,
            'formatted': format_jalali_date(dt)
        },
        'timestamp': dt.timestamp(),
        'timezone': {
            'name': current_timezone,
            'offset': get_utc_offset()
        }
    }

def get_next_weekday(weekday: int, from_date: Optional[datetime.date] = None) -> datetime.date:
    """
    دریافت تاریخ اولین روز هفته آینده.
    
    پارامترها:
        weekday: روز هفته (0=دوشنبه، 6=یکشنبه)
        from_date: تاریخ شروع (اگر None باشد، امروز استفاده می‌شود)
        
    بازگشت:
        datetime.date: تاریخ روز هفته آینده
    """
    if from_date is None:
        from_date = today()
    
    days_ahead = weekday - from_date.weekday()
    if days_ahead <= 0:  # روز هفته گذشته، برو به هفته آینده
        days_ahead += 7
    
    return from_date + timedelta(days=days_ahead)

def date_range(start_date: datetime.date, end_date: datetime.date) -> list:
    """
    تولید لیستی از تاریخ‌ها در یک بازه.
    
    پارامترها:
        start_date: تاریخ شروع
        end_date: تاریخ پایان
        
    بازگشت:
        list: لیست تاریخ‌ها
    """
    days = (end_date - start_date).days + 1
    return [start_date + timedelta(days=i) for i in range(days)]

# ایجاد نسخه‌های خود از توابع زمان پایتون برای استفاده در کل پروژه
def datetime_now() -> datetime.datetime:
    """
    نسخه ایمن از get_current_datetime() با منطقه زمانی.
    
    بازگشت:
        datetime.datetime: زمان فعلی با منطقه زمانی
    """
    return now()

def datetime_utcnow() -> datetime.datetime:
    """
    نسخه ایمن از datetime.utcnow() با منطقه زمانی.
    
    بازگشت:
        datetime.datetime: زمان UTC فعلی با منطقه زمانی
    """
    return datetime.datetime.now(pytz.UTC)

def time_time() -> float:
    """
    نسخه ایمن از time.time().
    
    بازگشت:
        float: timestamp فعلی
    """
    return time.time()

def convert_timezone(dt: Optional[datetime.datetime] = None, 
                     target_timezone: str = DEFAULT_TIMEZONE) -> datetime.datetime:
    """
    تبدیل یک شیء datetime به منطقه زمانی دلخواه.
    
    پارامترها:
        dt: شیء datetime (اگر None باشد، زمان فعلی استفاده می‌شود)
        target_timezone: منطقه زمانی مقصد (پیش‌فرض: منطقه زمانی پیش‌فرض)
        
    بازگشت:
        datetime.datetime: شیء datetime با منطقه زمانی جدید
        
    استثناها:
        ValueError: اگر منطقه زمانی نامعتبر باشد
    """
    if dt is None:
        dt = now()
    
    try:
        target_tz = pytz.timezone(target_timezone)
        # اگر زمان دارای منطقه زمانی نیست، ابتدا به منطقه زمانی فعلی اضافه می‌کنیم
        if dt.tzinfo is None:
            dt = localize_datetime(dt)
        
        # تبدیل به منطقه زمانی مقصد
        return dt.astimezone(target_tz)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(f"منطقه زمانی '{target_timezone}' نامعتبر است.")
        raise ValueError(f"منطقه زمانی '{target_timezone}' نامعتبر است.")

def convert_to_user_timezone(dt: Optional[datetime.datetime] = None, 
                           user_timezone: Optional[str] = None) -> datetime.datetime:
    """
    تبدیل یک شیء datetime به منطقه زمانی کاربر.
    
    پارامترها:
        dt: شیء datetime (اگر None باشد، زمان فعلی استفاده می‌شود)
        user_timezone: منطقه زمانی کاربر (اگر None باشد، از منطقه زمانی سیستم استفاده می‌شود)
        
    بازگشت:
        datetime.datetime: شیء datetime با منطقه زمانی کاربر
    """
    if dt is None:
        dt = now()
    
    # اگر منطقه زمانی کاربر مشخص نشده، از منطقه زمانی سیستم استفاده می‌کنیم
    if user_timezone is None:
        user_timezone = get_user_timezone()
    
    # تبدیل به منطقه زمانی کاربر
    return convert_timezone(dt, user_timezone)

def parse_datetime_string(date_str: str, 
                          format_str: Optional[str] = None, 
                          timezone: Optional[str] = None) -> datetime.datetime:
    """
    تبدیل یک رشته تاریخ و زمان به شیء datetime با پشتیبانی از فرمت‌های مختلف.
    
    پارامترها:
        date_str: رشته تاریخ و زمان
        format_str: قالب تاریخ و زمان (اختیاری)
        timezone: منطقه زمانی (اختیاری)
        
    بازگشت:
        datetime.datetime: شیء datetime با منطقه زمانی
        
    استثناها:
        ValueError: اگر رشته با قالب مطابقت نداشته باشد
    """
    # تلاش برای پارس کردن با فرمت مشخص شده
    if format_str:
        return parse_datetime(date_str, format_str)
    
    # تلاش برای پارس کردن با فرمت‌های مختلف
    parse_formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y/%m/%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%d/%m/%Y %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S%z'
    ]
    
    for fmt in parse_formats:
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            dt = localize_datetime(dt)
            
            # اگر منطقه زمانی مشخص شده، تبدیل کن
            if timezone:
                dt = convert_timezone(dt, timezone)
            
            return dt
        except ValueError:
            continue
    
    # اگر هیچ فرمتی مچ نشد، تلاش به پارس با ISO 8601
    try:
        return parse_iso_datetime(date_str)
    except ValueError:
        # اگر باز هم موفق نشد
        logger.error(f"عدم موفقیت در پارس رشته تاریخ: {date_str}")
        raise ValueError(f"فرمت تاریخ نامعتبر: {date_str}")

def get_timezone_difference(timezone1: Optional[str] = None, 
                            timezone2: Optional[str] = None) -> str:
    """
    محاسبه اختلاف زمانی بین دو منطقه زمانی.
    
    پارامترها:
        timezone1: منطقه زمانی اول (پیش‌فرض: منطقه زمانی فعلی)
        timezone2: منطقه زمانی دوم (پیش‌فرض: UTC)
        
    بازگشت:
        str: اختلاف زمانی (مثلاً '+03:30')
    """
    # استفاده از منطقه زمانی پیش‌فرض در صورت عدم تعیین
    if timezone1 is None:
        timezone1 = current_timezone
    
    if timezone2 is None:
        timezone2 = 'UTC'
    
    try:
        # محاسبه زمان فعلی در هر دو منطقه زمانی
        current_time = datetime.get_current_datetime()
        
        tz1 = pytz.timezone(timezone1)
        tz2 = pytz.timezone(timezone2)
        
        # محاسبه اختلاف زمانی
        offset1 = tz1.utcoffset(current_time)
        offset2 = tz2.utcoffset(current_time)
        
        difference = offset1 - offset2
        
        # تبدیل به ساعت و دقیقه
        total_seconds = int(difference.total_seconds())
        hours, remainder = divmod(abs(total_seconds), 3600)
        minutes = remainder // 60
        
        # قالب‌بندی
        sign = '+' if total_seconds >= 0 else '-'
        return f"{sign}{hours:02d}:{minutes:02d}"
    
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(f"یکی از منطقه‌های زمانی نامعتبر است: {timezone1}, {timezone2}")
        raise ValueError(f"منطقه زمانی نامعتبر: {timezone1} یا {timezone2}")

def get_user_timezone() -> str:
    """
    دریافت منطقه زمانی سیستم کاربر.
    
    بازگشت:
        str: منطقه زمانی سیستم
    """
    try:
        # تلاش برای دریافت منطقه زمانی از سیستم
        system_timezone = time.tzname[time.daylight]
        
        # تبدیل به فرمت استاندارد pytz
        timezone_mapping = {
            'Iran Standard Time': 'Asia/Tehran',
            'Tehran': 'Asia/Tehran',
            'IRST': 'Asia/Tehran',
            # می‌توانید نگاشت‌های بیشتری اضافه کنید
        }
        
        # جستجوی منطقه زمانی در نگاشت
        mapped_timezone = timezone_mapping.get(system_timezone, system_timezone)
        
        # بررسی اعتبار منطقه زمانی
        pytz.timezone(mapped_timezone)
        
        return mapped_timezone
    except Exception:
        # در صورت شکست، منطقه زمانی پیش‌فرض را برمی‌گرداند
        logger.warning("عدم موفقیت در دریافت منطقه زمانی سیستم. استفاده از پیش‌فرض.")
        return DEFAULT_TIMEZONE

def is_same_day(dt1: datetime.datetime, 
                dt2: Optional[datetime.datetime] = None, 
                timezone: Optional[str] = None) -> bool:
    """
    بررسی اینکه آیا دو تاریخ در یک روز هستند.
    
    پارامترها:
        dt1: تاریخ اول
        dt2: تاریخ دوم (اگر None باشد، از زمان فعلی استفاده می‌شود)
        timezone: منطقه زمانی برای مقایسه (اختیاری)
        
    بازگشت:
        bool: آیا دو تاریخ در یک روز هستند
    """
    # اگر dt2 مشخص نشده، از زمان فعلی استفاده می‌کنیم
    if dt2 is None:
        dt2 = now()
    
    # اگر منطقه زمانی مشخص شده، تبدیل می‌کنیم
    if timezone:
        dt1 = convert_timezone(dt1, timezone)
        dt2 = convert_timezone(dt2, timezone)
    else:
        # اطمینان از اینکه هر دو تاریخ در یک منطقه زمانی هستند
        dt1 = localize_datetime(dt1)
        dt2 = localize_datetime(dt2)
    
    # مقایسه سال، ماه و روز
    return (dt1.year == dt2.year and 
            dt1.month == dt2.month and 
            dt1.day == dt2.day)