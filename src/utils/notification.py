#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول سیستم اطلاع‌رسانی.

این ماژول مسئول ارسال اطلاعیه‌ها و هشدارها به کاربران و ادمین‌ها است.

تاریخ ایجاد: ۱۴۰۴/۰۱/۰۷
"""

import logging
from typing import Dict, List, Any, Optional, Union
import asyncio
from datetime import datetime
from src.utils.timezone_utils import get_current_datetime

from telegram import Bot, InlineKeyboardMarkup
from telegram.error import TelegramError

from src.utils.localization import get_message

logger = logging.getLogger(__name__)

async def send_message(bot: Bot, chat_id: Union[int, str], text: str, 
                     reply_markup: Optional[InlineKeyboardMarkup] = None,
                     parse_mode: str = 'HTML') -> bool:
    """
    ارسال پیام به کاربر.
    
    پارامترها:
        bot: نمونه ربات تلگرام
        chat_id: شناسه چت کاربر
        text: متن پیام
        reply_markup: دکمه‌های اینلاین (اختیاری)
        parse_mode: نوع پارس متن (HTML یا Markdown)
        
    بازگشت:
        bool: True در صورت موفقیت، False در غیر این صورت
    """
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        return True
        
    except TelegramError as e:
        logger.error(f"خطا در ارسال پیام به کاربر {chat_id}: {str(e)}")
        return False

async def send_admin_notification(bot: Bot, message: str, config: Dict[str, Any]) -> None:
    """
    ارسال اطلاعیه به تمام ادمین‌ها.
    
    پارامترها:
        bot: نمونه ربات تلگرام
        message: متن پیام
        config: تنظیمات برنامه
    """
    admin_ids = config.get('ADMIN_IDS', [])
    
    if not admin_ids:
        logger.warning("لیست ادمین‌ها خالی است. اطلاعیه ارسال نشد.")
        return
    
    admin_message = get_message('admin_notification').format(message=message)
    
    for admin_id in admin_ids:
        try:
            await send_message(bot, admin_id, admin_message)
            # تأخیر کوتاه برای جلوگیری از محدودیت API تلگرام
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"خطا در ارسال اطلاعیه به ادمین {admin_id}: {str(e)}")

async def send_bulk_message(bot: Bot, user_ids: List[int], text: str,
                          reply_markup: Optional[InlineKeyboardMarkup] = None,
                          parse_mode: str = 'HTML') -> Dict[str, int]:
    """
    ارسال پیام به تعداد زیادی از کاربران.
    
    پارامترها:
        bot: نمونه ربات تلگرام
        user_ids: لیست شناسه‌های کاربران
        text: متن پیام
        reply_markup: دکمه‌های اینلاین (اختیاری)
        parse_mode: نوع پارس متن (HTML یا Markdown)
        
    بازگشت:
        Dict[str, int]: آمار ارسال {'success': تعداد موفق, 'failed': تعداد ناموفق}
    """
    success_count = 0
    failed_count = 0
    
    for user_id in user_ids:
        try:
            await send_message(bot, user_id, text, reply_markup, parse_mode)
            success_count += 1
            
            # تأخیر برای جلوگیری از محدودیت API تلگرام
            await asyncio.sleep(0.05)
            
        except Exception as e:
            logger.error(f"خطا در ارسال پیام انبوه به کاربر {user_id}: {str(e)}")
            failed_count += 1
            
            # تأخیر بیشتر در صورت خطا
            await asyncio.sleep(0.1)
    
    return {
        'success': success_count,
        'failed': failed_count
    }

async def send_scheduled_message(bot: Bot, chat_id: Union[int, str], text: str, 
                               schedule_time: datetime,
                               reply_markup: Optional[InlineKeyboardMarkup] = None,
                               parse_mode: str = 'HTML') -> bool:
    """
    ارسال پیام زمان‌بندی شده به کاربر.
    
    پارامترها:
        bot: نمونه ربات تلگرام
        chat_id: شناسه چت کاربر
        text: متن پیام
        schedule_time: زمان ارسال پیام
        reply_markup: دکمه‌های اینلاین (اختیاری)
        parse_mode: نوع پارس متن (HTML یا Markdown)
        
    بازگشت:
        bool: True در صورت موفقیت، False در غیر این صورت
    """
    now = get_current_datetime()
    
    # محاسبه تأخیر ارسال
    if schedule_time > now:
        delay_seconds = (schedule_time - now).total_seconds()
        logger.info(f"پیام برای کاربر {chat_id} با تأخیر {delay_seconds:.2f} ثانیه ارسال خواهد شد.")
        
        # تأخیر تا زمان مشخص شده
        await asyncio.sleep(delay_seconds)
    
    return await send_message(bot, chat_id, text, reply_markup, parse_mode)

async def send_error_notification(bot: Bot, user_id: int, error_message: str) -> None:
    """
    ارسال اطلاعیه خطا به کاربر.
    
    پارامترها:
        bot: نمونه ربات تلگرام
        user_id: شناسه کاربر
        error_message: پیام خطا
    """
    error_text = get_message('error').format(message=error_message)
    await send_message(bot, user_id, error_text)

async def send_typing_action(bot: Bot, chat_id: Union[int, str], duration: float = 2.0) -> None:
    """
    ارسال وضعیت 'در حال تایپ' به چت.
    
    پارامترها:
        bot: نمونه ربات تلگرام
        chat_id: شناسه چت
        duration: مدت زمان نمایش وضعیت (ثانیه)
    """
    try:
        await bot.send_chat_action(chat_id=chat_id, action='typing')
        await asyncio.sleep(duration)
    except TelegramError as e:
        logger.error(f"خطا در ارسال وضعیت تایپ به چت {chat_id}: {str(e)}")

async def edit_message_text(bot: Bot, chat_id: Union[int, str], message_id: int, text: str,
                          reply_markup: Optional[InlineKeyboardMarkup] = None,
                          parse_mode: str = 'HTML') -> bool:
    """
    ویرایش متن یک پیام.
    
    پارامترها:
        bot: نمونه ربات تلگرام
        chat_id: شناسه چت
        message_id: شناسه پیام
        text: متن جدید
        reply_markup: دکمه‌های اینلاین جدید (اختیاری)
        parse_mode: نوع پارس متن (HTML یا Markdown)
        
    بازگشت:
        bool: True در صورت موفقیت، False در غیر این صورت
    """
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        return True
        
    except TelegramError as e:
        logger.error(f"خطا در ویرایش پیام {message_id} در چت {chat_id}: {str(e)}")
        return False

async def delete_message(bot: Bot, chat_id: Union[int, str], message_id: int) -> bool:
    """
    حذف یک پیام.
    
    پارامترها:
        bot: نمونه ربات تلگرام
        chat_id: شناسه چت
        message_id: شناسه پیام
        
    بازگشت:
        bool: True در صورت موفقیت، False در غیر این صورت
    """
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
        
    except TelegramError as e:
        logger.error(f"خطا در حذف پیام {message_id} از چت {chat_id}: {str(e)}")
        return False 
    
    
async def send_telegram_notification(
    chat_id: Union[int, str], 
    message: str, 
    bot: Optional[Bot] = None, 
    **kwargs
) -> bool:
    """
    ارسال نوتیفیکیشن تلگرام

    پارامترها:
        chat_id: شناسه چت
        message: متن پیام
        bot: نمونه ربات تلگرام (اختیاری)
        **kwargs: پارامترهای اضافی

    بازگشت:
        bool: وضعیت موفقیت ارسال
    """
    try:
        if bot is None:
            # در اینجا می‌توانید منطق ایجاد bot پیش‌فرض را اضافه کنید
            logger.warning("نمونه ربات تلگرام ارائه نشده است.")
            return False
        
        # استفاده از تابع send_message موجود در همین فایل
        asyncio.create_task(send_message(bot, chat_id, message))
        return True
    except Exception as e:
        logger.error(f"خطا در ارسال نوتیفیکیشن تلگرام: {str(e)}")
        return False

def send_email_notification(
    recipient: str, 
    subject: str, 
    body: str, 
    **kwargs
) -> bool:
    """
    ارسال ایمیل

    پارامترها:
        recipient: گیرنده ایمیل
        subject: موضوع ایمیل
        body: متن ایمیل
        **kwargs: پارامترهای اضافی

    بازگشت:
        bool: وضعیت موفقیت ارسال
    """
    try:
        logger.info(f"ارسال ایمیل به {recipient}")
        # TODO: پیاده‌سازی منطق ارسال ایمیل
        return True
    except Exception as e:
        logger.error(f"خطا در ارسال ایمیل: {str(e)}")
        return False

def register_for_notifications(
    user_id: Union[int, str], 
    notification_types: List[str], 
    **kwargs
) -> bool:
    """
    ثبت‌نام برای دریافت نوتیفیکیشن‌ها

    پارامترها:
        user_id: شناسه کاربر
        notification_types: انواع نوتیفیکیشن‌ها
        **kwargs: پارامترهای اضافی

    بازگشت:
        bool: وضعیت موفقیت ثبت‌نام
    """
    try:
        logger.info(f"ثبت‌نام {user_id} برای {notification_types}")
        # TODO: پیاده‌سازی منطق ثبت‌نام
        return True
    except Exception as e:
        logger.error(f"خطا در ثبت‌نام برای نوتیفیکیشن‌ها: {str(e)}")
        return False

def unregister_from_notifications(
    user_id: Union[int, str], 
    notification_types: Optional[List[str]] = None, 
    **kwargs
) -> bool:
    """
    لغو ثبت‌نام از نوتیفیکیشن‌ها

    پارامترها:
        user_id: شناسه کاربر
        notification_types: انواع نوتیفیکیشن‌ها (اختیاری)
        **kwargs: پارامترهای اضافی

    بازگشت:
        bool: وضعیت موفقیت لغو ثبت‌نام
    """
    try:
        logger.info(f"لغو ثبت‌نام {user_id} از نوتیفیکیشن‌ها")
        # TODO: پیاده‌سازی منطق لغو ثبت‌نام
        return True
    except Exception as e:
        logger.error(f"خطا در لغو ثبت‌نام از نوتیفیکیشن‌ها: {str(e)}")
        return False    


class NotificationManager:
    """
    مدیر سیستم اطلاع‌رسانی.
    
    این کلاس مسئول مدیریت ارسال انواع اطلاعیه‌ها و هشدارها به کاربران است.
    """
    
    def __init__(self, bot=None, config=None):
        """
        مقداردهی اولیه.
        
        پارامترها:
            bot: نمونه ربات تلگرام (اختیاری)
            config: تنظیمات برنامه (اختیاری)
        """
        self.bot = bot
        self.config = config
    
    async def send_message(self, chat_id: Union[int, str], text: str, 
                         reply_markup: Optional[InlineKeyboardMarkup] = None,
                         parse_mode: str = 'HTML') -> bool:
        """
        ارسال پیام به کاربر.
        
        پارامترها:
            chat_id: شناسه چت کاربر
            text: متن پیام
            reply_markup: دکمه‌های اینلاین (اختیاری)
            parse_mode: نوع پارس متن (HTML یا Markdown)
            
        بازگشت:
            bool: True در صورت موفقیت، False در غیر این صورت
        """
        if self.bot is None:
            logger.error("نمونه ربات تنظیم نشده است")
            return False
            
        return await send_message(self.bot, chat_id, text, reply_markup, parse_mode)
    
    async def send_admin_notification(self, message: str) -> None:
        """
        ارسال اطلاعیه به تمام ادمین‌ها.
        
        پارامترها:
            message: متن پیام
        """
        if self.bot is None or self.config is None:
            logger.error("نمونه ربات یا تنظیمات برنامه تنظیم نشده است")
            return
            
        await send_admin_notification(self.bot, message, self.config)
    
    async def send_bulk_message(self, user_ids: List[int], text: str,
                              reply_markup: Optional[InlineKeyboardMarkup] = None,
                              parse_mode: str = 'HTML') -> Dict[str, int]:
        """
        ارسال پیام به تعداد زیادی از کاربران.
        
        پارامترها:
            user_ids: لیست شناسه‌های کاربران
            text: متن پیام
            reply_markup: دکمه‌های اینلاین (اختیاری)
            parse_mode: نوع پارس متن (HTML یا Markdown)
            
        بازگشت:
            Dict[str, int]: آمار ارسال {'success': تعداد موفق, 'failed': تعداد ناموفق}
        """
        if self.bot is None:
            logger.error("نمونه ربات تنظیم نشده است")
            return {'success': 0, 'failed': len(user_ids)}
            
        return await send_bulk_message(self.bot, user_ids, text, reply_markup, parse_mode)
    
    async def send_scheduled_message(self, chat_id: Union[int, str], text: str, 
                                   schedule_time: datetime,
                                   reply_markup: Optional[InlineKeyboardMarkup] = None,
                                   parse_mode: str = 'HTML') -> bool:
        """
        ارسال پیام زمان‌بندی شده به کاربر.
        
        پارامترها:
            chat_id: شناسه چت کاربر
            text: متن پیام
            schedule_time: زمان ارسال پیام
            reply_markup: دکمه‌های اینلاین (اختیاری)
            parse_mode: نوع پارس متن (HTML یا Markdown)
            
        بازگشت:
            bool: True در صورت موفقیت، False در غیر این صورت
        """
        if self.bot is None:
            logger.error("نمونه ربات تنظیم نشده است")
            return False
            
        return await send_scheduled_message(self.bot, chat_id, text, schedule_time, reply_markup, parse_mode)
    
    async def send_error_notification(self, user_id: int, error_message: str) -> None:
        """
        ارسال اطلاعیه خطا به کاربر.
        
        پارامترها:
            user_id: شناسه کاربر
            error_message: پیام خطا
        """
        if self.bot is None:
            logger.error("نمونه ربات تنظیم نشده است")
            return
            
        await send_error_notification(self.bot, user_id, error_message)
    
    async def send_typing_action(self, chat_id: Union[int, str], duration: float = 2.0) -> None:
        """
        ارسال وضعیت 'در حال تایپ' به چت.
        
        پارامترها:
            chat_id: شناسه چت
            duration: مدت زمان نمایش وضعیت (ثانیه)
        """
        if self.bot is None:
            logger.error("نمونه ربات تنظیم نشده است")
            return
            
        await send_typing_action(self.bot, chat_id, duration)
    
    async def edit_message_text(self, chat_id: Union[int, str], message_id: int, text: str,
                              reply_markup: Optional[InlineKeyboardMarkup] = None,
                              parse_mode: str = 'HTML') -> bool:
        """
        ویرایش متن یک پیام.
        
        پارامترها:
            chat_id: شناسه چت
            message_id: شناسه پیام
            text: متن جدید
            reply_markup: دکمه‌های اینلاین جدید (اختیاری)
            parse_mode: نوع پارس متن (HTML یا Markdown)
            
        بازگشت:
            bool: True در صورت موفقیت، False در غیر این صورت
        """
        if self.bot is None:
            logger.error("نمونه ربات تنظیم نشده است")
            return False
            
        return await edit_message_text(self.bot, chat_id, message_id, text, reply_markup, parse_mode)
    
    async def delete_message(self, chat_id: Union[int, str], message_id: int) -> bool:
        """
        حذف یک پیام.
        
        پارامترها:
            chat_id: شناسه چت
            message_id: شناسه پیام
            
        بازگشت:
            bool: True در صورت موفقیت، False در غیر این صورت
        """
        if self.bot is None:
            logger.error("نمونه ربات تنظیم نشده است")
            return False
            
        return await delete_message(self.bot, chat_id, message_id)
    
    async def send_telegram_notification(self, chat_id: Union[int, str], message: str, **kwargs) -> bool:
        """
        ارسال نوتیفیکیشن تلگرام
        
        پارامترها:
            chat_id: شناسه چت
            message: متن پیام
            **kwargs: پارامترهای اضافی
            
        بازگشت:
            bool: وضعیت موفقیت ارسال
        """
        return await send_telegram_notification(chat_id, message, self.bot, **kwargs)
    
    def send_email_notification(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        """
        ارسال ایمیل
        
        پارامترها:
            recipient: گیرنده ایمیل
            subject: موضوع ایمیل
            body: متن ایمیل
            **kwargs: پارامترهای اضافی
            
        بازگشت:
            bool: وضعیت موفقیت ارسال
        """
        return send_email_notification(recipient, subject, body, **kwargs)
    
    def register_for_notifications(self, user_id: Union[int, str], notification_types: List[str], **kwargs) -> bool:
        """
        ثبت‌نام برای دریافت نوتیفیکیشن‌ها
        
        پارامترها:
            user_id: شناسه کاربر
            notification_types: انواع نوتیفیکیشن‌ها
            **kwargs: پارامترهای اضافی
            
        بازگشت:
            bool: وضعیت موفقیت ثبت‌نام
        """
        return register_for_notifications(user_id, notification_types, **kwargs)
    
    def unregister_from_notifications(self, user_id: Union[int, str], notification_types: Optional[List[str]] = None, **kwargs) -> bool:
        """
        لغو ثبت‌نام از نوتیفیکیشن‌ها
        
        پارامترها:
            user_id: شناسه کاربر
            notification_types: انواع نوتیفیکیشن‌ها (اختیاری)
            **kwargs: پارامترهای اضافی
            
        بازگشت:
            bool: وضعیت موفقیت لغو ثبت‌نام
        """
        return unregister_from_notifications(user_id, notification_types, **kwargs)
    
    def set_bot(self, bot):
        """
        تنظیم نمونه ربات.
        
        پارامترها:
            bot: نمونه ربات تلگرام
        """
        self.bot = bot
    
    def set_config(self, config):
        """
        تنظیم تنظیمات برنامه.
        
        پارامترها:
            config: تنظیمات برنامه
        """
        self.config = config