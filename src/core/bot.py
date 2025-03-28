#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
کلاس اصلی ربات تلگرام.

این ماژول شامل کلاس اصلی ربات تلگرام است که ارتباط با API تلگرام را مدیریت می‌کند
و هندلرهای مختلف را برای پردازش پیام‌ها، دستورات و کالبک‌ها ثبت می‌کند.

تاریخ ایجاد: ۱۴۰۴/۰۱/۰۷
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ماژول‌های داخلی
from handlers.admin_handlers import register_admin_handlers
from handlers.payment_handlers import register_payment_handlers
from handlers.user_handlers import register_user_handlers
from utils.notification import send_admin_notification
from utils.localization import get_message
from core.database import Database
from utils.cache import Cache

logger = logging.getLogger(__name__)

class TelegramBot:
    """
    کلاس اصلی ربات تلگرام که تمام عملیات مربوط به تلگرام را مدیریت می‌کند.
    """
    
    def __init__(self, config: Dict[str, Any], database: Database, cache: Cache):
        """
        مقداردهی اولیه کلاس ربات.
        
        پارامترها:
            config: دیکشنری حاوی تنظیمات ربات
            database: شیء پایگاه داده
            cache: سیستم کش
        """
        print("در حال ایجاد آبجکت TelegramBot...")
        self.config = config
        self.database = database
        self.cache = cache
        self.bot_token = self._get_bot_token()
        self.application = None
        self.bot = None
        
        # ثبت وضعیت ربات
        self.is_running = False
        
        print("کلاس ربات تلگرام ایجاد شد.")
        logger.info("کلاس ربات تلگرام ایجاد شد.")
    
    def _get_bot_token(self) -> str:
        """
        دریافت توکن ربات از تنظیمات.
        
        بازگشت:
            str: توکن ربات تلگرام
        
        استثناها:
            ValueError: اگر توکن ربات تنظیم نشده باشد.
        """
        token = self.config.get('TELEGRAM_BOT_TOKEN')
        if not token:
            logger.error("توکن ربات تلگرام تنظیم نشده است!")
            raise ValueError("توکن ربات تلگرام در فایل تنظیمات یافت نشد.")
        print(f"توکن ربات دریافت شد: {token[:5]}...{token[-5:]}")
        return token
    
    async def error_handler(self, update: Optional[Update], context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        پردازش خطاهای رخ داده در ربات.
        
        پارامترها:
            update: آبجکت آپدیت تلگرام (می‌تواند None باشد)
            context: کانتکست ربات
        """
        logger.error(f"خطا در پردازش آپدیت: {context.error}")
        print(f"خطا در پردازش آپدیت: {context.error}")
        
        # ارسال اعلان به ادمین‌ها
        error_message = f"خطا در ربات:\n{context.error}"
        if update:
            error_message += f"\nکاربر: {update.effective_user.id if update.effective_user else 'ناشناس'}"
            error_message += f"\nچت: {update.effective_chat.id if update.effective_chat else 'ناشناس'}"
            if update.effective_message:
                error_message += f"\nپیام: {update.effective_message.text}"
        
        await send_admin_notification(context.bot, error_message, self.config)
    
    def setup_handlers(self) -> None:
        """
        ثبت تمام هندلرهای ربات.
        """
        print("در حال ثبت هندلرهای ربات...")
        logger.info("در حال ثبت هندلرهای ربات...")
        
        # اطلاعاتی که باید در دسترس همه هندلرها باشد
        self.application.bot_data['database'] = self.database
        self.application.bot_data['config'] = self.config
        self.application.bot_data['cache'] = self.cache
        
        # ثبت هندلرهای مدیریتی
        register_admin_handlers(self.application, self.config, self.database, self.cache)
        
        # ثبت هندلرهای پرداخت
        register_payment_handlers(self.application, self.config, self.database, self.cache)
        
        # ثبت هندلرهای کاربران عادی
        register_user_handlers(self.application)
        
        # ثبت هندلر خطا
        self.application.add_error_handler(self.error_handler)
        
        print("تمام هندلرهای ربات با موفقیت ثبت شدند.")
        logger.info("تمام هندلرهای ربات با موفقیت ثبت شدند.")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        پردازش دستور /start
        
        پارامترها:
            update: آبجکت آپدیت تلگرام
            context: کانتکست ربات
        """
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        # ذخیره کاربر در پایگاه داده اگر جدید است
        self.database.add_or_update_user(user.id, user.first_name, user.last_name, user.username)
        
        # دریافت پیام به زبان کاربر
        user_lang = self.database.get_user_language(user.id) or 'fa'
        welcome_message = get_message('welcome', user_lang).format(name=user.first_name)
        
        await context.bot.send_message(chat_id=chat_id, text=welcome_message)
        
        logger.info(f"کاربر {user.id} ربات را استارت کرد.")
    
    async def post_init(self, application: Application) -> None:
        """
        اجرا پس از راه‌اندازی ربات.
        
        پارامترها:
            application: آبجکت اپلیکیشن تلگرام
        """
        # ارسال اعلان راه‌اندازی به ادمین‌ها
        await send_admin_notification(
            self.bot, 
            "🟢 ربات با موفقیت راه‌اندازی شد.", 
            self.config
        )
    
    def start(self) -> None:
        """
        راه‌اندازی ربات و شروع به دریافت پیام‌ها.
        """
        if self.is_running:
            logger.warning("ربات قبلاً راه‌اندازی شده است!")
            print("ربات قبلاً راه‌اندازی شده است!")
            return
        
        print("در حال راه‌اندازی ربات تلگرام...")
        logger.info("در حال راه‌اندازی ربات تلگرام...")
        
        try:
            # ایجاد آپلیکیشن تلگرام
            print(f"در حال ایجاد آپلیکیشن با توکن: {self.bot_token[:5]}...{self.bot_token[-5:]}")
            self.application = Application.builder().token(self.bot_token).post_init(self.post_init).build()
            self.bot = self.application.bot
            
            # افزودن هندلر دستور /start
            self.application.add_handler(CommandHandler("start", self.start_command))
            
            # ثبت سایر هندلرها
            self.setup_handlers()
            
            # راه‌اندازی polling
            print("شروع دریافت پیام‌های ربات...")
            logger.info("شروع دریافت پیام‌های ربات...")
            self.is_running = True
            self.application.run_polling()
            
        except Exception as e:
            print(f"خطا در راه‌اندازی ربات: {str(e)}")
            logger.error(f"خطا در راه‌اندازی ربات: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def stop(self) -> None:
        """
        توقف ربات.
        """
        if not self.is_running:
            logger.warning("ربات در حال اجرا نیست!")
            return 
        
        logger.info("در حال متوقف کردن ربات...")
        
        if self.application:
            self.application.stop()
            
        self.is_running = False
        logger.info("ربات با موفقیت متوقف شد.")