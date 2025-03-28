#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
این ماژول شامل کلاس اصلی مدیریت تلگرام برای ربات چندمنظوره است.
کلاس TelegramHandler مسئول راه‌اندازی، پیکربندی و مدیریت چرخه حیات ربات تلگرام است.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Union, Callable
import signal
import os
import sys
import time
import glob
import json
from datetime import datetime, timedelta

from telegram import Bot, Update, BotCommand, BotCommandScopeChat
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes, JobQueue
)

from src.core.config import Config
from src.utils.logger import setup_logger
from src.utils.security import encrypt_sensitive_data, decrypt_sensitive_data
from src.utils.localization import get_text
from src.utils.notification import NotificationManager
from src.core.database import Database
from src.handlers import register_all_handlers
from src.utils.timezone_utils import get_current_datetime

logger = logging.getLogger('telegram.handler')

class TelegramHandler:
    """
    مدیریت ارتباط با API تلگرام و تنظیم هندلرها برای پاسخگویی به پیام‌های کاربران.
    """
    
    def __init__(self, config: Config, database: Database):
        """
        مقداردهی اولیه هندلر تلگرام.
        
        Args:
            config (Config): پیکربندی ربات
            database (Database): دسترسی به پایگاه داده
        """
        self.config = config
        self.db = database
        self.application = None
        self.bot = None
        self.job_queue = None
        self.notification_manager = NotificationManager(config)
        
        # لیست دستورهای ربات برای نمایش در منوی دستورات
        self.commands = [
            BotCommand('start', 'شروع استفاده از ربات'),
            BotCommand('help', 'راهنمای استفاده از ربات'),
            BotCommand('settings', 'تنظیمات ربات'),
            BotCommand('profile', 'مشاهده پروفایل کاربری'),
            BotCommand('subscribe', 'خرید اشتراک'),
            BotCommand('contact', 'تماس با پشتیبانی'),
            BotCommand('language', 'تغییر زبان'),
        ]
        
        # لیست دستورهای ادمین
        self.admin_commands = [
            BotCommand('admin', 'پنل مدیریت'),
            BotCommand('stats', 'آمار ربات'),
            BotCommand('broadcast', 'ارسال پیام به همه کاربران'),
            BotCommand('adduser', 'افزودن کاربر جدید'),
            BotCommand('blockuser', 'مسدود کردن کاربر'),
            BotCommand('logs', 'مشاهده لاگ‌ها'),
        ]
        
        logger.info("هندلر تلگرام ایجاد شد")
        
    async def initialize(self):
        """
        راه‌اندازی اولیه هندلر تلگرام و اتصال به API تلگرام.
        """
        logger.info("در حال راه‌اندازی هندلر تلگرام...")
        
        # رمزگشایی توکن تلگرام در صورت نیاز
        token = self.config.get('TELEGRAM_BOT_TOKEN')
        encryption_enabled = self.config.get_bool('SECURITY_ENCRYPT_TOKENS', False)
        if encryption_enabled:
            encryption_key = self.config.get('ENCRYPTION_KEY')
            if encryption_key:
                token = decrypt_sensitive_data(token, encryption_key)
            else:
                logger.warning("کلید رمزنگاری یافت نشد. از توکن بدون رمزگشایی استفاده می‌شود.")
        
        # ایجاد اتصال به تلگرام با API جدید
        self.application = Application.builder().token(token).build()
        self.bot = self.application.bot
        self.job_queue = self.application.job_queue
        
        # اضافه کردن داده‌های ربات به application
        self.application.bot_data['database'] = self.db
        self.application.bot_data['config'] = self.config
        
        # تنظیم اطلاعات پروفایل ربات
        await self._set_bot_commands()
        await self._set_bot_profile()
        
        # ثبت هندلرهای خاص سیستمی
        self._register_system_handlers()
        
        # ثبت تمام هندلرهای دیگر از ماژول‌های دیگر
        register_all_handlers(self.application)
        
        # ثبت کننده‌های سیگنال برای پایان دادن به برنامه
        self._register_signal_handlers()
        
        logger.info("هندلر تلگرام با موفقیت راه‌اندازی شد")
    
    async def _set_bot_commands(self):
        """
        تنظیم لیست دستورات قابل نمایش در منوی تلگرام.
        """
        await self.bot.set_my_commands(self.commands)
        
        # تنظیم دستورات ادمین برای ادمین‌ها
        admin_ids = self.config.get_list('ADMIN_IDS')
        for admin_id in admin_ids:
            try:
                admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
                await self.bot.set_my_commands(
                    self.commands + self.admin_commands,
                    scope=BotCommandScopeChat(chat_id=admin_id_int)
                )
            except Exception as e:
                logger.error(f"خطا در تنظیم دستورات ادمین برای {admin_id}: {e}")
    
    async def _set_bot_profile(self):
        """
        به‌روزرسانی اطلاعات پروفایل ربات (نام، توضیحات و عکس پروفایل).
        """
        bot_name = self.config.get('BOT_NAME', 'Mr.Trader Bot')
        bot_description = self.config.get('BOT_DESCRIPTION', 'ربات تحلیلگر و معامله‌گر ارزهای دیجیتال')
        
        try:
            await self.bot.set_my_name(bot_name)
            await self.bot.set_my_description(bot_description)
            
            # آپلود عکس پروفایل اگر مسیر فایل تنظیم شده است
            profile_photo_path = self.config.get('PROFILE_PHOTO_PATH')
            if profile_photo_path and os.path.exists(profile_photo_path):
                with open(profile_photo_path, 'rb') as photo:
                    await self.bot.set_my_profile_photo(photo.read())
                    logger.info(f"عکس پروفایل از مسیر {profile_photo_path} آپلود شد")
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی پروفایل ربات: {e}")
    
    def _register_system_handlers(self):
        """
        ثبت هندلرهای سیستمی اصلی که باید در این کلاس مدیریت شوند.
        """
        # هندلر خطاها
        self.application.add_error_handler(self._error_handler)
        
        # هندلر دستورات عمومی
        self.application.add_handler(CommandHandler("version", self._version_command))
        self.application.add_handler(CommandHandler("uptime", self._uptime_command))
        self.application.add_handler(CommandHandler("status", self._status_command))
        
        # زمان‌بندی کارهای دوره‌ای
        self._schedule_jobs()
    
    def _register_signal_handlers(self):
        """
        ثبت هندلرهای سیگنال سیستم عامل برای پایان دادن صحیح به ربات.
        """
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, sig, frame):
        """
        مدیریت سیگنال‌های سیستم عامل (SIGINT, SIGTERM).
        
        Args:
            sig: نوع سیگنال
            frame: فریم اجرا
        """
        logger.warning(f"سیگنال {sig} دریافت شد. در حال خروج از برنامه...")
        self.stop()
        sys.exit(0)
    
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        مدیریت و ثبت خطاهای ایجاد شده در هندلرها.
        
        Args:
            update: اطلاعات به‌روزرسانی تلگرام
            context: اطلاعات زمینه‌ای پردازش
        """
        error = context.error
        logger.error(f"خطا در پردازش آپدیت {update}: {error}")
        
        try:
            if isinstance(error, Exception):
                # اطلاع به ادمین‌ها در مورد خطا
                admin_ids = self.config.get_list('ADMIN_IDS')
                for admin_id in admin_ids:
                    admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
                    error_text = f"🔴 *خطای سیستمی*:\n\n" \
                                f"نوع خطا: `{type(error).__name__}`\n" \
                                f"پیام خطا: `{str(error)}`\n\n" \
                                f"زمان: `{get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}`"
                    
                    if update:
                        if update.effective_user:
                            error_text += f"\nکاربر: {update.effective_user.id} (@{update.effective_user.username or 'بدون نام کاربری'})"
                        if update.effective_message:
                            error_text += f"\nپیام: {update.effective_message.text or '[بدون متن]'}"
                    
                    try:
                        await self.bot.send_message(
                            chat_id=admin_id_int,
                            text=error_text,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"خطا در ارسال پیام خطا به ادمین {admin_id}: {e}")
                
            # اطلاع به کاربر در مورد خطا
            if update and update.effective_chat:
                language_code = 'fa'
                if update.effective_user:
                    # تلاش برای دریافت زبان کاربر از دیتابیس
                    try:
                        user_data = self.db.execute(
                            "SELECT language_code FROM users WHERE user_id = ?", 
                            (update.effective_user.id,)
                        )
                        if user_data and user_data[0]:
                            language_code = user_data[0][0] or 'fa'
                    except:
                        # اگر دریافت از دیتابیس ناموفق بود، از زبان تلگرام استفاده می‌کنیم
                        language_code = update.effective_user.language_code or 'fa'
                
                error_msg = get_text("error.general", language_code)
                await self.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=error_msg,
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logger.error(f"خطا در هندلر خطا: {e}")
    
    async def _version_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        نمایش اطلاعات نسخه ربات.
        
        Args:
            update: اطلاعات به‌روزرسانی تلگرام
            context: اطلاعات زمینه‌ای پردازش
        """
        version = self.config.get('BOT_VERSION', '1.0.0')
        last_update = self.config.get('LAST_UPDATE_DATE', 'نامشخص')
        await update.message.reply_text(
            f"🤖 *نسخه ربات*: `{version}`\n"
            f"📅 تاریخ آخرین به‌روزرسانی: {last_update}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def _uptime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        نمایش زمان فعالیت ربات.
        
        Args:
            update: اطلاعات به‌روزرسانی تلگرام
            context: اطلاعات زمینه‌ای پردازش
        """
        # زمان شروع ربات از متغیر محیطی یا فایل تنظیمات
        start_time = float(os.environ.get('BOT_START_TIME', self.config.get('START_TIME', time.time())))
        
        uptime_seconds = int(time.time() - start_time)
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        uptime_text = f"🕒 *زمان فعالیت ربات*:\n\n" \
                     f"{days} روز, {hours} ساعت, {minutes} دقیقه, {seconds} ثانیه"
        
        await update.message.reply_text(uptime_text, parse_mode=ParseMode.MARKDOWN)
    
    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        نمایش وضعیت ربات و سیستم.
        
        Args:
            update: اطلاعات به‌روزرسانی تلگرام
            context: اطلاعات زمینه‌ای پردازش
        """
        # بررسی دسترسی کاربر (فقط ادمین‌ها)
        admin_ids = self.config.get_list('ADMIN_IDS')
        if str(update.effective_user.id) not in map(str, admin_ids):
            await update.message.reply_text("⛔ شما دسترسی به این دستور را ندارید.")
            return
            
        try:
            # اطلاعات سیستم
            try:
                import psutil
                
                # مصرف CPU و RAM
                cpu_percent = psutil.cpu_percent()
                memory_info = psutil.virtual_memory()
                disk_info = psutil.disk_usage('/')
                
                system_info = f"🖥️ *سیستم*:\n" \
                             f"  • CPU: {cpu_percent}%\n" \
                             f"  • RAM: {memory_info.percent}% (استفاده شده: {memory_info.used // (1024**2)} MB)\n" \
                             f"  • دیسک: {disk_info.percent}% (آزاد: {disk_info.free // (1024**3)} GB)\n\n"
            except ImportError:
                system_info = "🖥️ *سیستم*: (اطلاعات در دسترس نیست - psutil نصب نشده)\n\n"
            
            # تعداد کاربران
            try:
                total_users = self.db.execute("SELECT COUNT(*) FROM users")[0][0]
                active_users = self.db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")[0][0]
                users_info = f"👥 *کاربران*:\n" \
                            f"  • کل: {total_users}\n" \
                            f"  • فعال: {active_users}\n\n"
            except Exception as e:
                logger.error(f"خطا در دریافت آمار کاربران: {e}")
                users_info = "👥 *کاربران*: (خطا در دریافت آمار)\n\n"
            
            # آمار پرداخت‌ها (نمونه)
            try:
                total_payments = self.db.execute("SELECT COUNT(*) FROM payments")[0][0]
                successful_payments = self.db.execute("SELECT COUNT(*) FROM payments WHERE status = 'success'")[0][0]
                payments_info = f"💰 *پرداخت‌ها*:\n" \
                               f"  • کل: {total_payments}\n" \
                               f"  • موفق: {successful_payments}\n\n"
            except Exception as e:
                logger.error(f"خطا در دریافت آمار پرداخت‌ها: {e}")
                payments_info = "💰 *پرداخت‌ها*: (خطا در دریافت آمار)\n\n"
            
            status_text = f"📊 *وضعیت سیستم ربات*\n\n" \
                         f"{system_info}" \
                         f"{users_info}" \
                         f"{payments_info}" \
                         f"⏱️ *زمان سرور*: {get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"خطا در اجرای دستور status: {e}")
            await update.message.reply_text(f"❌ خطا در دریافت وضعیت: {str(e)}")
    
    def _schedule_jobs(self):
        """
        زمان‌بندی کارهای دوره‌ای برای اجرا.
        """
        # بررسی اشتراک‌های منقضی شده - هر روز ساعت ۱ صبح
        self.job_queue.run_daily(
            self._check_expired_subscriptions,
            time=datetime.time(hour=1, minute=0, second=0)
        )
        
        # پشتیبان‌گیری روزانه - هر روز ساعت ۲ صبح
        self.job_queue.run_daily(
            self._daily_backup,
            time=datetime.time(hour=2, minute=0, second=0)
        )
        
        # پاکسازی فایل‌های موقت - هر هفته
        self.job_queue.run_daily(
            self._clean_temp_files,
            time=datetime.time(hour=3, minute=0, second=0),
            days=(1,)  # دوشنبه‌ها
        )
        
        # بررسی وضعیت سیستم - هر ۳۰ دقیقه
        self.job_queue.run_repeating(
            self._monitor_system_status,
            interval=1800
        )
    
    async def _check_expired_subscriptions(self, context: ContextTypes.DEFAULT_TYPE):
        """
        بررسی اشتراک‌های منقضی شده و اطلاع به کاربران.
        
        Args:
            context: اطلاعات زمینه‌ای پردازش
        """
        logger.info("در حال بررسی اشتراک‌های منقضی شده...")
        
        # کاربرانی که اشتراک آنها منقضی شده
        try:
            expired_users = self.db.execute(
                "SELECT user_id, subscription_type FROM subscriptions "
                "WHERE expiry_date < CURRENT_TIMESTAMP AND notified = 0"
            )
            
            for user_id, subscription_type in expired_users:
                # آپدیت وضعیت اطلاع‌رسانی
                self.db.execute(
                    "UPDATE subscriptions SET notified = 1 WHERE user_id = ?",
                    (user_id,)
                )
                
                # ارسال پیام به کاربر
                try:
                    user_lang = self.db.execute(
                        "SELECT language_code FROM users WHERE user_id = ?", 
                        (user_id,)
                    )[0][0] or 'fa'
                    
                    expire_msg = get_text("subscription.expired", user_lang)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=expire_msg.format(subscription_type=subscription_type),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.error(f"خطا در ارسال پیام انقضای اشتراک به کاربر {user_id}: {e}")
        except Exception as e:
            logger.error(f"خطا در بررسی اشتراک‌های منقضی شده: {e}")
    
    async def _daily_backup(self, context: ContextTypes.DEFAULT_TYPE):
        """
        ایجاد پشتیبان روزانه از پایگاه داده.
        
        Args:
            context: اطلاعات زمینه‌ای پردازش
        """
        logger.info("در حال ایجاد پشتیبان روزانه...")
        
        try:
            import shutil
            from pathlib import Path
            
            # مسیر پایگاه داده اصلی
            db_path = self.config.get('DB_PATH', 'data/db/bot.db')
            
            # مسیر فولدر پشتیبان روزانه
            backup_dir = Path("data/backups/daily")
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # ایجاد نام فایل پشتیبان با تاریخ
            backup_filename = f"bot_backup_{get_current_datetime().strftime('%Y-%m-%d')}.db"
            backup_path = backup_dir / backup_filename
            
            # کپی فایل پایگاه داده
            shutil.copy2(db_path, backup_path)
            
            # حذف پشتیبان‌های قدیمی (بیشتر از ۷ روز)
            backup_files = list(backup_dir.glob("bot_backup_*.db"))
            backup_files.sort()
            
            while len(backup_files) > 7:
                oldest_file = backup_files.pop(0)
                oldest_file.unlink()
                
            # اطلاع به ادمین‌ها
            admin_ids = self.config.get_list('ADMIN_IDS')
            admin_msg = f"✅ پشتیبان روزانه با موفقیت ایجاد شد: `{backup_filename}`"
            
            for admin_id in admin_ids:
                try:
                    admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
                    await context.bot.send_message(
                        chat_id=admin_id_int,
                        text=admin_msg,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.error(f"خطا در ارسال پیام پشتیبان‌گیری به ادمین {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"خطا در ایجاد پشتیبان روزانه: {e}")
            
            # اطلاع به ادمین‌ها در مورد خطا
            error_msg = f"❌ خطا در ایجاد پشتیبان روزانه: `{str(e)}`"
            admin_ids = self.config.get_list('ADMIN_IDS')
            
            for admin_id in admin_ids:
                try:
                    admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
                    await context.bot.send_message(
                        chat_id=admin_id_int,
                        text=error_msg,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass
    
    async def _clean_temp_files(self, context: ContextTypes.DEFAULT_TYPE):
        """
        پاکسازی فایل‌های موقت و قدیمی.
        
        Args:
            context: اطلاعات زمینه‌ای پردازش
        """
        logger.info("در حال پاکسازی فایل‌های موقت...")
        
        try:
            import os
            from pathlib import Path
            import time
            
            # پاکسازی فولدر کش
            cache_dir = Path("cache")
            if cache_dir.exists():
                now = time.time()
                deleted_count = 0
                
                for file_path in cache_dir.glob("**/*"):
                    if file_path.is_file():
                        # حذف فایل‌های قدیمی‌تر از ۷ روز
                        if now - file_path.stat().st_mtime > (7 * 86400):
                            file_path.unlink()
                            deleted_count += 1
                
                logger.info(f"{deleted_count} فایل موقت پاکسازی شد")
                
                # اطلاع به ادمین‌ها
                if deleted_count > 0:
                    admin_msg = f"🧹 تعداد {deleted_count} فایل موقت پاکسازی شد"
                    admin_ids = self.config.get_list('ADMIN_IDS')
                    
                    for admin_id in admin_ids:
                        try:
                            admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
                            await context.bot.send_message(
                                chat_id=admin_id_int, 
                                text=admin_msg
                            )
                        except Exception:
                            pass
        
        except Exception as e:
            logger.error(f"خطا در پاکسازی فایل‌های موقت: {e}")
    
    async def _monitor_system_status(self, context: ContextTypes.DEFAULT_TYPE):
        """
        بررسی وضعیت سیستم و هشدار در صورت مشکل.
        
        Args:
            context: اطلاعات زمینه‌ای پردازش
        """
        try:
            import psutil
            
            # بررسی مصرف CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:  # استفاده بیش از ۹۰٪
                admin_ids = self.config.get_list('ADMIN_IDS')
                for admin_id in admin_ids:
                    admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
                    await context.bot.send_message(
                        chat_id=admin_id_int,
                        text=f"⚠️ *هشدار سیستم*: مصرف CPU بالا ({cpu_percent}%)",
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            # بررسی مصرف RAM
            memory = psutil.virtual_memory()
            if memory.percent > 90:  # استفاده بیش از ۹۰٪
                admin_ids = self.config.get_list('ADMIN_IDS')
                for admin_id in admin_ids:
                    admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
                    await context.bot.send_message(
                        chat_id=admin_id_int,
                        text=f"⚠️ *هشدار سیستم*: مصرف حافظه بالا ({memory.percent}%)",
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            # بررسی فضای دیسک
            disk = psutil.disk_usage('/')
            if disk.percent > 90:  # استفاده بیش از ۹۰٪
                admin_ids = self.config.get_list('ADMIN_IDS')
                for admin_id in admin_ids:
                    admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
                    await context.bot.send_message(
                        chat_id=admin_id_int,
                        text=f"⚠️ *هشدار سیستم*: فضای دیسک کم ({disk.percent}%)",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
        except Exception as e:
            logger.error(f"خطا در بررسی وضعیت سیستم: {e}")
    
    async def start_polling(self):
        """
        شروع ربات در حالت polling (دریافت مستمر آپدیت‌ها).
        """
        logger.info("شروع ربات در حالت polling...")
        
        # ثبت زمان شروع
        os.environ['BOT_START_TIME'] = str(time.time())
        
        # اطلاع به ادمین‌ها
        start_msg = f"🟢 *ربات شروع به کار کرد*\n\n" \
                   f"⏰ زمان: {get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}\n" \
                   f"🤖 نسخه: {self.config.get('BOT_VERSION', '1.0.0')}"
        
        admin_ids = self.config.get_list('ADMIN_IDS')
        for admin_id in admin_ids:
            try:
                admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
                await self.bot.send_message(
                    chat_id=admin_id_int,
                    text=start_msg,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"خطا در ارسال پیام شروع به ادمین {admin_id}: {e}")
        
        # شروع پردازش آپدیت‌ها
        await self.application.start_polling()
        
        logger.info("ربات با موفقیت شروع به کار کرد")
    
    async def start_webhook(self, webhook_url, webhook_port=8443, webhook_path='', listen_address='0.0.0.0'):
        """
        شروع ربات در حالت webhook.
        
        Args:
            webhook_url: آدرس webhook
            webhook_port: شماره پورت (پیش‌فرض: 8443)
            webhook_path: مسیر در URL (پیش‌فرض: '')
            listen_address: آدرس شنود (پیش‌فرض: '0.0.0.0')
        """
        logger.info("شروع ربات در حالت webhook...")
        
        # ثبت زمان شروع
        os.environ['BOT_START_TIME'] = str(time.time())
        
        # راه‌اندازی وب‌هوک
        await self.application.start_webhook(
            listen=listen_address,
            port=webhook_port,
            url_path=webhook_path,
            webhook_url=webhook_url
        )
        
        logger.info(f"ربات با موفقیت در حالت webhook راه‌اندازی شد (پورت: {webhook_port})")
        
        # اطلاع به ادمین‌ها
        start_msg = f"🟢 *ربات در حالت webhook شروع به کار کرد*\n\n" \
                   f"⏰ زمان: {get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}\n" \
                   f"🤖 نسخه: {self.config.get('BOT_VERSION', '1.0.0')}\n" \
                   f"🔗 Webhook URL: {webhook_url}"
        
        admin_ids = self.config.get_list('ADMIN_IDS')   
        for admin_id in admin_ids:
            try:
                admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
                await self.bot.send_message(
                    chat_id=admin_id_int,
                    text=start_msg,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"خطا در ارسال پیام شروع به ادمین {admin_id}: {e}")
    
    async def stop(self):
        """
        توقف کامل ربات و پاکسازی منابع.
        """
        logger.info("در حال متوقف کردن ربات...")
        
        # اطلاع به ادمین‌ها
        stop_msg = f"🔴 *ربات متوقف شد*\n\n⏰ زمان: {get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}"
        admin_ids = self.config.get_list('ADMIN_IDS')
        
        if self.bot:
            for admin_id in admin_ids:
                try:
                    admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
                    await self.bot.send_message(
                        chat_id=admin_id_int,
                        text=stop_msg,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass
        
        # توقف application
        if self.application:
            await self.application.stop()
        
        logger.info("ربات با موفقیت متوقف شد")