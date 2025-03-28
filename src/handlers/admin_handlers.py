#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول هندلرهای مدیریت.

این ماژول شامل هندلرهای تلگرام برای پردازش پیام‌ها و دستورات مدیران ربات است.

تاریخ ایجاد: ۱۴۰۴/۰۱/۰۷
"""

import datetime
from datetime import timezone
import logging
import json
from typing import Dict, Any, List, Tuple, Set, Optional
from datetime import datetime
from src.utils.timezone_utils import get_current_datetime
from datetime import timedelta
import asyncio
import os
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

from src.core.database import Database
from src.utils.cache import Cache
from src.utils.localization import get_message, get_available_languages
from src.utils.notification import send_typing_action, send_admin_notification
from src.utils.logger import log_execution_time

logger = logging.getLogger(__name__)

# مجموعه کلیدهای مجاز کالبک ادمین
ADMIN_CALLBACK_STATS = "admin:stats"
ADMIN_CALLBACK_BROADCAST = "admin:broadcast"
ADMIN_CALLBACK_USERS = "admin:users"
ADMIN_CALLBACK_PAYMENTS = "admin:payments"
ADMIN_CALLBACK_SETTINGS = "admin:settings"
ADMIN_CALLBACK_BACKUP = "admin:backup"
ADMIN_CALLBACK_RELOAD = "admin:reload"

# وضعیت‌های گفتگو برای مدیران
ADMIN_STATE_BROADCAST = "admin_broadcast"
ADMIN_STATE_USER_SEARCH = "admin_user_search"
ADMIN_STATE_ADD_ADMIN = "admin_add_admin"

async def check_admin_permission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    بررسی دسترسی ادمینی کاربر.
    
    پارامترها: 
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        
    بازگشت:
        bool: True اگر کاربر ادمین باشد، False در غیر این صورت
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت پایگاه داده و تنظیمات از کانتکست
    database: Database = context.bot_data.get('database')
    config = context.bot_data.get('config', {})
    
    # دریافت لیست ادمین‌ها از تنظیمات
    admin_ids = set(config.get('ADMIN_IDS', []))
    
    # بررسی وضعیت ادمین از پایگاه داده
    user_data = database.get_user(user.id)
    if user_data and user_data.get('is_admin', 0) == 1:
        return True
    
    # اگر کاربر در لیست ادمین‌های تنظیمات باشد
    if user.id in admin_ids:
        # اطمینان از ثبت در پایگاه داده
        try:
            database.execute_query(
                "UPDATE users SET is_admin = 1 WHERE user_id = ?",
                (user.id,)
            )
            logger.info(f"کاربر {user.id} به عنوان ادمین در پایگاه داده ثبت شد.")
        except Exception as e:
            logger.error(f"خطا در ثبت وضعیت ادمین کاربر {user.id}: {str(e)}")
        
        return True
    
    # کاربر ادمین نیست
    # دریافت زبان کاربر
    user_lang = database.get_user_language(user.id) or 'fa'
    
    # ارسال پیام خطای دسترسی
    await context.bot.send_message(
        chat_id=chat_id,
        text=get_message('permission_denied', user_lang)
    )
    
    logger.warning(f"کاربر {user.id} تلاش کرد به بخش ادمین دسترسی پیدا کند.")
    return False

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش دستور /admin
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    # بررسی دسترسی ادمینی
    if not await check_admin_permission(update, context):
        return
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # دریافت زبان کاربر
    user_lang = database.get_user_language(user.id) or 'fa'
    
    # ساخت دکمه‌های پنل ادمین
    keyboard = [
        [
            InlineKeyboardButton("📊 آمار", callback_data=ADMIN_CALLBACK_STATS),
            InlineKeyboardButton("📢 اعلان عمومی", callback_data=ADMIN_CALLBACK_BROADCAST)
        ],
        [
            InlineKeyboardButton("👤 کاربران", callback_data=ADMIN_CALLBACK_USERS),
            InlineKeyboardButton("💰 پرداخت‌ها", callback_data=ADMIN_CALLBACK_PAYMENTS)
        ],
        [
            InlineKeyboardButton("⚙️ تنظیمات", callback_data=ADMIN_CALLBACK_SETTINGS),
            InlineKeyboardButton("💾 پشتیبان‌گیری", callback_data=ADMIN_CALLBACK_BACKUP)
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام پنل ادمین
    admin_message = f"👨‍💼 پنل مدیریت\n\n"
    admin_message += f"خوش آمدید {user.first_name}!\n"
    admin_message += f"از این بخش می‌توانید ربات را مدیریت کنید."
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=admin_message,
        reply_markup=reply_markup
    )
    
    logger.info(f"پنل ادمین برای کاربر {user.id} نمایش داده شد.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش دستور /stats
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    # بررسی دسترسی ادمینی
    if not await check_admin_permission(update, context):
        return
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # نمایش وضعیت تایپ برای محاسبات
    await send_typing_action(context.bot, chat_id, duration=2.0)
    
    # دریافت آمار از پایگاه داده
    try:
        total_users = database.execute_query("SELECT COUNT(*) as count FROM users")[0]['count']
        active_users = database.execute_query(
            "SELECT COUNT(*) as count FROM users WHERE last_activity > ?",
            (get_current_datetime() - timedelta(days=7)).isoformat()
        )[0]['count']
        total_payments = database.execute_query("SELECT COUNT(*) as count FROM payments")[0]['count']
        successful_payments = database.execute_query(
            "SELECT COUNT(*) as count FROM payments WHERE status = 'completed'"
        )[0]['count']
        total_amount = database.execute_query(
            "SELECT SUM(amount) as total FROM payments WHERE status = 'completed'"
        )[0]['total'] or 0
        
        # توزیع زبان‌ها
        language_stats = database.execute_query(
            "SELECT language, COUNT(*) as count FROM users GROUP BY language ORDER BY count DESC"
        )
        
        # تعداد اشتراک‌های فعال
        active_subscriptions = database.execute_query(
            "SELECT COUNT(*) as count FROM users WHERE subscription_expiry > ?",
            (get_current_datetime().isoformat(),)
        )[0]['count']
    except Exception as e:
        logger.error(f"خطا در دریافت آمار: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ خطا در دریافت آمار: {str(e)}"
        )
        return
    
    # ساخت پیام آمار
    stats_message = f"📊 آمار ربات\n\n"
    stats_message += f"👤 کاربران کل: {total_users:,}\n"
    stats_message += f"🟢 کاربران فعال (۷ روز اخیر): {active_users:,}\n"
    stats_message += f"💳 اشتراک‌های فعال: {active_subscriptions:,}\n\n"
    
    stats_message += f"💰 پرداخت‌ها:\n"
    stats_message += f"- تعداد کل: {total_payments:,}\n"
    stats_message += f"- موفق: {successful_payments:,}\n"
    stats_message += f"- جمع مبالغ: {total_amount:,} تومان\n\n"
    
    stats_message += f"🌐 توزیع زبان‌ها:\n"
    for lang_stat in language_stats:
        lang_code = lang_stat['language']
        lang_count = lang_stat['count']
        lang_percent = (lang_count / total_users) * 100 if total_users > 0 else 0
        stats_message += f"- {lang_code}: {lang_count:,} ({lang_percent:.1f}%)\n"
    
    # اضافه کردن تاریخ گزارش
    stats_message += f"\n⏱ تاریخ گزارش: {get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # نمایش آمار
    await context.bot.send_message(
        chat_id=chat_id,
        text=stats_message
    )
    
    logger.info(f"آمار ربات برای کاربر {user.id} نمایش داده شد.")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش دستور /broadcast
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    # بررسی دسترسی ادمینی
    if not await check_admin_permission(update, context):
        return
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # دریافت زبان کاربر
    user_lang = database.get_user_language(user.id) or 'fa'
    
    # تنظیم وضعیت کاربر
    context.user_data['state'] = ADMIN_STATE_BROADCAST
    
    # ساخت دکمه‌های انتخاب گروه کاربران
    keyboard = [
        [
            InlineKeyboardButton("👥 همه کاربران", callback_data="broadcast:all"),
            InlineKeyboardButton("💳 مشترکین", callback_data="broadcast:subscribers")
        ],
        [
            InlineKeyboardButton("🟢 کاربران فعال", callback_data="broadcast:active"),
            InlineKeyboardButton("🆕 کاربران جدید", callback_data="broadcast:new")
        ],
        [InlineKeyboardButton("❌ لغو", callback_data="broadcast:cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام راهنمای اعلان عمومی
    broadcast_message = f"📢 ارسال اعلان عمومی\n\n"
    broadcast_message += f"لطفاً گروه کاربران هدف را انتخاب کنید:"
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=broadcast_message,
        reply_markup=reply_markup
    )
    
    logger.info(f"فرآیند اعلان عمومی توسط کاربر {user.id} آغاز شد.")

async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str) -> None:
    """
    پردازش متن اعلان عمومی
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        message_text: متن اعلان
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # دریافت اطلاعات گروه هدف
    target_group = context.user_data.get('broadcast_target', 'all')
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id)
    
    # دریافت لیست کاربران هدف
    try:
        if target_group == 'all':
            # همه کاربران
            users = database.execute_query("SELECT user_id FROM users WHERE is_blocked = 0")
        elif target_group == 'subscribers':
            # مشترکین فعال
            users = database.execute_query(
                "SELECT user_id FROM users WHERE is_blocked = 0 AND subscription_expiry > ?",
                (get_current_datetime().isoformat(),)
            )
        elif target_group == 'active':
            # کاربران فعال (7 روز اخیر)
            users = database.execute_query(
                "SELECT user_id FROM users WHERE is_blocked = 0 AND last_activity > ?",
                ((get_current_datetime() - timedelta(days=7)).isoformat(),)
            )
        elif target_group == 'new':
            # کاربران جدید (7 روز اخیر)
            users = database.execute_query(
                "SELECT user_id FROM users WHERE is_blocked = 0 AND created_at > ?",
                ((get_current_datetime() - timedelta(days=7)).isoformat(),)
            )
        else:
            users = []
    except Exception as e:
        logger.error(f"خطا در دریافت لیست کاربران: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ خطا در دریافت لیست کاربران: {str(e)}"
        )
        context.user_data['state'] = None
        context.user_data.pop('broadcast_target', None)
        return
    
    # تبدیل نتیجه به لیست شناسه‌ها
    user_ids = [user['user_id'] for user in users]
    total_users = len(user_ids)
    
    if total_users == 0:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ هیچ کاربری در گروه هدف یافت نشد!"
        )
        context.user_data['state'] = None
        context.user_data.pop('broadcast_target', None)
        return
    
    # ساخت دکمه‌های تأیید یا لغو
    keyboard = [
        [
            InlineKeyboardButton("✅ ارسال", callback_data="broadcast:confirm"),
            InlineKeyboardButton("❌ لغو", callback_data="broadcast:cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ذخیره اطلاعات اعلان
    context.user_data['broadcast_message'] = message_text
    context.user_data['broadcast_users'] = user_ids
    
    # ارسال پیام تأیید
    confirm_message = f"⚠️ تأیید ارسال اعلان عمومی\n\n"
    confirm_message += f"متن پیام:\n"
    confirm_message += f"{message_text}\n\n"
    confirm_message += f"این پیام به {total_users:,} کاربر ارسال خواهد شد.\n"
    confirm_message += f"آیا از ارسال اطمینان دارید؟"
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=confirm_message,
        reply_markup=reply_markup
    )
    
    logger.info(f"متن اعلان عمومی توسط کاربر {user.id} آماده شد.")

async def send_broadcast_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    ارسال اعلان عمومی به کاربران
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت اطلاعات اعلان
    message_text = context.user_data.get('broadcast_message', '')
    user_ids = context.user_data.get('broadcast_users', [])
    
    if not message_text or not user_ids:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ اطلاعات اعلان ناقص است!"
        )
        return
    
    # پاکسازی وضعیت
    context.user_data['state'] = None
    context.user_data.pop('broadcast_message', None)
    context.user_data.pop('broadcast_users', None)
    context.user_data.pop('broadcast_target', None)
    
    # ارسال پیام شروع
    status_message = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔄 در حال ارسال اعلان به {len(user_ids):,} کاربر...\n\n"
             f"0% تکمیل شده"
    )
    
    # ارسال پیام به کاربران
    success_count = 0
    failed_count = 0
    
    for index, user_id in enumerate(user_ids):
        try:
            # ارسال پیام به کاربر
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode=ParseMode.HTML
            )
            success_count += 1
            
            # به‌روزرسانی پیام وضعیت هر 50 مورد
            if (index + 1) % 50 == 0 or index == len(user_ids) - 1:
                progress = ((index + 1) / len(user_ids)) * 100
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_message.message_id,
                    text=f"🔄 در حال ارسال اعلان به {len(user_ids):,} کاربر...\n\n"
                         f"موفق: {success_count:,}\n"
                         f"ناموفق: {failed_count:,}\n"
                         f"{progress:.1f}% تکمیل شده"
                )
            
            # تأخیر برای جلوگیری از محدودیت API تلگرام
            await asyncio.sleep(0.05)
            
        except Exception as e:
            logger.error(f"خطا در ارسال اعلان به کاربر {user_id}: {str(e)}")
            failed_count += 1
            await asyncio.sleep(0.1)  # تأخیر بیشتر در صورت خطا
    
    # ارسال گزارش نهایی
    final_message = f"✅ ارسال اعلان عمومی به پایان رسید.\n\n"
    final_message += f"📊 آمار ارسال:\n"
    final_message += f"- کل: {len(user_ids):,}\n"
    final_message += f"- موفق: {success_count:,}\n"
    final_message += f"- ناموفق: {failed_count:,}\n"
    final_message += f"- درصد موفقیت: {(success_count / len(user_ids) * 100):.1f}%"
    
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=status_message.message_id,
        text=final_message
    )
    
    logger.info(f"ارسال اعلان عمومی توسط کاربر {user.id} به پایان رسید. "
                f"موفق: {success_count}, ناموفق: {failed_count}")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش دستور /users
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    # بررسی دسترسی ادمینی
    if not await check_admin_permission(update, context):
        return
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id)
    
    # دریافت آخرین کاربران
    try:
        recent_users = database.execute_query(
            "SELECT user_id, first_name, last_name, username, created_at "
            "FROM users ORDER BY created_at DESC LIMIT 10"
        )
    except Exception as e:
        logger.error(f"خطا در دریافت لیست کاربران: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ خطا در دریافت لیست کاربران: {str(e)}"
        )
        return
    
    # ساخت پیام
    users_message = f"👥 کاربران اخیر\n\n"
    
    for u in recent_users:
        created_date = u['created_at'].split('T')[0] if u['created_at'] else "نامشخص"
        users_message += f"👤 {u['first_name']} {u['last_name'] or ''}\n"
        users_message += f"🆔 {u['user_id']}\n"
        users_message += f"🌐 @{u['username'] or 'ندارد'}\n"
        users_message += f"📅 {created_date}\n\n"
    
    # ساخت دکمه‌های مدیریت کاربران
    keyboard = [
        [
            InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin:search_user"),
            InlineKeyboardButton("➕ افزودن ادمین", callback_data="admin:add_admin")
        ],
        [
            InlineKeyboardButton("📊 آمار کاربران", callback_data="admin:user_stats"),
            InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:back")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام
    await context.bot.send_message(
        chat_id=chat_id,
        text=users_message,
        reply_markup=reply_markup
    )
    
    logger.info(f"لیست کاربران اخیر برای کاربر {user.id} نمایش داده شد.")

async def handle_admin_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش کالبک‌های بخش ادمین
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    callback_query = update.callback_query
    user = callback_query.from_user
    chat_id = callback_query.message.chat_id
    message_id = callback_query.message.message_id
    callback_data = callback_query.data
    
    # بررسی دسترسی ادمینی
    if not await check_admin_permission(update, context):
        await callback_query.answer("⛔ شما دسترسی به این بخش را ندارید!", show_alert=True)
        return
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # پاسخ به کالبک
    await callback_query.answer()
    
    # پردازش کالبک بر اساس نوع آن
    if callback_data == ADMIN_CALLBACK_STATS:
        # نمایش آمار
        await callback_query.delete_message()
        await stats_command(update, context)
        
    elif callback_data == ADMIN_CALLBACK_BROADCAST:
        # شروع فرآیند اعلان عمومی
        await callback_query.delete_message()
        await broadcast_command(update, context)
        
    elif callback_data == ADMIN_CALLBACK_USERS:
        # نمایش لیست کاربران
        await callback_query.delete_message()
        await users_command(update, context)
        
    elif callback_data == ADMIN_CALLBACK_PAYMENTS:
        # نمایش پرداخت‌ها
        await show_payments(update, context)
        
    elif callback_data == ADMIN_CALLBACK_SETTINGS:
        # نمایش تنظیمات ادمین
        await show_admin_settings(update, context)
        
    elif callback_data == ADMIN_CALLBACK_BACKUP:
        # پشتیبان‌گیری از پایگاه داده
        await create_database_backup(update, context)
        
    elif callback_data == ADMIN_CALLBACK_RELOAD:
        # بارگذاری مجدد تنظیمات
        await reload_settings(update, context)
        
    elif callback_data.startswith("broadcast:"):
        # پردازش کالبک‌های مربوط به اعلان عمومی
        action = callback_data.split(":")[1]
        
        if action in ('all', 'subscribers', 'active', 'new'):
            # انتخاب گروه هدف
            context.user_data['broadcast_target'] = action
            
            # ارسال پیام راهنما
            await callback_query.edit_message_text(
                text=f"📝 لطفاً متن اعلان خود را ارسال کنید:\n\n"
                    f"نکته: می‌توانید از فرمت HTML استفاده کنید. مثال:\n"
                    f"<b>متن پررنگ</b>\n"
                    f"<i>متن مورب</i>\n"
                    f"<a href='https://example.com'>لینک</a>"
            )
            
        elif action == 'confirm':
            # تأیید ارسال اعلان
            await callback_query.edit_message_text(
                text="🔄 در حال آماده‌سازی ارسال اعلان..."
            )
            
            # ارسال اعلان
            await send_broadcast_messages(update, context)
            
        elif action == 'cancel':
            # لغو فرآیند اعلان
            context.user_data['state'] = None
            context.user_data.pop('broadcast_target', None)
            context.user_data.pop('broadcast_message', None)
            context.user_data.pop('broadcast_users', None)
            
            await callback_query.edit_message_text(
                text="❌ فرآیند ارسال اعلان عمومی لغو شد."
            )
            
    elif callback_data == "admin:search_user":
        # شروع فرآیند جستجوی کاربر
        context.user_data['state'] = ADMIN_STATE_USER_SEARCH
        
        await callback_query.edit_message_text(
            text="🔍 جستجوی کاربر\n\n"
                "لطفاً شناسه کاربر یا نام کاربری را وارد کنید:"
        )
        
    elif callback_data == "admin:add_admin":
        # شروع فرآیند افزودن ادمین
        context.user_data['state'] = ADMIN_STATE_ADD_ADMIN
        
        await callback_query.edit_message_text(
            text="➕ افزودن ادمین جدید\n\n"
                "لطفاً شناسه کاربر یا نام کاربری کاربر مورد نظر را وارد کنید:"
        )
        
    elif callback_data == "admin:user_stats":
        # نمایش آمار تفصیلی کاربران
        await show_detailed_user_stats(update, context)
        
    elif callback_data == "admin:back":
        # بازگشت به منوی اصلی ادمین
        await callback_query.delete_message()
        await admin_command(update, context)

async def show_payments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    نمایش پرداخت‌های اخیر
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id)
    
    # دریافت آخرین پرداخت‌ها
    try:
        recent_payments = database.execute_query(
            "SELECT p.id, p.user_id, p.amount, p.currency, p.status, p.created_at, p.plan_name, "
            "u.first_name, u.last_name, u.username "
            "FROM payments p "
            "LEFT JOIN users u ON p.user_id = u.user_id "
            "ORDER BY p.created_at DESC LIMIT 10"
        )
    except Exception as e:
        logger.error(f"خطا در دریافت لیست پرداخت‌ها: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ خطا در دریافت لیست پرداخت‌ها: {str(e)}"
        )
        return
    
    # ساخت پیام
    payments_message = f"💰 پرداخت‌های اخیر\n\n"
    
    for p in recent_payments:
        created_date = p['created_at'].split('T')[0] if p['created_at'] else "نامشخص"
        status_emoji = "✅" if p['status'] == 'completed' else "🔄" if p['status'] == 'pending' else "❌"
        
        payments_message += f"{status_emoji} {p['amount']:,} {p['currency']}\n"
        payments_message += f"👤 {p['first_name']} {p['last_name'] or ''} (ID: {p['user_id']})\n"
        payments_message += f"📋 طرح: {p['plan_name'] or 'نامشخص'}\n"
        payments_message += f"📅 {created_date}\n\n"
    
    # ساخت دکمه‌های مدیریت پرداخت‌ها
    keyboard = [
        [
            InlineKeyboardButton("💹 آمار پرداخت‌ها", callback_data="admin:payment_stats"),
            InlineKeyboardButton("🔍 جستجوی پرداخت", callback_data="admin:search_payment")
        ],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام
    await context.bot.send_message(
        chat_id=chat_id,
        text=payments_message,
        reply_markup=reply_markup
    )
    
    logger.info(f"لیست پرداخت‌های اخیر برای کاربر {user.id} نمایش داده شد.")

async def show_admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    نمایش تنظیمات ادمین
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت تنظیمات از کانتکست
    config = context.bot_data.get('config', {})
    
    # ساخت پیام تنظیمات
    settings_message = f"⚙️ تنظیمات ادمین\n\n"
    
    # نمایش ادمین‌ها
    admin_ids = config.get('ADMIN_IDS', [])
    settings_message += f"👨‍💼 ادمین‌ها: {', '.join(map(str, admin_ids))}\n\n"
    
    # نمایش سایر تنظیمات
    settings_message += f"🌐 زبان پیش‌فرض: {config.get('DEFAULT_LANGUAGE', 'fa')}\n"
    settings_message += f"⏱ منطقه زمانی: {config.get('TIMEZONE', 'Asia/Tehran')}\n"
    settings_message += f"🔄 پشتیبان‌گیری خودکار: {'فعال' if config.get('BACKUP_ENABLED', True) else 'غیرفعال'}\n"
    settings_message += f"📊 آنالیتیکس: {'فعال' if config.get('ENABLE_ANALYTICS', False) else 'غیرفعال'}\n"
    settings_message += f"🤖 یادگیری ماشین: {'فعال' if config.get('ENABLE_ML', False) else 'غیرفعال'}\n"
    
    # ساخت دکمه‌های مدیریت تنظیمات
    keyboard = [
        [
            InlineKeyboardButton("🔃 بارگذاری مجدد", callback_data=ADMIN_CALLBACK_RELOAD),
            InlineKeyboardButton("➕ افزودن ادمین", callback_data="admin:add_admin")
        ],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام
    await context.bot.send_message(
        chat_id=chat_id,
        text=settings_message,
        reply_markup=reply_markup
    )
    
    logger.info(f"تنظیمات ادمین برای کاربر {user.id} نمایش داده شد.")

async def create_database_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    ایجاد پشتیبان از پایگاه داده
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id)
    
    # ایجاد مسیر پشتیبان
    now = get_current_datetime()
    backup_dir = os.path.join('data', 'backups', 'manual')
    os.makedirs(backup_dir, exist_ok=True)
    
    backup_file = os.path.join(
        backup_dir,
        f"backup_{now.strftime('%Y%m%d_%H%M%S')}.db"
    )
    
    # ایجاد پشتیبان
    try:
        success = database.backup_database(backup_file)
        
        if success:
            # ارسال پیام موفقیت
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ پشتیبان‌گیری با موفقیت انجام شد.\n\n"
                    f"📂 مسیر فایل: {backup_file}\n"
                    f"⏱ زمان: {now.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            logger.info(f"پشتیبان‌گیری از پایگاه داده توسط کاربر {user.id} انجام شد: {backup_file}")
        else:
            # ارسال پیام خطا
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ خطا در ایجاد پشتیبان از پایگاه داده."
            )
            logger.error(f"خطا در پشتیبان‌گیری از پایگاه داده توسط کاربر {user.id}")
            
    except Exception as e:
        logger.error(f"خطا در پشتیبان‌گیری: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ خطا در پشتیبان‌گیری: {str(e)}"
        )

async def reload_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    بارگذاری مجدد تنظیمات
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id)
    
    try:
        # فراخوانی تابع بارگذاری تنظیمات
        from core.config import load_config
        config = load_config()
        
        # به‌روزرسانی تنظیمات در کانتکست
        context.bot_data['config'] = config
        
        # بارگذاری مجدد زبان‌ها
        from utils.localization import reload
        reload()
        
        # ارسال پیام موفقیت
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ تنظیمات با موفقیت بارگذاری مجدد شدند."
        )
        
        logger.info(f"تنظیمات توسط کاربر {user.id} بارگذاری مجدد شدند.")
        
    except Exception as e:
        logger.error(f"خطا در بارگذاری مجدد تنظیمات: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ خطا در بارگذاری مجدد تنظیمات: {str(e)}"
        )

async def handle_admin_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    پردازش پیام‌های متنی برای ادمین‌ها
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        
    بازگشت:
        bool: True اگر پیام پردازش شده باشد، False در غیر این صورت
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    message_text = update.message.text
    
    # بررسی دسترسی ادمینی
    if not await check_admin_permission(update, context):
        return False
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # بررسی وضعیت ادمین
    admin_state = context.user_data.get('state', None)
    
    if admin_state == ADMIN_STATE_BROADCAST:
        # پردازش متن اعلان عمومی
        await handle_admin_broadcast(update, context, message_text)
        return True
        
    elif admin_state == ADMIN_STATE_USER_SEARCH:
        # پردازش جستجوی کاربر
        await handle_user_search(update, context, message_text)
        context.user_data['state'] = None
        return True
        
    elif admin_state == ADMIN_STATE_ADD_ADMIN:
        # پردازش افزودن ادمین جدید
        await handle_add_admin(update, context, message_text)
        context.user_data['state'] = None
        return True
    
    # اگر پیام پردازش نشده باشد
    return False

async def handle_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    """
    پردازش جستجوی کاربر
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        query: عبارت جستجو
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id)
    
    try:
        # تلاش برای تبدیل به شناسه عددی
        try:
            user_id = int(query)
            # جستجو بر اساس شناسه
            found_users = database.execute_query(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            )
        except ValueError:
            # جستجو بر اساس نام کاربری یا نام
            query = query.replace('@', '')  # حذف @ در صورت وجود
            found_users = database.execute_query(
                "SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ? OR last_name LIKE ? LIMIT 5",
                (f"%{query}%", f"%{query}%", f"%{query}%")
            )
    except Exception as e:
        logger.error(f"خطا در جستجوی کاربر: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ خطا در جستجوی کاربر: {str(e)}"
        )
        return
    
    if not found_users:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ کاربری با این مشخصات یافت نشد."
        )
        return
    
    # ساخت پیام برای نمایش کاربران یافت شده
    results_message = f"🔍 نتایج جستجو برای «{query}»:\n\n"
    
    for u in found_users:
        created_date = u['created_at'].split('T')[0] if u['created_at'] else "نامشخص"
        last_activity = u['last_activity'].split('T')[0] if u['last_activity'] else "نامشخص"
        
        results_message += f"👤 {u['first_name']} {u['last_name'] or ''}\n"
        results_message += f"🆔 {u['user_id']}\n"
        results_message += f"🌐 @{u['username'] or 'ندارد'}\n"
        results_message += f"🔐 ادمین: {'✅' if u['is_admin'] == 1 else '❌'}\n"
        results_message += f"🚫 مسدود: {'✅' if u['is_blocked'] == 1 else '❌'}\n"
        results_message += f"🗣 زبان: {u['language']}\n"
        results_message += f"📅 تاریخ عضویت: {created_date}\n"
        results_message += f"⏱ آخرین فعالیت: {last_activity}\n"
        
        # نمایش وضعیت اشتراک
        if u['subscription_plan'] and u['subscription_expiry']:
            expiry_date = u['subscription_expiry'].split('T')[0]
            results_message += f"💳 اشتراک {u['subscription_plan']} تا {expiry_date}\n"
        else:
            results_message += "💳 بدون اشتراک\n"
        
        results_message += "\n"
    
    # ساخت دکمه‌های عملیات کاربر (برای اولین کاربر یافت شده)
    first_user = found_users[0]
    user_id = first_user['user_id']
    is_admin = first_user['is_admin'] == 1
    is_blocked = first_user['is_blocked'] == 1
    
    keyboard = []
    
    # دکمه‌های مدیریت کاربر
    admin_action = "admin:remove_admin" if is_admin else "admin:make_admin"
    admin_text = "❌ حذف ادمین" if is_admin else "➕ ادمین کردن"
    
    block_action = "admin:unblock_user" if is_blocked else "admin:block_user"
    block_text = "✅ رفع مسدودیت" if is_blocked else "🚫 مسدود کردن"
    
    keyboard.append([
        InlineKeyboardButton(admin_text, callback_data=f"{admin_action}:{user_id}"),
        InlineKeyboardButton(block_text, callback_data=f"{block_action}:{user_id}")
    ])
    
    # دکمه‌های اطلاعات بیشتر
    keyboard.append([
        InlineKeyboardButton("📊 آمار کاربر", callback_data=f"admin:user_detail:{user_id}"),
        InlineKeyboardButton("💰 پرداخت‌ها", callback_data=f"admin:user_payments:{user_id}")
    ])
    
    # دکمه بازگشت
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام
    await context.bot.send_message(
        chat_id=chat_id,
        text=results_message,
        reply_markup=reply_markup
    )
    
    logger.info(f"جستجوی کاربر توسط {user.id} برای عبارت '{query}' انجام شد.")

async def handle_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    """
    پردازش افزودن ادمین جدید
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        query: شناسه یا نام کاربری
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id)
    
    # یافتن کاربر
    try:
        # تلاش برای تبدیل به شناسه عددی
        try:
            user_id = int(query)
            # جستجو بر اساس شناسه
            found_user = database.execute_query(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            )
        except ValueError:
            # جستجو بر اساس نام کاربری
            query = query.replace('@', '')  # حذف @ در صورت وجود
            found_user = database.execute_query(
                "SELECT * FROM users WHERE username = ?",
                (query,)
            )
    except Exception as e:
        logger.error(f"خطا در جستجوی کاربر: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ خطا در جستجوی کاربر: {str(e)}"
        )
        return
    
    if not found_user:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ کاربری با این مشخصات یافت نشد."
        )
        return
    
    # دریافت اطلاعات کاربر
    found_user = found_user[0]
    target_user_id = found_user['user_id']
    
    if found_user['is_admin'] == 1:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ کاربر {found_user['first_name']} (ID: {target_user_id}) در حال حاضر ادمین است!"
        )
        return
    
    # ارتقا به ادمین
    try:
        database.execute_query(
            "UPDATE users SET is_admin = 1 WHERE user_id = ?",
            (target_user_id,)
        )
        
        # به‌روزرسانی لیست ادمین‌ها در تنظیمات
        config = context.bot_data.get('config', {})
        admin_ids = set(config.get('ADMIN_IDS', []))
        admin_ids.add(target_user_id)
        config['ADMIN_IDS'] = list(admin_ids)
        context.bot_data['config'] = config
        
        # ارسال پیام موفقیت
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ کاربر {found_user['first_name']} (ID: {target_user_id}) با موفقیت به ادمین ارتقا یافت."
        )
        
        # ارسال اعلان به کاربر جدید
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🎉 تبریک! شما به عنوان ادمین ربات منصوب شدید.\n"
                    "می‌توانید با ارسال دستور /admin به پنل مدیریت دسترسی پیدا کنید."
            )
        except Exception:
            logger.warning(f"خطا در ارسال اعلان به ادمین جدید {target_user_id}")
        
        logger.info(f"کاربر {target_user_id} توسط {user.id} به ادمین ارتقا یافت.")
        
    except Exception as e:
        logger.error(f"خطا در ارتقا به ادمین: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ خطا در ارتقا به ادمین: {str(e)}"
        )

async def show_detailed_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    نمایش آمار تفصیلی کاربران
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id, duration=2.0)
    
    # دریافت آمار کاربران
    try:
        # تعداد کل کاربران
        total_users = database.execute_query("SELECT COUNT(*) as count FROM users")[0]['count']
        
        # کاربران فعال (7 روز اخیر)
        active_users = database.execute_query(
            "SELECT COUNT(*) as count FROM users WHERE last_activity > ?",
            ((get_current_datetime() - timedelta(days=7)).isoformat(),)
        )[0]['count']
        
        # کاربران جدید (7 روز اخیر)
        new_users = database.execute_query(
            "SELECT COUNT(*) as count FROM users WHERE created_at > ?",
            ((get_current_datetime() - timedelta(days=7)).isoformat(),)
        )[0]['count']
        
        # کاربران مسدود شده
        blocked_users = database.execute_query(
            "SELECT COUNT(*) as count FROM users WHERE is_blocked = 1"
        )[0]['count']
        
        # ادمین‌ها
        admin_users = database.execute_query(
            "SELECT COUNT(*) as count FROM users WHERE is_admin = 1"
        )[0]['count']
        
        # آمار اشتراک‌ها
        active_subscriptions = database.execute_query(
            "SELECT COUNT(*) as count FROM users WHERE subscription_expiry > ?",
            (get_current_datetime().isoformat(),)
        )[0]['count']
        
        # توزیع طرح‌های اشتراک
        subscription_stats = database.execute_query(
            "SELECT subscription_plan, COUNT(*) as count FROM users "
            "WHERE subscription_expiry > ? AND subscription_plan IS NOT NULL "
            "GROUP BY subscription_plan ORDER BY count DESC",
            (get_current_datetime().isoformat(),)
        )
        
        # آمار رشد روزانه (۷ روز اخیر)
        growth_stats = []
        for days_ago in range(7, 0, -1):
            date = (get_current_datetime() - timedelta(days=days_ago)).date()
            next_date = (get_current_datetime() - timedelta(days=days_ago-1)).date()
            
            count = database.execute_query(
                "SELECT COUNT(*) as count FROM users WHERE DATE(created_at) = ?",
                (date.isoformat(),)
            )[0]['count']
            
            growth_stats.append((date.isoformat(), count))
        
    except Exception as e:
        logger.error(f"خطا در دریافت آمار تفصیلی کاربران: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ خطا در دریافت آمار: {str(e)}"
        )
        return
    
    # ساخت پیام آمار
    stats_message = f"📊 آمار تفصیلی کاربران\n\n"
    
    stats_message += f"👥 کاربران:\n"
    stats_message += f"- کل: {total_users:,}\n"
    stats_message += f"- فعال (۷ روز): {active_users:,} ({active_users/total_users*100:.1f}%)\n"
    stats_message += f"- جدید (۷ روز): {new_users:,}\n"
    stats_message += f"- مسدود شده: {blocked_users:,}\n"
    stats_message += f"- ادمین‌ها: {admin_users:,}\n\n"
    
    stats_message += f"💳 اشتراک‌ها:\n"
    stats_message += f"- فعال: {active_subscriptions:,} ({active_subscriptions/total_users*100:.1f}%)\n"
    for plan in subscription_stats:
        plan_name = plan['subscription_plan'] or "نامشخص"
        plan_count = plan['count']
        stats_message += f"- {plan_name}: {plan_count:,} ({plan_count/active_subscriptions*100:.1f}%)\n"
    
    stats_message += f"\n📈 رشد روزانه (۷ روز اخیر):\n"
    for date, count in growth_stats:
        stats_message += f"- {date}: {count:,} کاربر جدید\n"
    
    # اضافه کردن زمان گزارش
    stats_message += f"\n⏱ زمان گزارش: {get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # ساخت دکمه‌های مدیریت
    keyboard = [
        [
            InlineKeyboardButton("📥 دریافت فایل CSV", callback_data="admin:export_users"),
            InlineKeyboardButton("🔄 به‌روزرسانی", callback_data="admin:refresh_stats")
        ],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام
    await context.bot.send_message(
        chat_id=chat_id,
        text=stats_message,
        reply_markup=reply_markup
    )
    
    logger.info(f"آمار تفصیلی کاربران برای {user.id} نمایش داده شد.")

async def handle_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش عملیات‌های مدیریتی روی کاربران (مسدود کردن، ارتقا به ادمین و...)
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    callback_query = update.callback_query
    user = callback_query.from_user
    chat_id = callback_query.message.chat_id
    callback_data = callback_query.data
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # پاسخ به کالبک
    await callback_query.answer()
    
    try:
        # استخراج عملیات و شناسه کاربر
        action, target_user_id = callback_data.split(':', 2)[1:]
        target_user_id = int(target_user_id)
        
        # دریافت اطلاعات کاربر هدف
        target_user = database.get_user(target_user_id)
        
        if not target_user:
            await callback_query.edit_message_text(
                text="❌ کاربر مورد نظر یافت نشد!"
            )
            return
        
        # انجام عملیات مورد نظر
        if action == "make_admin":
            # ارتقا به ادمین
            database.execute_query(
                "UPDATE users SET is_admin = 1 WHERE user_id = ?",
                (target_user_id,)
            )
            
            # به‌روزرسانی لیست ادمین‌ها در تنظیمات
            config = context.bot_data.get('config', {})
            admin_ids = set(config.get('ADMIN_IDS', []))
            admin_ids.add(target_user_id)
            config['ADMIN_IDS'] = list(admin_ids)
            context.bot_data['config'] = config
            
            success_message = f"✅ کاربر {target_user['first_name']} با موفقیت به ادمین ارتقا یافت."
            
            # ارسال اعلان به کاربر جدید
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="🎉 تبریک! شما به عنوان ادمین ربات منصوب شدید.\n"
                         "می‌توانید با ارسال دستور /admin به پنل مدیریت دسترسی پیدا کنید."
                )
            except Exception:
                logger.warning(f"خطا در ارسال اعلان به ادمین جدید {target_user_id}")
            
        elif action == "remove_admin":
            # حذف از ادمین
            database.execute_query(
                "UPDATE users SET is_admin = 0 WHERE user_id = ?",
                (target_user_id,)
            )
            
            # به‌روزرسانی لیست ادمین‌ها در تنظیمات
            config = context.bot_data.get('config', {})
            admin_ids = set(config.get('ADMIN_IDS', []))
            admin_ids.discard(target_user_id)
            config['ADMIN_IDS'] = list(admin_ids)
            context.bot_data['config'] = config
            
            success_message = f"✅ کاربر {target_user['first_name']} از لیست ادمین‌ها حذف شد."
            
            # ارسال اعلان به کاربر 
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="⚠️ دسترسی‌های ادمین شما لغو شده است."
                )
            except Exception:
                logger.warning(f"خطا در ارسال اعلان به کاربر {target_user_id}")
            
        elif action == "block_user":
            # مسدود کردن کاربر
            database.execute_query(
                "UPDATE users SET is_blocked = 1 WHERE user_id = ?",
                (target_user_id,)
            )
            
            success_message = f"✅ کاربر {target_user['first_name']} مسدود شد."
            
            # ارسال اعلان به کاربر
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="⛔ دسترسی شما به ربات مسدود شده است.\n"
                         "برای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
                )
            except Exception:
                logger.warning(f"خطا در ارسال اعلان به کاربر مسدود شده {target_user_id}")
            
        elif action == "unblock_user":
            # رفع مسدودیت کاربر
            database.execute_query(
                "UPDATE users SET is_blocked = 0 WHERE user_id = ?",
                (target_user_id,)
            )
            
            success_message = f"✅ مسدودیت کاربر {target_user['first_name']} رفع شد."
            
            # ارسال اعلان به کاربر
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="🎉 دسترسی شما به ربات مجدداً فعال شده است.\n"
                         "خوش آمدید!"
                )
            except Exception:
                logger.warning(f"خطا در ارسال اعلان به کاربر رفع مسدودیت شده {target_user_id}")
            
        elif action == "delete_user":
            # حذف کاربر (فقط تغییر وضعیت - حذف فیزیکی انجام نمی‌شود)
            database.execute_query(
                "UPDATE users SET is_blocked = 1, is_deleted = 1 WHERE user_id = ?",
                (target_user_id,)
            )
            
            success_message = f"✅ کاربر {target_user['first_name']} به عنوان حذف شده علامت‌گذاری شد."
            
            # ارسال اعلان به کاربر
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="⛔ حساب کاربری شما در ربات حذف شده است."
                )
            except Exception:
                logger.warning(f"خطا در ارسال اعلان به کاربر حذف شده {target_user_id}")
        
        elif action == "user_detail":
            # نمایش جزئیات کاربر
            await show_user_details(update, context, target_user_id)
            return
            
        elif action == "user_payments":
            # نمایش تاریخچه پرداخت‌های کاربر
            await show_user_payments(update, context, target_user_id)
            return
        
        elif action == "extend_subscription":
            # تمدید دستی اشتراک
            await show_extend_subscription_form(update, context, target_user_id)
            return
            
        else:
            success_message = "⚠️ عملیات نامشخص!"
        
        # ارسال پیام موفقیت
        await callback_query.edit_message_text(
            text=success_message
        )
        
        logger.info(f"عملیات {action} روی کاربر {target_user_id} توسط {user.id} انجام شد.")
        
    except Exception as e:
        logger.error(f"خطا در انجام عملیات روی کاربر: {str(e)}")
        await callback_query.edit_message_text(
            text=f"❌ خطا در انجام عملیات: {str(e)}"
        )

async def show_user_details(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """
    نمایش جزئیات کاربر
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        user_id: شناسه کاربر
    """
    callback_query = update.callback_query
    admin_user = callback_query.from_user
    chat_id = callback_query.message.chat_id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id)
    
    # دریافت اطلاعات کاربر
    user_data = database.get_user(user_id)
    
    if not user_data:
        await callback_query.edit_message_text(
            text="❌ کاربر مورد نظر یافت نشد!"
        )
        return
    
    # دریافت آمار و اطلاعات کاربر
    try:
        # تعداد پرداخت‌ها
        payment_count = database.execute_query(
            "SELECT COUNT(*) as count FROM payments WHERE user_id = ?",
            (user_id,)
        )[0]['count']
        
        # مجموع پرداخت‌های موفق
        total_payments = database.execute_query(
            "SELECT SUM(amount) as total FROM payments WHERE user_id = ? AND status = 'completed'",
            (user_id,)
        )[0]['total'] or 0
        
        # تاریخ آخرین فعالیت
        last_activity = user_data.get('last_activity', '').split('T')[0] if user_data.get('last_activity') else "نامشخص"
        
        # تاریخ عضویت
        join_date = user_data.get('created_at', '').split('T')[0] if user_data.get('created_at') else "نامشخص"
        
        # اطلاعات اشتراک
        subscription_plan = user_data.get('subscription_plan', None)
        subscription_expiry = user_data.get('subscription_expiry', None)
        
        # بررسی وضعیت اشتراک
        has_active_subscription = False
        if subscription_expiry:
            expiry_date = datetime.fromisoformat(subscription_expiry.replace('Z', '+00:00'))
            has_active_subscription = expiry_date > datetime.now(timezone.utc)
        
    except Exception as e:
        logger.error(f"خطا در دریافت اطلاعات کاربر: {str(e)}")
        await callback_query.edit_message_text(
            text=f"❌ خطا در دریافت اطلاعات کاربر: {str(e)}"
        )
        return
    
    # ساخت پیام اطلاعات کاربر
    user_message = f"👤 اطلاعات کاربر\n\n"
    user_message += f"🔹 نام: {user_data.get('first_name', '')} {user_data.get('last_name', '') or ''}\n"
    user_message += f"🔹 شناسه: {user_id}\n"
    user_message += f"🔹 نام کاربری: {('@' + user_data.get('username')) if user_data.get('username') else 'ندارد'}\n"
    user_message += f"🔹 زبان: {user_data.get('language', 'fa')}\n"
    user_message += f"🔹 تاریخ عضویت: {join_date}\n"
    user_message += f"🔹 آخرین فعالیت: {last_activity}\n"
    user_message += f"🔹 ادمین: {'✅' if user_data.get('is_admin', 0) == 1 else '❌'}\n"
    user_message += f"🔹 مسدود: {'✅' if user_data.get('is_blocked', 0) == 1 else '❌'}\n\n"
    
    user_message += f"💳 اشتراک:\n"
    if has_active_subscription and subscription_plan:
        expiry_date = subscription_expiry.split('T')[0]
        user_message += f"🔹 طرح: {subscription_plan}\n"
        user_message += f"🔹 تاریخ انقضا: {expiry_date}\n"
        user_message += f"🔹 وضعیت: فعال ✅\n"
    else:
        user_message += f"🔹 بدون اشتراک فعال\n"
    
    user_message += f"\n💰 پرداخت‌ها:\n"
    user_message += f"🔹 تعداد: {payment_count}\n"
    user_message += f"🔹 مجموع: {total_payments:,} تومان\n"
    
    # ساخت دکمه‌های مدیریت کاربر
    is_admin = user_data.get('is_admin', 0) == 1
    is_blocked = user_data.get('is_blocked', 0) == 1
    
    keyboard = []
    
    # دکمه‌های مدیریت کاربر
    admin_action = "admin:remove_admin" if is_admin else "admin:make_admin"
    admin_text = "❌ حذف ادمین" if is_admin else "➕ ادمین کردن"
    
    block_action = "admin:unblock_user" if is_blocked else "admin:block_user"
    block_text = "✅ رفع مسدودیت" if is_blocked else "🚫 مسدود کردن"
    
    keyboard.append([
        InlineKeyboardButton(admin_text, callback_data=f"{admin_action}:{user_id}"),
        InlineKeyboardButton(block_text, callback_data=f"{block_action}:{user_id}")
    ])
    
    # دکمه‌های اشتراک و پرداخت
    keyboard.append([
        InlineKeyboardButton("➕ تمدید اشتراک", callback_data=f"admin:extend_subscription:{user_id}"),
        InlineKeyboardButton("💰 پرداخت‌ها", callback_data=f"admin:user_payments:{user_id}")
    ])
    
    # دکمه‌های ارتباط و سایر عملیات
    keyboard.append([
        InlineKeyboardButton("📝 ارسال پیام", callback_data=f"admin:message_user:{user_id}"),
        InlineKeyboardButton("❌ حذف کاربر", callback_data=f"admin:delete_user:{user_id}")
    ])
    
    # دکمه بازگشت
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام
    await callback_query.edit_message_text(
        text=user_message,
        reply_markup=reply_markup
    )
    
    logger.info(f"اطلاعات کاربر {user_id} برای ادمین {admin_user.id} نمایش داده شد.")

async def show_user_payments(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """
    نمایش تاریخچه پرداخت‌های کاربر
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        user_id: شناسه کاربر
    """
    callback_query = update.callback_query
    admin_user = callback_query.from_user
    chat_id = callback_query.message.chat_id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id)
    
    # دریافت اطلاعات کاربر
    user_data = database.get_user(user_id)
    
    if not user_data:
        await callback_query.edit_message_text(
            text="❌ کاربر مورد نظر یافت نشد!"
        )
        return
    
    # دریافت تاریخچه پرداخت‌ها
    try:
        payments = database.execute_query(
            "SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (user_id,)
        )
    except Exception as e:
        logger.error(f"خطا در دریافت تاریخچه پرداخت‌ها: {str(e)}")
        await callback_query.edit_message_text(
            text=f"❌ خطا در دریافت تاریخچه پرداخت‌ها: {str(e)}"
        )
        return
    
    # ساخت پیام تاریخچه پرداخت‌ها
    user_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '') or ''}"
    
    payments_message = f"💰 تاریخچه پرداخت‌های کاربر\n\n"
    payments_message += f"👤 {user_name} (ID: {user_id})\n\n"
    
    if not payments:
        payments_message += "هیچ پرداختی یافت نشد."
    else:
        # محاسبه آمار کلی
        total_amount = sum(p['amount'] for p in payments if p['status'] == 'completed')
        successful_count = sum(1 for p in payments if p['status'] == 'completed')
        failed_count = sum(1 for p in payments if p['status'] == 'failed')
        pending_count = sum(1 for p in payments if p['status'] == 'pending')
        
        payments_message += f"📊 آمار کلی:\n"
        payments_message += f"- تعداد کل: {len(payments)}\n"
        payments_message += f"- موفق: {successful_count}\n"
        payments_message += f"- ناموفق: {failed_count}\n"
        payments_message += f"- در انتظار: {pending_count}\n"
        payments_message += f"- مجموع پرداخت‌های موفق: {total_amount:,} تومان\n\n"
        
        payments_message += f"📜 تاریخچه پرداخت‌ها:\n\n"
        
        for p in payments:
            created_date = p['created_at'].split('T')[0] if p['created_at'] else "نامشخص"
            status_emoji = "✅" if p['status'] == 'completed' else "🔄" if p['status'] == 'pending' else "❌"
            
            payments_message += f"{status_emoji} {p['amount']:,} {p['currency']}\n"
            payments_message += f"🆔 شناسه پرداخت: {p['id']}\n"
            payments_message += f"📋 طرح: {p['plan_name'] or 'نامشخص'}\n"
            payments_message += f"📝 توضیحات: {p['description'] or '-'}\n"
            payments_message += f"📅 تاریخ: {created_date}\n\n"
    
    # ساخت دکمه‌های مدیریت
    keyboard = [
        [
            InlineKeyboardButton("➕ افزودن پرداخت", callback_data=f"admin:add_payment:{user_id}"),
            InlineKeyboardButton("👤 پروفایل کاربر", callback_data=f"admin:user_detail:{user_id}")
        ],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام
    await callback_query.edit_message_text(
        text=payments_message,
        reply_markup=reply_markup
    )
    
    logger.info(f"تاریخچه پرداخت‌های کاربر {user_id} برای ادمین {admin_user.id} نمایش داده شد.")

async def show_extend_subscription_form(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """
    نمایش فرم تمدید اشتراک
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        user_id: شناسه کاربر
    """
    callback_query = update.callback_query
    admin_user = callback_query.from_user
    chat_id = callback_query.message.chat_id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    config = context.bot_data.get('config', {})
    
    # دریافت اطلاعات کاربر
    user_data = database.get_user(user_id)
    
    if not user_data:
        await callback_query.edit_message_text(
            text="❌ کاربر مورد نظر یافت نشد!"
        )
        return
    
    # دریافت طرح‌های اشتراک
    subscription_plans = config.get('SUBSCRIPTION_PLANS', {})
    
    # ساخت پیام
    user_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '') or ''}"
    
    form_message = f"➕ تمدید اشتراک کاربر\n\n"
    form_message += f"👤 {user_name} (ID: {user_id})\n\n"
    
    # بررسی اشتراک فعلی
    subscription_plan = user_data.get('subscription_plan', None)
    subscription_expiry = user_data.get('subscription_expiry', None)
    
    if subscription_plan and subscription_expiry:
        expiry_date = datetime.fromisoformat(subscription_expiry.replace('Z', '+00:00'))
        is_active = expiry_date > datetime.now(timezone.utc)
        
        form_message += f"💳 اشتراک فعلی:\n"
        form_message += f"- طرح: {subscription_plan}\n"
        form_message += f"- تاریخ انقضا: {subscription_expiry.split('T')[0]}\n"
        form_message += f"- وضعیت: {'فعال ✅' if is_active else 'منقضی شده ❌'}\n\n"
    else:
        form_message += f"💳 کاربر اشتراک فعالی ندارد.\n\n"
    
    form_message += f"📋 لطفاً طرح و مدت تمدید را انتخاب کنید:"
    
    # ساخت دکمه‌های انتخاب طرح
    keyboard = []
    
    for plan_name, plan_data in subscription_plans.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{plan_name} - {plan_data.get('duration', 30)} روز", 
                callback_data=f"admin:do_extend:{user_id}:{plan_name}:30"
            )
        ])
    
    # اضافه کردن دکمه‌های مدت زمان سفارشی
    custom_durations = [60, 90, 180, 365]
    
    if subscription_plans:
        default_plan = list(subscription_plans.keys())[0]
        duration_buttons = []
        
        for duration in custom_durations:
            duration_buttons.append(
                InlineKeyboardButton(
                    f"{duration} روز", 
                    callback_data=f"admin:do_extend:{user_id}:{default_plan}:{duration}"
                )
            )
        
        # قرار دادن دکمه‌های مدت زمان در یک ردیف
        keyboard.append(duration_buttons)
    
    # دکمه بازگشت
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"admin:user_detail:{user_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام
    await callback_query.edit_message_text(
        text=form_message,
        reply_markup=reply_markup
    )
    
    logger.info(f"فرم تمدید اشتراک برای کاربر {user_id} توسط ادمین {admin_user.id} نمایش داده شد.")

async def handle_extend_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش تمدید اشتراک کاربر
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    callback_query = update.callback_query
    admin_user = callback_query.from_user
    chat_id = callback_query.message.chat_id
    callback_data = callback_query.data
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    config = context.bot_data.get('config', {})
    
    # پاسخ به کالبک
    await callback_query.answer()
    
    try:
        # استخراج اطلاعات از کالبک
        _, user_id, plan_name, duration = callback_data.split(':', 3)
        user_id = int(user_id)
        duration = int(duration)
        
        # دریافت اطلاعات کاربر
        user_data = database.get_user(user_id)
        
        if not user_data:
            await callback_query.edit_message_text(
                text="❌ کاربر مورد نظر یافت نشد!"
            )
            return
        
        # دریافت اطلاعات طرح
        subscription_plans = config.get('SUBSCRIPTION_PLANS', {})
        plan_data = subscription_plans.get(plan_name, {})
        
        if not plan_data:
            await callback_query.edit_message_text(
                text="❌ طرح اشتراک مورد نظر یافت نشد!"
            )
            return
        
        # محاسبه تاریخ انقضای جدید
        current_expiry = user_data.get('subscription_expiry', None)
        
        if current_expiry:
            # تبدیل به datetime
            expiry_date = datetime.fromisoformat(current_expiry.replace('Z', '+00:00'))
            
            # اگر اشتراک منقضی شده، از تاریخ امروز شروع می‌کنیم
            if expiry_date < datetime.now(timezone.utc):
                new_expiry = datetime.now(timezone.utc) + timedelta(days=duration)
            else:
                # اگر اشتراک فعال است، به تاریخ انقضای فعلی اضافه می‌کنیم
                new_expiry = expiry_date + timedelta(days=duration)
        else:
            # اگر اشتراکی وجود ندارد، از امروز شروع می‌کنیم
            new_expiry = datetime.now(timezone.utc) + timedelta(days=duration)
        
        # محاسبه قیمت طرح بر اساس مدت
        base_price = plan_data.get('price', 0)
        base_duration = plan_data.get('duration', 30)
        
        price = (base_price / base_duration) * duration
        
        # به‌روزرسانی اشتراک کاربر
        database.execute_query(
            "UPDATE users SET subscription_plan = ?, subscription_expiry = ? WHERE user_id = ?",
            (plan_name, new_expiry.isoformat(), user_id)
        )
        
        # ثبت پرداخت دستی
        payment_id = database.add_payment(
            user_id=user_id,
            amount=price,
            currency='IRR',
            gateway='manual_admin',
            reference_id=f"manual_{int(time.time())}",
            plan_name=plan_name,
            description=f"تمدید دستی اشتراک {plan_name} به مدت {duration} روز توسط ادمین"
        )
        
        # به‌روزرسانی وضعیت پرداخت به تکمیل شده
        database.update_payment_status(payment_id, 'completed')
        
        # ارسال اعلان به کاربر
        user_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '') or ''}"
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ اشتراک شما تمدید شد!\n\n"
                     f"📋 طرح: {plan_name}\n"
                     f"⏱ مدت: {duration} روز\n"
                     f"📅 تاریخ انقضا: {new_expiry.strftime('%Y-%m-%d')}\n\n"
                     f"این تمدید توسط مدیر سیستم انجام شده است."
            )
        except Exception as e:
            logger.warning(f"خطا در ارسال اعلان تمدید اشتراک به کاربر {user_id}: {str(e)}")
        
        # ارسال پیام موفقیت به ادمین
        success_message = f"✅ اشتراک کاربر با موفقیت تمدید شد.\n\n"
        success_message += f"👤 کاربر: {user_name}\n"
        success_message += f"📋 طرح: {plan_name}\n"
        success_message += f"⏱ مدت: {duration} روز\n"
        success_message += f"📅 تاریخ انقضای جدید: {new_expiry.strftime('%Y-%m-%d')}\n"
        success_message += f"💰 مبلغ: {price:,} تومان\n"
        success_message += f"🧾 شناسه پرداخت: {payment_id}"
        
        await callback_query.edit_message_text(
            text=success_message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 بازگشت به پروفایل کاربر", callback_data=f"admin:user_detail:{user_id}")]
            ])
        )
        
        logger.info(f"اشتراک کاربر {user_id} توسط ادمین {admin_user.id} تمدید شد. "
                   f"طرح: {plan_name}, مدت: {duration} روز")
        
    except Exception as e:
        logger.error(f"خطا در تمدید اشتراک: {str(e)}")
        await callback_query.edit_message_text(
            text=f"❌ خطا در تمدید اشتراک: {str(e)}"
        )

async def export_users_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    استخراج اطلاعات کاربران به صورت فایل CSV
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    callback_query = update.callback_query
    admin_user = callback_query.from_user
    chat_id = callback_query.message.chat_id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # پاسخ به کالبک
    await callback_query.answer()
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id, duration=2.0)
    
    # ارسال پیام در حال پردازش
    status_message = await callback_query.edit_message_text(
        text="🔄 در حال استخراج اطلاعات کاربران...\n\n"
             "لطفاً صبر کنید."
    )
    
    try:
        # دریافت اطلاعات کاربران
        users = database.execute_query(
            "SELECT user_id, first_name, last_name, username, language, "
            "is_admin, is_blocked, created_at, last_activity, "
            "subscription_plan, subscription_expiry "
            "FROM users ORDER BY created_at DESC"
        )
        
        if not users:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message.message_id,
                text="⚠️ هیچ کاربری یافت نشد!"
            )
            return
        
        # ساخت محتوای فایل CSV
        import csv
        import io
        
        csv_file = io.StringIO()
        csv_writer = csv.writer(csv_file)
        
        # نوشتن سرستون‌ها
        csv_writer.writerow([
            "شناسه کاربر", "نام", "نام خانوادگی", "نام کاربری", "زبان",
            "ادمین", "مسدود", "تاریخ عضویت", "آخرین فعالیت",
            "طرح اشتراک", "تاریخ انقضای اشتراک"
        ])
        
        # نوشتن داده‌ها
        for u in users:
            created_date = u['created_at'].split('T')[0] if u['created_at'] else ""
            last_activity = u['last_activity'].split('T')[0] if u['last_activity'] else ""
            expiry_date = u['subscription_expiry'].split('T')[0] if u['subscription_expiry'] else ""
            
            csv_writer.writerow([
                u['user_id'],
                u['first_name'],
                u['last_name'] or "",
                u['username'] or "",
                u['language'],
                "✓" if u['is_admin'] == 1 else "",
                "✓" if u['is_blocked'] == 1 else "",
                created_date,
                last_activity,
                u['subscription_plan'] or "",
                expiry_date
            ])
        
        # تبدیل به بایت‌ها
        csv_bytes = csv_file.getvalue().encode('utf-8-sig')  # با BOM برای پشتیبانی از کاراکترهای فارسی در اکسل
        
        # ساخت فایل در حافظه
        file = io.BytesIO(csv_bytes)
        file.name = f"users_{get_current_datetime().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # ارسال فایل
        await context.bot.send_document(
            chat_id=chat_id,
            document=file,
            caption=f"📊 فایل اطلاعات کاربران\n"
                   f"📅 تاریخ: {get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}\n"
                   f"👥 تعداد کاربران: {len(users)}"
        )
        
        # به‌روزرسانی پیام وضعیت
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message.message_id,
            text="✅ فایل اطلاعات کاربران با موفقیت ایجاد و ارسال شد."
        )
        
        logger.info(f"فایل اطلاعات کاربران برای ادمین {admin_user.id} ایجاد و ارسال شد.")
        
    except Exception as e:
        logger.error(f"خطا در استخراج اطلاعات کاربران: {str(e)}")
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message.message_id,
            text=f"❌ خطا در استخراج اطلاعات کاربران: {str(e)}"
        )

async def view_system_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    نمایش لاگ‌های سیستم
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    # بررسی دسترسی ادمینی
    if not await check_admin_permission(update, context):
        return
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id)
    
    # مسیر فایل‌های لاگ
    log_dir = 'logs'
    log_file = os.path.join(log_dir, 'telegram_bot.log')
    error_log_file = os.path.join(log_dir, 'error.log')
    
    # بررسی وجود فایل‌های لاگ
    if not os.path.exists(log_file) and not os.path.exists(error_log_file):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ فایل‌های لاگ یافت نشدند!"
        )
        return
    
    # خواندن آخرین خطوط لاگ
    logs = []
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                # خواندن 100 خط آخر
                lines = f.readlines()
                logs.extend(lines[-100:])
        except Exception as e:
            logger.error(f"خطا در خواندن فایل لاگ: {str(e)}")
            logs.append(f"خطا در خواندن فایل لاگ: {str(e)}\n")
    
    if os.path.exists(error_log_file):
        try:
            with open(error_log_file, 'r', encoding='utf-8') as f:
                # خواندن 50 خط آخر
                lines = f.readlines()
                logs.extend(lines[-50:])
        except Exception as e:
            logger.error(f"خطا در خواندن فایل لاگ خطا: {str(e)}")
            logs.append(f"خطا در خواندن فایل لاگ خطا: {str(e)}\n")
    
    # مرتب‌سازی بر اساس تاریخ
    logs.sort()
    
    # ارسال لاگ‌ها (حداکثر 20 خط آخر)
    logs_text = "📋 آخرین لاگ‌های سیستم:\n\n"
    logs_text += "".join(logs[-20:])
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=logs_text[:4000]  # محدودیت طول پیام تلگرام
    )
    
    # ارسال فایل‌های لاگ
    try:
        if os.path.exists(log_file):
            await context.bot.send_document(
                chat_id=chat_id,
                document=open(log_file, 'rb'),
                caption="📋 فایل لاگ اصلی سیستم"
            )
        
        if os.path.exists(error_log_file):
            await context.bot.send_document(
                chat_id=chat_id,
                document=open(error_log_file, 'rb'),
                caption="⚠️ فایل لاگ خطاهای سیستم"
            )
    except Exception as e:
        logger.error(f"خطا در ارسال فایل‌های لاگ: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ خطا در ارسال فایل‌های لاگ: {str(e)}"
        )
    
    logger.info(f"لاگ‌های سیستم برای ادمین {user.id} نمایش داده شد.")

async def system_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش دستور /status
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    # بررسی دسترسی ادمینی
    if not await check_admin_permission(update, context):
        return
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت پایگاه داده از کانتکست
    database: Database = context.bot_data.get('database')
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id, duration=2.0)
    
    # جمع‌آوری اطلاعات وضعیت سیستم
    import platform
    import psutil
    
    # اطلاعات سیستم عامل
    system_info = {
        'os': platform.system(),
        'version': platform.version(),
        'python': platform.python_version(),
        'machine': platform.machine()
    }
    
    # اطلاعات منابع سیستم
    cpu_percent = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # اطلاعات پروسه فعلی
    process = psutil.Process()
    process_info = {
        'cpu_percent': process.cpu_percent(interval=0.5),
        'memory_percent': process.memory_percent(),
        'threads': process.num_threads(),
        'uptime': time.time() - process.create_time()
    }
    
    # اطلاعات پایگاه داده
    db_size = 0
    if os.path.exists(database.db_path):
        db_size = os.path.getsize(database.db_path)
    
    # اطلاعات فایل‌های لاگ
    log_dir = 'logs'
    log_sizes = {}
    if os.path.exists(log_dir):
        for file in os.listdir(log_dir):
            if file.endswith('.log'):
                log_sizes[file] = os.path.getsize(os.path.join(log_dir, file))
    
    # ساخت پیام وضعیت
    status_message = f"🖥️ وضعیت سیستم\n\n"
    
    status_message += f"⚙️ سیستم عامل: {system_info['os']} {system_info['version']}\n"
    status_message += f"🐍 نسخه پایتون: {system_info['python']}\n"
    status_message += f"💻 معماری: {system_info['machine']}\n\n"
    
    status_message += f"📊 منابع سیستم:\n"
    status_message += f"- CPU: {cpu_percent}%\n"
    status_message += f"- حافظه: {memory.percent}% ({memory.used / (1024**3):.1f} GB از {memory.total / (1024**3):.1f} GB)\n"
    status_message += f"- دیسک: {disk.percent}% ({disk.used / (1024**3):.1f} GB از {disk.total / (1024**3):.1f} GB)\n\n"
    
    status_message += f"🤖 منابع پروسه ربات:\n"
    status_message += f"- CPU: {process_info['cpu_percent']}%\n"
    status_message += f"- حافظه: {process_info['memory_percent']:.2f}%\n"
    status_message += f"- تعداد نخ‌ها: {process_info['threads']}\n"
    
    days, remainder = divmod(process_info['uptime'], 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{int(days)} روز, {int(hours)} ساعت, {int(minutes)} دقیقه"
    status_message += f"- زمان کارکرد: {uptime_str}\n\n"
    
    status_message += f"💾 پایگاه داده:\n"
    status_message += f"- مسیر: {database.db_path}\n"
    status_message += f"- حجم: {db_size / (1024**2):.2f} MB\n\n"
    
    if log_sizes:
        status_message += f"📋 فایل‌های لاگ:\n"
        for file, size in log_sizes.items():
            status_message += f"- {file}: {size / 1024:.2f} KB\n"
    
    # اضافه کردن تاریخ گزارش
    status_message += f"\n⏱ زمان گزارش: {get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # ساخت دکمه‌های مدیریت
    keyboard = [
        [
            InlineKeyboardButton("🔄 به‌روزرسانی", callback_data="admin:refresh_status"),
            InlineKeyboardButton("📋 مشاهده لاگ‌ها", callback_data="admin:view_logs")
        ],
        [
            InlineKeyboardButton("💾 پشتیبان‌گیری", callback_data="admin:backup"),
            InlineKeyboardButton("🧹 پاکسازی کش", callback_data="admin:clear_cache")
        ],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام
    await context.bot.send_message(
        chat_id=chat_id,
        text=status_message,
        reply_markup=reply_markup
    )
    
    logger.info(f"وضعیت سیستم برای ادمین {user.id} نمایش داده شد.")

async def clear_cache_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پاکسازی داده‌های کش
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    callback_query = update.callback_query
    admin_user = callback_query.from_user
    chat_id = callback_query.message.chat_id
    
    # دریافت کش از کانتکست
    cache: Cache = context.bot_data.get('cache')
    
    # پاسخ به کالبک
    await callback_query.answer()
    
    # نمایش وضعیت تایپ
    await send_typing_action(context.bot, chat_id)
    
    # پاکسازی کش
    try:
        # پاکسازی کش حافظه
        cache.clear()
        
        # پاکسازی کش دیسک (اگر وجود دارد)
        cache_dir = 'cache'
        if os.path.exists(cache_dir):
            import shutil
            files_removed = 0
            
            for root, dirs, files in os.walk(cache_dir):
                for file in files:
                    if file.endswith('.cache'):
                        os.remove(os.path.join(root, file))
                        files_removed += 1
            
            # ارسال پیام موفقیت
            await callback_query.edit_message_text(
                text=f"✅ داده‌های کش با موفقیت پاکسازی شدند.\n\n"
                     f"- کش حافظه: پاکسازی شد\n"
                     f"- کش دیسک: {files_removed} فایل حذف شد"
            )
        else:
            # ارسال پیام موفقیت (فقط کش حافظه)
            await callback_query.edit_message_text(
                text="✅ کش حافظه با موفقیت پاکسازی شد."
            )
        
        logger.info(f"داده‌های کش توسط ادمین {admin_user.id} پاکسازی شدند.")
        
    except Exception as e:
        logger.error(f"خطا در پاکسازی کش: {str(e)}")
        await callback_query.edit_message_text(
            text=f"❌ خطا در پاکسازی کش: {str(e)}"
        )

def register_admin_handlers(application: Application, config: Dict[str, Any], database: Database, cache: Cache) -> None:
    """
    ثبت هندلرهای مدیریت.
    
    پارامترها:
        application: آبجکت اپلیکیشن تلگرام
        config: تنظیمات برنامه
        database: شیء پایگاه داده
        cache: سیستم کش
    """
    # ثبت هندلرهای دستورات ادمین
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("status", system_status_command))
    
    # ثبت هندلر کالبک‌های ادمین
    # (کالبک‌های ادمین با پیشوند "admin:" شروع می‌شوند)
    application.add_handler(
        CallbackQueryHandler(
            handle_admin_callback_query, 
            pattern=r"^(admin:|broadcast:)"
        )
    )
    
    # ثبت هندلر کالبک‌های عملیات کاربر
    application.add_handler(
        CallbackQueryHandler(
            handle_user_action,
            pattern=r"^admin:(make_admin|remove_admin|block_user|unblock_user|delete_user|user_detail|user_payments|extend_subscription):"
        )
    )
    
    # ثبت هندلر کالبک تمدید اشتراک
    application.add_handler(
        CallbackQueryHandler(
            handle_extend_subscription,
            pattern=r"^admin:do_extend:"
        )
    )
    
    logger.info("هندلرهای مدیریت با موفقیت ثبت شدند.")