#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
این ماژول شامل تمام هندلرهای مرتبط با کاربران عادی ربات تلگرام است.
"""


from datetime import timezone
import logging
import re
from datetime import datetime
from src.utils.timezone_utils import get_current_datetime
from datetime import timedelta
from typing import Dict, List, Optional, Union, Any

from telegram.ext import (
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    ConversationHandler, 
    ContextTypes,
    filters
) 
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    CallbackQuery, 
    ReplyKeyboardRemove
)
from telegram.constants import ParseMode
from src.core.config import Config
from src.core.database import Database
from src.models.user import User
from src.models.subscription import Subscription
from src.utils.localization import get_text, get_available_languages
from src.utils.security import encrypt_sensitive_data, decrypt_sensitive_data
from src.utils.logger import setup_logger
from src.utils.cache import Cache
from src.utils.validators import validate_email, validate_phone_number
from src.utils.notification import NotificationManager
from src.utils.timezone_utils import get_user_timezone, convert_to_user_timezone

# تنظیم لاگر
logger = logging.getLogger('telegram.user_handlers')

# استیت‌های مکالمه برای ثبت‌نام کاربر
(CHOOSING_LANGUAGE, ENTERING_NAME, ENTERING_EMAIL, 
 ENTERING_PHONE, CONFIRMING_INFO) = range(5)

# استیت‌های مکالمه برای تنظیمات
(SETTINGS_MAIN, SETTINGS_LANGUAGE, SETTINGS_NOTIFICATION,
 SETTINGS_TIMEZONE, SETTINGS_PROFILE) = range(10, 15)

# کش برای پیشگیری از flood جهت ارسال پیام‌های تکراری
user_action_cache = Cache(default_ttl=60)  # 60 ثانیه

def register_user_handlers(application):
    """
    ثبت تمام هندلرهای کاربر در اپلیکیشن.
    
    Args:
        application: اپلیکیشن تلگرام
        
    Returns:
        None
    """
    # دریافت دسترسی به پایگاه داده و تنظیمات
    db = application.bot_data.get('db')
    config = application.bot_data.get('config')
    
    # هندلر شروع
    application.add_handler(CommandHandler("start", start))
    
    # هندلر راهنما
    application.add_handler(CommandHandler("help", help_command))
    
    # هندلر ثبت نام و تکمیل پروفایل
    registration_conv = ConversationHandler(
        entry_points=[
            CommandHandler("register", start_registration),
            CallbackQueryHandler(start_registration, pattern="^register$")
        ],
        states={
            CHOOSING_LANGUAGE: [CallbackQueryHandler(set_language, pattern="^lang_")],
            ENTERING_NAME: [MessageHandler(filters.text & ~filters.command, process_name)],
            ENTERING_EMAIL: [MessageHandler(filters.text & ~filters.command, process_email)],
            ENTERING_PHONE: [
                MessageHandler(filters.text & ~filters.command, process_phone),
                MessageHandler(filters.contact, process_contact)
            ],
            CONFIRMING_INFO: [CallbackQueryHandler(process_registration_confirmation)]
        },
        fallbacks=[CommandHandler("cancel", cancel_registration)],
        name="user_registration",
        persistent=False
    )
    application.add_handler(registration_conv)
    
    # هندلر تنظیمات کاربر
    settings_conv = ConversationHandler(
        entry_points=[
            CommandHandler("settings", show_settings),
            CallbackQueryHandler(show_settings, pattern="^settings$")
        ],
        states={
            SETTINGS_MAIN: [CallbackQueryHandler(handle_settings_menu, pattern="^setting_")],
            SETTINGS_LANGUAGE: [CallbackQueryHandler(change_language_setting, pattern="^lang_")],
            SETTINGS_NOTIFICATION: [CallbackQueryHandler(change_notification_setting, pattern="^notif_")],
            SETTINGS_TIMEZONE: [CallbackQueryHandler(change_timezone_setting, pattern="^tz_")],
            SETTINGS_PROFILE: [
                MessageHandler(filters.text & ~filters.command, update_profile_field),
                CallbackQueryHandler(select_profile_field, pattern="^profile_")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_settings),
            CallbackQueryHandler(cancel_settings, pattern="^cancel_settings$")
        ],
        name="user_settings",
        persistent=False
    )
    application.add_handler(settings_conv)
    
    # هندلر پروفایل کاربر
    application.add_handler(CommandHandler("profile", show_profile))
    
    # هندلر تماس با پشتیبانی
    contact_conv = ConversationHandler(
        entry_points=[CommandHandler("contact", contact_support)],
        states={
            1: [MessageHandler(filters.text & ~filters.command, process_support_message)]
        },
        fallbacks=[CommandHandler("cancel", cancel_contact)],
        name="contact_support",
        persistent=False
    )
    application.add_handler(contact_conv)
    
    # هندلر تغییر زبان
    application.add_handler(CommandHandler("language", change_language_command))
    
    # هندلر درباره ما
    application.add_handler(CommandHandler("about", about_command))
    
    # هندلر قوانین
    application.add_handler(CommandHandler("terms", terms_command))
    
    # هندلر برای پیام‌های متنی عادی که با دستور شروع نمی‌شوند
    application.add_handler(MessageHandler(
        filters.text & ~filters.command,
        handle_text_message
    ))
    
    # هندلر برای استیکرها
    application.add_handler(MessageHandler(
        filters.sticker,
        handle_sticker
    ))
    
    # هندلر برای تصاویر
    application.add_handler(MessageHandler(
        filters.photo,
        handle_photo
    ))
    
    # هندلر برای فایل‌ها
    application.add_handler(MessageHandler(
        filters.document,
        handle_document
    ))
    
    # هندلر برای موقعیت مکانی
    application.add_handler(MessageHandler(
        filters.location,
        handle_location
    ))
    
    # هندلر‌های callback query عمومی
    application.add_handler(CallbackQueryHandler(handle_help_callback, pattern="^help_"))
    application.add_handler(CallbackQueryHandler(handle_about_callback, pattern="^about_"))
    
    logger.info("هندلرهای کاربر با موفقیت ثبت شدند")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    هندلر دستور /start که اولین نقطه تماس کاربر با ربات است.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    db = context.bot_data.get('db')
    config = context.bot_data.get('config')
    
    # بررسی اگر کاربر از قبل در دیتابیس وجود دارد
    user_exists = db.execute(
        "SELECT COUNT(*) FROM users WHERE user_id = ?", 
        (user.id,)
    )[0][0] > 0
    
    # دریافت زبان کاربر
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # پیام خوشامدگویی بر اساس کاربر جدید یا قدیمی
    if not user_exists:
        # ثبت کاربر جدید در دیتابیس
        db.execute(
            "INSERT INTO users (user_id, username, first_name, last_name, language_code, joined_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user.id, user.username, user.first_name, user.last_name, user_lang, get_current_datetime())
        )
        
        # پیام خوشامدگویی برای کاربران جدید
        welcome_text = get_text("welcome.new_user", user_lang).format(
            name=user.first_name or "کاربر عزیز"
        )
        
        # دکمه‌های شروع برای کاربر جدید
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.register", user_lang), callback_data="register"),
                InlineKeyboardButton(get_text("button.help", user_lang), callback_data="help_main")
            ],
            [
                InlineKeyboardButton(get_text("button.language", user_lang), callback_data="setting_language")
            ]
        ]
    else:
        # به‌روزرسانی آخرین فعالیت کاربر
        db.execute(
            "UPDATE users SET last_activity = ? WHERE user_id = ?",
            (get_current_datetime(), user.id)
        )
        
        # دریافت اطلاعات کاربر از دیتابیس
        user_data = db.execute(
            "SELECT first_name, is_registered, is_active, language_code FROM users WHERE user_id = ?", 
            (user.id,)
        )[0]
        
        db_first_name, is_registered, is_active, db_lang = user_data
        
        # استفاده از زبان ذخیره شده در دیتابیس
        user_lang = db_lang or user_lang
        context.user_data['language'] = user_lang
        
        # بررسی وضعیت ثبت‌نام کاربر
        if not is_registered:
            welcome_text = get_text("welcome.returning_unregistered", user_lang).format(
                name=db_first_name or user.first_name or "کاربر عزیز"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(get_text("button.register", user_lang), callback_data="register"),
                    InlineKeyboardButton(get_text("button.help", user_lang), callback_data="help_main")
                ],
                [
                    InlineKeyboardButton(get_text("button.settings", user_lang), callback_data="settings")
                ]
            ]
        else:
            # بررسی وضعیت اشتراک کاربر
            subscription_data = db.execute(
                "SELECT subscription_type, expiry_date FROM subscriptions "
                "WHERE user_id = ? AND expiry_date > CURRENT_TIMESTAMP",
                (user.id,)
            )
            
            if subscription_data:
                sub_type, expiry_date = subscription_data[0]
                days_left = (expiry_date - get_current_datetime()).days
                
                welcome_text = get_text("welcome.returning_subscribed", user_lang).format(
                    name=db_first_name or user.first_name or "کاربر عزیز",
                    subscription_type=sub_type,
                    days_left=days_left
                )
            else:
                welcome_text = get_text("welcome.returning_user", user_lang).format(
                    name=db_first_name or user.first_name or "کاربر عزیز"
                )
            
            # دکمه‌های اصلی
            keyboard = [
                [
                    InlineKeyboardButton(get_text("button.services", user_lang), callback_data="show_services"),
                    InlineKeyboardButton(get_text("button.subscribe", user_lang), callback_data="subscribe")
                ],
                [
                    InlineKeyboardButton(get_text("button.profile", user_lang), callback_data="show_profile"),
                    InlineKeyboardButton(get_text("button.settings", user_lang), callback_data="settings")
                ],
                [
                    InlineKeyboardButton(get_text("button.help", user_lang), callback_data="help_main")
                ]
            ]
    
    # ارسال پیام خوشامدگویی با دکمه‌ها
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

    # ارسال اطلاعات شروع کار به ادمین‌ها
    admin_ids = config.get_list('telegram', 'admin_ids')
    for admin_id in admin_ids:
        # بررسی کش برای جلوگیری از ارسال مکرر
        cache_key = f"start_notification_{user.id}_{admin_id}"
        if not user_action_cache.get(cache_key):
            admin_text = f"👤 کاربر جدید شروع به استفاده از ربات کرد:\n\n" \
                        f"🆔 شناسه: `{user.id}`\n" \
                        f"👤 نام: {user.first_name or '-'} {user.last_name or ''}\n" \
                        f"📝 نام کاربری: @{user.username or 'ندارد'}\n" \
                        f"⏰ زمان: {get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}"
                        
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                # ذخیره در کش برای جلوگیری از ارسال مکرر
                user_action_cache.set(cache_key, True)
            except Exception as e:
                logger.error(f"خطا در ارسال اطلاعیه شروع به ادمین {admin_id}: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    هندلر دستور /help برای نمایش راهنمای ربات.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    db = context.bot_data.get('db')
    
    # دریافت زبان کاربر
    user_lang = context.user_data.get('language')
    if not user_lang:
        user_data = db.execute(
            "SELECT language_code FROM users WHERE user_id = ?", 
            (user.id,)
        )
        user_lang = user_data[0][0] if user_data else (user.language_code or 'fa')
        context.user_data['language'] = user_lang
    
    # متن راهنما
    help_text = get_text("help.main", user_lang)
    
    # دکمه‌های راهنما
    keyboard = [
        [
            InlineKeyboardButton(get_text("button.help_commands", user_lang), callback_data="help_commands"),
            InlineKeyboardButton(get_text("button.help_services", user_lang), callback_data="help_services")
        ],
        [
            InlineKeyboardButton(get_text("button.help_subscription", user_lang), callback_data="help_subscription"),
            InlineKeyboardButton(get_text("button.help_payment", user_lang), callback_data="help_payment")
        ],
        [
            InlineKeyboardButton(get_text("button.contact_support", user_lang), callback_data="contact_support")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    هندلر برای پردازش کلیک‌های کاربر در منوی راهنما.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db = context.bot_data.get('db')
    
    # دریافت زبان کاربر
    user_lang = context.user_data.get('language')
    if not user_lang:
        user_data = db.execute(
            "SELECT language_code FROM users WHERE user_id = ?", 
            (user.id,)
        )
        user_lang = user_data[0][0] if user_data else (user.language_code or 'fa')
        context.user_data['language'] = user_lang
    
    callback_data = query.data
    
    # دکمه برگشت به منوی اصلی راهنما
    back_button = [
        [InlineKeyboardButton(get_text("button.back", user_lang), callback_data="help_main")]
    ]
    
    if callback_data == "help_main":
        # منوی اصلی راهنما
        help_text = get_text("help.main", user_lang)
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.help_commands", user_lang), callback_data="help_commands"),
                InlineKeyboardButton(get_text("button.help_services", user_lang), callback_data="help_services")
            ],
            [
                InlineKeyboardButton(get_text("button.help_subscription", user_lang), callback_data="help_subscription"),
                InlineKeyboardButton(get_text("button.help_payment", user_lang), callback_data="help_payment")
            ],
            [
                InlineKeyboardButton(get_text("button.contact_support", user_lang), callback_data="contact_support")
            ]
        ]
    
    elif callback_data == "help_commands":
        # راهنمای دستورات
        help_text = get_text("help.commands", user_lang)
        keyboard = back_button
    
    elif callback_data == "help_services":
        # راهنمای خدمات
        help_text = get_text("help.services", user_lang)
        keyboard = back_button
    
    elif callback_data == "help_subscription":
        # راهنمای اشتراک‌ها
        help_text = get_text("help.subscription", user_lang)
        keyboard = back_button
    
    elif callback_data == "help_payment":
        # راهنمای پرداخت‌ها
        help_text = get_text("help.payment", user_lang)
        keyboard = back_button
    
    else:
        return
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=help_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    شروع فرایند ثبت‌نام کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    # بررسی آیا از طریق دکمه شروع شده یا دستور
    query = update.callback_query
    if query:
        await query.answer()
    
    user = update.effective_user
    db = context.bot_data.get('db')
    
    # دریافت زبان کاربر
    user_lang = context.user_data.get('language')
    if not user_lang:
        user_data = db.execute(
            "SELECT language_code FROM users WHERE user_id = ?", 
            (user.id,)
        )
        user_lang = user_data[0][0] if user_data else (user.language_code or 'fa')
        context.user_data['language'] = user_lang
    
    # بررسی آیا کاربر قبلاً ثبت‌نام کرده است
    is_registered = db.execute(
        "SELECT is_registered FROM users WHERE user_id = ?", 
        (user.id,)
    )
    
    if is_registered and is_registered[0][0]:
        # کاربر قبلاً ثبت‌نام کرده است
        message_text = get_text("registration.already_registered", user_lang)
        
        # دکمه‌های مربوطه
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.profile", user_lang), callback_data="show_profile"),
                InlineKeyboardButton(get_text("button.settings", user_lang), callback_data="settings")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        
        return ConversationHandler.END
    
    # شروع فرایند ثبت‌نام - انتخاب زبان
    message_text = get_text("registration.start", user_lang)
    
    # دکمه‌های انتخاب زبان
    keyboard = []
    available_languages = get_available_languages()
    
    # تقسیم دکمه‌ها به ردیف‌های دو تایی
    row = []
    for lang_code, lang_name in available_languages.items():
        if len(row) < 2:
            row.append(InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}"))
        else:
            keyboard.append(row)
            row = [InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}")]
    
    if row:  # اضافه کردن آخرین ردیف اگر کامل نشده باشد
        keyboard.append(row)
    
    # دکمه لغو
    keyboard.append([InlineKeyboardButton(get_text("button.cancel", user_lang), callback_data="cancel_registration")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    return CHOOSING_LANGUAGE

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    تنظیم زبان انتخابی کاربر در فرآیند ثبت‌نام.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db = context.bot_data.get('db')
    
    # استخراج کد زبان از callback_data
    selected_lang = query.data.split('_')[1]
    
    # ذخیره زبان انتخابی در دیتابیس و context
    db.execute(
        "UPDATE users SET language_code = ? WHERE user_id = ?",
        (selected_lang, user.id)
    )
    
    context.user_data['language'] = selected_lang
    
    # ادامه با مرحله بعدی - ورود نام
    message_text = get_text("registration.enter_name", selected_lang)
    
    await query.edit_message_text(
        text=message_text,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return ENTERING_NAME

async def process_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    پردازش نام وارد شده توسط کاربر در فرایند ثبت‌نام.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', 'fa')
    
    # دریافت نام از پیام کاربر
    full_name = update.message.text.strip()
    
    # اعتبارسنجی نام
    if len(full_name) < 3 or len(full_name) > 50:
        await update.message.reply_text(
            get_text("registration.invalid_name", user_lang),
            parse_mode=ParseMode.MARKDOWN
        )
        return ENTERING_NAME
    
    # ذخیره نام در context
    context.user_data['registration_name'] = full_name
    
    # ادامه با مرحله بعدی - ورود ایمیل
    await update.message.reply_text(
        get_text("registration.enter_email", user_lang),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return ENTERING_EMAIL

async def process_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    پردازش ایمیل وارد شده توسط کاربر در فرایند ثبت‌نام.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', 'fa')
    db = context.bot_data.get('db')
    
    # دریافت ایمیل از پیام کاربر
    email = update.message.text.strip().lower()
    
    # اعتبارسنجی ایمیل
    if not validate_email(email):
        await update.message.reply_text(
            get_text("registration.invalid_email", user_lang),
            parse_mode=ParseMode.MARKDOWN
        )
        return ENTERING_EMAIL
    
    # بررسی تکراری نبودن ایمیل
    email_exists = db.execute(
        "SELECT COUNT(*) FROM users WHERE email = ? AND user_id != ?",
        (email, user.id)
    )[0][0] > 0
    
    if email_exists:
        await update.message.reply_text(
            get_text("registration.email_exists", user_lang),
            parse_mode=ParseMode.MARKDOWN
        )
        return ENTERING_EMAIL
    
    # ذخیره ایمیل در context
    context.user_data['registration_email'] = email
    
    # درخواست شماره تلفن با دکمه اشتراک‌گذاری شماره تماس
    keyboard = ReplyKeyboardMarkup(
        [[{
            'text': get_text("button.share_contact", user_lang),
            'request_contact': True
        }]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await update.message.reply_text(
        get_text("registration.enter_phone", user_lang),
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return ENTERING_PHONE

async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    پردازش شماره تلفن وارد شده توسط کاربر به صورت متنی در فرایند ثبت‌نام.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', 'fa')
    
    # دریافت شماره تلفن از پیام متنی کاربر
    phone = update.message.text.strip()
    
    # اعتبارسنجی شماره تلفن
    if not validate_phone_number(phone):
        await update.message.reply_text(
            get_text("registration.invalid_phone", user_lang),
            parse_mode=ParseMode.MARKDOWN
        )
        return ENTERING_PHONE
    
    # ذخیره شماره تلفن در context
    context.user_data['registration_phone'] = phone
    
    # نمایش خلاصه اطلاعات برای تایید
    return await show_registration_summary(update, context)

async def process_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    پردازش شماره تلفن ارسال شده توسط کاربر از طریق اشتراک‌گذاری مخاطب در فرایند ثبت‌نام.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', 'fa')
    
    # دریافت شماره تلفن از کارت مخاطب
    phone = update.message.contact.phone_number
    
    # بررسی تطابق کاربر با مخاطب ارسالی
    if user.id != update.message.contact.user_id:
        await update.message.reply_text(
            get_text("registration.different_contact", user_lang),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
        return ENTERING_PHONE
    
    # ذخیره شماره تلفن در context
    context.user_data['registration_phone'] = phone
    
    # نمایش خلاصه اطلاعات برای تایید
    return await show_registration_summary(update, context)

async def show_registration_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    نمایش خلاصه اطلاعات ثبت‌نام برای تایید کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', 'fa')
    
    # دریافت اطلاعات جمع‌آوری شده
    name = context.user_data.get('registration_name', '')
    email = context.user_data.get('registration_email', '')
    phone = context.user_data.get('registration_phone', '')
    
    # متن خلاصه ثبت‌نام
    summary_text = get_text("registration.summary", user_lang).format(
        name=name,
        email=email,
        phone=phone
    )
    
    # دکمه‌های تایید یا اصلاح اطلاعات
    keyboard = [
        [
            InlineKeyboardButton(get_text("button.confirm", user_lang), callback_data="confirm_registration"),
            InlineKeyboardButton(get_text("button.edit", user_lang), callback_data="edit_registration")
        ],
        [
            InlineKeyboardButton(get_text("button.cancel", user_lang), callback_data="cancel_registration")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        summary_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # حذف کیبورد درخواست شماره تماس
    await update.message.reply_text(
        get_text("registration.check_info", user_lang),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return CONFIRMING_INFO

async def process_registration_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    پردازش پاسخ کاربر به تایید اطلاعات ثبت‌نام.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    user_lang = context.user_data.get('language', 'fa')
    db = context.bot_data.get('db')
    config = context.bot_data.get('config')
    
    if query.data == "confirm_registration":
        # دریافت اطلاعات ثبت شده
        name = context.user_data.get('registration_name', '')
        email = context.user_data.get('registration_email', '')
        phone = context.user_data.get('registration_phone', '')
        
        # به‌روزرسانی اطلاعات کاربر در دیتابیس
        db.execute(
            "UPDATE users SET full_name = ?, email = ?, phone = ?, is_registered = 1, "
            "registration_date = ? WHERE user_id = ?",
            (name, email, phone, get_current_datetime(), user.id)
        )
        
        # پاکسازی داده‌های موقت ثبت‌نام از context
        context.user_data.pop('registration_name', None)
        context.user_data.pop('registration_email', None)
        context.user_data.pop('registration_phone', None)
        
        # پیام موفقیت‌آمیز بودن ثبت‌نام
        success_text = get_text("registration.success", user_lang)
        
        # دکمه‌های بعد از ثبت‌نام
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.services", user_lang), callback_data="show_services"),
                InlineKeyboardButton(get_text("button.subscribe", user_lang), callback_data="subscribe")
            ],
            [
                InlineKeyboardButton(get_text("button.profile", user_lang), callback_data="show_profile")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=success_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # اطلاع به ادمین‌ها در مورد ثبت‌نام جدید
        admin_notification = f"✅ *ثبت‌نام جدید*\n\n" \
                           f"👤 نام: {name}\n" \
                           f"🆔 شناسه: `{user.id}`\n" \
                           f"📱 تلفن: `{phone}`\n" \
                           f"📧 ایمیل: {email}\n" \
                           f"⏰ زمان: {get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}"
        
        for admin_id in config.get_list('telegram', 'admin_ids'):
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_notification,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"خطا در ارسال اطلاعیه ثبت‌نام به ادمین {admin_id}: {e}")
        
        return ConversationHandler.END
        
    elif query.data == "edit_registration":
        # بازگشت به مرحله اول ثبت‌نام (انتخاب زبان)
        return await start_registration(update, context)
        
    elif query.data == "cancel_registration":
        # لغو ثبت‌نام
        return await cancel_registration(update, context)
    
    # اگر callback_data ناشناخته باشد
    return CONFIRMING_INFO

async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    لغو فرایند ثبت‌نام.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        END برای خاتمه مکالمه
    """
    # بررسی آیا از طریق دکمه لغو شده یا دستور
    query = update.callback_query
    user_lang = context.user_data.get('language', 'fa')
    
    # پاکسازی داده‌های موقت ثبت‌نام از context
    context.user_data.pop('registration_name', None)
    context.user_data.pop('registration_email', None)
    context.user_data.pop('registration_phone', None)
    
    # پیام لغو ثبت‌نام
    cancel_text = get_text("registration.cancelled", user_lang)
    
    if query:
        await query.answer()
        await query.edit_message_text(
            text=cancel_text,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            text=cancel_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    نمایش منوی تنظیمات کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    query = update.callback_query
    user = update.effective_user
    db = context.bot_data.get('db')
    
    # دریافت زبان کاربر
    user_lang = context.user_data.get('language')
    if not user_lang:
        user_data = db.execute(
            "SELECT language_code FROM users WHERE user_id = ?", 
            (user.id,)
        )
        user_lang = user_data[0][0] if user_data else (user.language_code or 'fa')
        context.user_data['language'] = user_lang
    
    # متن تنظیمات
    settings_text = get_text("settings.main", user_lang)
    
    # دکمه‌های تنظیمات
    keyboard = [
        [
            InlineKeyboardButton(get_text("button.settings_language", user_lang), callback_data="setting_language"),
            InlineKeyboardButton(get_text("button.settings_notification", user_lang), callback_data="setting_notification")
        ],
        [
            InlineKeyboardButton(get_text("button.settings_timezone", user_lang), callback_data="setting_timezone"),
            InlineKeyboardButton(get_text("button.settings_profile", user_lang), callback_data="setting_profile")
        ],
        [
            InlineKeyboardButton(get_text("button.settings_privacy", user_lang), callback_data="setting_privacy")
        ],
        [
            InlineKeyboardButton(get_text("button.back", user_lang), callback_data="cancel_settings")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.answer()
        await query.edit_message_text(
            text=settings_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            text=settings_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    return SETTINGS_MAIN

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش پیام‌های متنی عادی که با دستور خاصی شروع نمی‌شوند.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    db = context.bot_data.get('db')
    
    # دریافت زبان کاربر
    user_lang = context.user_data.get('language')
    if not user_lang:
        user_data = db.execute(
            "SELECT language_code FROM users WHERE user_id = ?", 
            (user.id,)
        )
        user_lang = user_data[0][0] if user_data else (user.language_code or 'fa')
        context.user_data['language'] = user_lang
    
    # به‌روزرسانی آخرین فعالیت کاربر
    db.execute(
        "UPDATE users SET last_activity = ? WHERE user_id = ?",
        (get_current_datetime(), user.id)
    )
    
    # بررسی وضعیت ثبت‌نام کاربر
    user_registered = db.execute(
        "SELECT is_registered FROM users WHERE user_id = ?", 
        (user.id,)
    )[0][0]
    
    if not user_registered:
        # اگر کاربر ثبت‌نام نکرده باشد، پیشنهاد ثبت‌نام
        register_text = get_text("messages.please_register", user_lang)
        
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.register", user_lang), callback_data="register"),
                InlineKeyboardButton(get_text("button.help", user_lang), callback_data="help_main")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text=register_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # برنامه‌ریزی برای اضافه کردن هوش مصنوعی برای پاسخگویی به پیام‌های متنی
    # فعلاً یک پاسخ ساده میدهیم
    
    default_response = get_text("messages.default_response", user_lang)
    
    keyboard = [
        [
            InlineKeyboardButton(get_text("button.services", user_lang), callback_data="show_services"),
            InlineKeyboardButton(get_text("button.help", user_lang), callback_data="help_main")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text=default_response,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    مدیریت منوی تنظیمات کاربر
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    user_lang = context.user_data.get('language', 'fa')
    callback_data = query.data
    
    if callback_data == "setting_language":
        # تنظیمات زبان
        message_text = get_text("settings.choose_language", user_lang)
        
        # دکمه‌های انتخاب زبان
        keyboard = []
        available_languages = get_available_languages()
        
        # تقسیم دکمه‌ها به ردیف‌های دو تایی
        row = []
        for lang_code, lang_name in available_languages.items():
            if len(row) < 2:
                row.append(InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}"))
            else:
                keyboard.append(row)
                row = [InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}")]
        
        if row:  # اضافه کردن آخرین ردیف اگر کامل نشده باشد
            keyboard.append(row)
        
        # دکمه بازگشت
        keyboard.append([
            InlineKeyboardButton(get_text("button.back", user_lang), callback_data="back_to_settings")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SETTINGS_LANGUAGE
        
    elif callback_data == "setting_notification":
        # تنظیمات اطلاع‌رسانی
        db = context.bot_data.get('db')
        
        # دریافت وضعیت فعلی اطلاع‌رسانی‌ها
        notification_settings = db.execute(
            "SELECT notify_news, notify_price_alerts, notify_subscription FROM users WHERE user_id = ?",
            (user.id,)
        )[0]
        
        notify_news, notify_price_alerts, notify_subscription = notification_settings
        
        # متن تنظیمات اطلاع‌رسانی
        message_text = get_text("settings.notification", user_lang)
        
        # وضعیت فعلی اطلاع‌رسانی‌ها
        news_status = "✅" if notify_news else "❌"
        price_status = "✅" if notify_price_alerts else "❌"
        subscription_status = "✅" if notify_subscription else "❌"
        
        # دکمه‌های تغییر وضعیت
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{get_text('button.notifications_news', user_lang)}: {news_status}", 
                    callback_data="notif_news"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{get_text('button.notifications_price', user_lang)}: {price_status}", 
                    callback_data="notif_price"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{get_text('button.notifications_subscription', user_lang)}: {subscription_status}", 
                    callback_data="notif_subscription"
                )
            ],
            [
                InlineKeyboardButton(get_text("button.back", user_lang), callback_data="back_to_settings")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SETTINGS_NOTIFICATION
        
    elif callback_data == "setting_timezone":
        # تنظیمات منطقه زمانی
        message_text = get_text("settings.timezone", user_lang)
        
        # لیست مناطق زمانی پرکاربرد
        common_timezones = [
            ("Asia/Tehran", "تهران (ایران)"),
            ("Asia/Dubai", "دبی (امارات)"),
            ("Europe/London", "لندن (انگلستان)"),
            ("America/New_York", "نیویورک (آمریکا)"),
            ("Asia/Tokyo", "توکیو (ژاپن)"),
            ("Europe/Moscow", "مسکو (روسیه)"),
            ("Asia/Shanghai", "شانگهای (چین)"),
            ("Asia/Istanbul", "استانبول (ترکیه)")
        ]
        
        # ساخت دکمه‌ها برای هر منطقه زمانی
        keyboard = []
        for tz_code, tz_name in common_timezones:
            keyboard.append([
                InlineKeyboardButton(tz_name, callback_data=f"tz_{tz_code}")
            ])
        
        # دکمه بازگشت
        keyboard.append([
            InlineKeyboardButton(get_text("button.back", user_lang), callback_data="back_to_settings")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SETTINGS_TIMEZONE
        
    elif callback_data == "setting_profile":
        # تنظیمات پروفایل
        message_text = get_text("settings.profile", user_lang)
        
        # دکمه‌های ویرایش فیلدهای پروفایل
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.edit_name", user_lang), callback_data="profile_name")
            ],
            [
                InlineKeyboardButton(get_text("button.edit_email", user_lang), callback_data="profile_email")
            ],
            [
                InlineKeyboardButton(get_text("button.edit_phone", user_lang), callback_data="profile_phone")
            ],
            [
                InlineKeyboardButton(get_text("button.back", user_lang), callback_data="back_to_settings")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SETTINGS_PROFILE
        
    elif callback_data == "setting_privacy":
        # تنظیمات حریم خصوصی
        message_text = get_text("settings.privacy", user_lang)
        
        # دکمه‌های حریم خصوصی
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.delete_account", user_lang), callback_data="privacy_delete")
            ],
            [
                InlineKeyboardButton(get_text("button.export_data", user_lang), callback_data="privacy_export")
            ],
            [
                InlineKeyboardButton(get_text("button.back", user_lang), callback_data="back_to_settings")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SETTINGS_MAIN  # همچنان در منوی اصلی باقی می‌ماند
        
    elif callback_data == "back_to_settings" or callback_data == "back_to_settings_main":
        # بازگشت به منوی اصلی تنظیمات
        return await show_settings(update, context)
    
    # در صورتی که callback_data ناشناخته باشد
    return SETTINGS_MAIN

async def change_language_setting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    تغییر تنظیمات زبان کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db = context.bot_data.get('db')
    
    if query.data.startswith("lang_"):
        # دریافت زبان انتخاب شده
        selected_lang = query.data.split('_')[1]
        
        # به‌روزرسانی در دیتابیس
        db.execute(
            "UPDATE users SET language_code = ? WHERE user_id = ?",
            (selected_lang, user.id)
        )
        
        # به‌روزرسانی در context
        context.user_data['language'] = selected_lang
        
        # دریافت متن پیام موفقیت‌آمیز با زبان جدید
        success_text = get_text("settings.language_updated", selected_lang)
        
        # دکمه بازگشت به تنظیمات
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.back", selected_lang), callback_data="back_to_settings")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=success_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SETTINGS_MAIN
    
    # در صورتی که callback_data ناشناخته باشد
    return SETTINGS_LANGUAGE

async def change_notification_setting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    تغییر تنظیمات اطلاع‌رسانی کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db = context.bot_data.get('db')
    user_lang = context.user_data.get('language', 'fa')
    
    # بررسی نوع اطلاع‌رسانی که باید تغییر کند
    if query.data == "notif_news":
        # تغییر وضعیت اطلاع‌رسانی اخبار
        current_value = db.execute(
            "SELECT notify_news FROM users WHERE user_id = ?",
            (user.id,)
        )[0][0]
        
        # تغییر به وضعیت مخالف
        new_value = 0 if current_value else 1
        
        db.execute(
            "UPDATE users SET notify_news = ? WHERE user_id = ?",
            (new_value, user.id)
        )
        
        # پیام موفقیت‌آمیز بودن تغییر
        status_text = get_text("settings.enabled", user_lang) if new_value else get_text("settings.disabled", user_lang)
        success_text = get_text("settings.notification_updated", user_lang).format(
            notification_type=get_text("button.notifications_news", user_lang),
            status=status_text
        )
        
    elif query.data == "notif_price":
        # تغییر وضعیت اطلاع‌رسانی قیمت‌ها
        current_value = db.execute(
            "SELECT notify_price_alerts FROM users WHERE user_id = ?",
            (user.id,)
        )[0][0]
        
        # تغییر به وضعیت مخالف
        new_value = 0 if current_value else 1
        
        db.execute(
            "UPDATE users SET notify_price_alerts = ? WHERE user_id = ?",
            (new_value, user.id)
        )
        
        # پیام موفقیت‌آمیز بودن تغییر
        status_text = get_text("settings.enabled", user_lang) if new_value else get_text("settings.disabled", user_lang)
        success_text = get_text("settings.notification_updated", user_lang).format(
            notification_type=get_text("button.notifications_price", user_lang),
            status=status_text
        )
        
    elif query.data == "notif_subscription":
        # تغییر وضعیت اطلاع‌رسانی اشتراک
        current_value = db.execute(
            "SELECT notify_subscription FROM users WHERE user_id = ?",
            (user.id,)
        )[0][0]
        
        # تغییر به وضعیت مخالف
        new_value = 0 if current_value else 1
        
        db.execute(
            "UPDATE users SET notify_subscription = ? WHERE user_id = ?",
            (new_value, user.id)
        )
        
        # پیام موفقیت‌آمیز بودن تغییر
        status_text = get_text("settings.enabled", user_lang) if new_value else get_text("settings.disabled", user_lang)
        success_text = get_text("settings.notification_updated", user_lang).format(
            notification_type=get_text("button.notifications_subscription", user_lang),
            status=status_text
        )
        
    elif query.data == "back_to_settings":
        # بازگشت به منوی اصلی تنظیمات
        return await show_settings(update, context)
    
    else:
        # callback_data ناشناخته
        return SETTINGS_NOTIFICATION
    
    # نمایش پیام موفقیت و بازگشت به منوی اطلاع‌رسانی
    await query.edit_message_text(
        text=success_text,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # نمایش مجدد منوی اطلاع‌رسانی بعد از کمی تاخیر
    import asyncio
    await asyncio.sleep(1)
    update_copy = Update(update.update_id, callback_query=CallbackQuery(
        id=query.id,
        from_user=query.from_user,
        chat_instance=query.chat_instance,
        data="setting_notification",
        message=query.message
    ))
    
    return await handle_settings_menu(update_copy, context)

async def change_timezone_setting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    تغییر تنظیمات منطقه زمانی کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db = context.bot_data.get('db')
    user_lang = context.user_data.get('language', 'fa')
    
    if query.data.startswith("tz_"):
        # دریافت منطقه زمانی انتخاب شده
        selected_timezone = query.data[3:]
        
        # به‌روزرسانی در دیتابیس
        db.execute(
            "UPDATE users SET timezone = ? WHERE user_id = ?",
            (selected_timezone, user.id)
        )
        
        # پیام موفقیت‌آمیز بودن تغییر
        success_text = get_text("settings.timezone_updated", user_lang).format(
            timezone=selected_timezone
        )
        
        # دکمه بازگشت به تنظیمات
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.back", user_lang), callback_data="back_to_settings")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=success_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SETTINGS_MAIN
        
    elif query.data == "back_to_settings":
        # بازگشت به منوی اصلی تنظیمات
        return await show_settings(update, context)
    
    # در صورتی که callback_data ناشناخته باشد
    return SETTINGS_TIMEZONE

async def select_profile_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    انتخاب فیلد پروفایل برای ویرایش.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db = context.bot_data.get('db')
    user_lang = context.user_data.get('language', 'fa')
    
    if query.data == "profile_name":
        # ویرایش نام
        current_name = db.execute(
            "SELECT full_name FROM users WHERE user_id = ?",
            (user.id,)
        )[0][0] or ""
        
        message_text = get_text("settings.edit_name", user_lang).format(
            current_name=current_name
        )
        
        # ذخیره فیلد در حال ویرایش
        context.user_data['editing_field'] = 'name'
        
    elif query.data == "profile_email":
        # ویرایش ایمیل
        current_email = db.execute(
            "SELECT email FROM users WHERE user_id = ?",
            (user.id,)
        )[0][0] or ""
        
        message_text = get_text("settings.edit_email", user_lang).format(
            current_email=current_email
        )
        
        # ذخیره فیلد در حال ویرایش
        context.user_data['editing_field'] = 'email'
        
    elif query.data == "profile_phone":
        # ویرایش شماره تلفن
        current_phone = db.execute(
            "SELECT phone FROM users WHERE user_id = ?",
            (user.id,)
        )[0][0] or ""
        
        message_text = get_text("settings.edit_phone", user_lang).format(
            current_phone=current_phone
        )
        
        # ذخیره فیلد در حال ویرایش
        context.user_data['editing_field'] = 'phone'
        
    elif query.data == "back_to_settings":
        # بازگشت به منوی اصلی تنظیمات
        return await show_settings(update, context)
        
    else:
        # callback_data ناشناخته
        return SETTINGS_PROFILE
    
    # دکمه لغو
    keyboard = [
        [
            InlineKeyboardButton(get_text("button.cancel", user_lang), callback_data="back_to_settings")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return SETTINGS_PROFILE

async def update_profile_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    به‌روزرسانی فیلد پروفایل با مقدار وارد شده توسط کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    user = update.effective_user
    db = context.bot_data.get('db')
    user_lang = context.user_data.get('language', 'fa')
    
    # دریافت فیلد در حال ویرایش
    editing_field = context.user_data.get('editing_field', '')
    
    # دریافت مقدار جدید از پیام کاربر
    new_value = update.message.text.strip()
    
    if editing_field == 'name':
        # اعتبارسنجی نام
        if len(new_value) < 3 or len(new_value) > 50:
            await update.message.reply_text(
                get_text("settings.invalid_name", user_lang),
                parse_mode=ParseMode.MARKDOWN
            )
            return SETTINGS_PROFILE
            
        # به‌روزرسانی نام در دیتابیس
        db.execute(
            "UPDATE users SET full_name = ? WHERE user_id = ?",
            (new_value, user.id)
        )
        
        success_text = get_text("settings.name_updated", user_lang)
        
    elif editing_field == 'email':
        # اعتبارسنجی ایمیل
        if not validate_email(new_value):
            await update.message.reply_text(
                get_text("settings.invalid_email", user_lang),
                parse_mode=ParseMode.MARKDOWN
            )
            return SETTINGS_PROFILE
            
        # بررسی تکراری نبودن ایمیل
        email_exists = db.execute(
            "SELECT COUNT(*) FROM users WHERE email = ? AND user_id != ?",
            (new_value, user.id)
        )[0][0] > 0
        
        if email_exists:
            await update.message.reply_text(
                get_text("settings.email_exists", user_lang),
                parse_mode=ParseMode.MARKDOWN
            )
            return SETTINGS_PROFILE
            
        # به‌روزرسانی ایمیل در دیتابیس
        db.execute(
            "UPDATE users SET email = ? WHERE user_id = ?",
            (new_value, user.id)
        )
        
        success_text = get_text("settings.email_updated", user_lang)
        
    elif editing_field == 'phone':
        # اعتبارسنجی شماره تلفن
        if not validate_phone_number(new_value):
            await update.message.reply_text(
                get_text("settings.invalid_phone", user_lang),
                parse_mode=ParseMode.MARKDOWN
            )
            return SETTINGS_PROFILE
            
        # به‌روزرسانی شماره تلفن در دیتابیس
        db.execute(
            "UPDATE users SET phone = ? WHERE user_id = ?",
            (new_value, user.id)
        )
        
        success_text = get_text("settings.phone_updated", user_lang)
        
    else:
        # فیلد نامعتبر
        return SETTINGS_PROFILE
    
    # پاکسازی فیلد در حال ویرایش
    context.user_data.pop('editing_field', None)
    
    # نمایش پیام موفقیت‌آمیز
    keyboard = [
        [
            InlineKeyboardButton(get_text("button.back", user_lang), callback_data="back_to_settings")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text=success_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return SETTINGS_MAIN

async def cancel_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    لغو تنظیمات و بازگشت به حالت عادی.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        END برای خاتمه مکالمه
    """
    # بررسی آیا از طریق دکمه لغو شده یا دستور
    query = update.callback_query
    user_lang = context.user_data.get('language', 'fa')
    
    # پاکسازی داده‌های موقت از context
    context.user_data.pop('editing_field', None)
    
    # پیام خروج از تنظیمات
    cancel_text = get_text("settings.cancelled", user_lang)
    
    if query:
        await query.answer()
        await query.edit_message_text(
            text=cancel_text,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            text=cancel_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    نمایش پروفایل کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    db = context.bot_data.get('db')
    
    # دریافت زبان کاربر
    user_lang = context.user_data.get('language')
    if not user_lang:
        user_data = db.execute(
            "SELECT language_code FROM users WHERE user_id = ?", 
            (user.id,)
        )
        user_lang = user_data[0][0] if user_data else (user.language_code or 'fa')
        context.user_data['language'] = user_lang
    
    # دریافت اطلاعات کاربر از دیتابیس
    user_info = db.execute(
        "SELECT full_name, email, phone, joined_date, is_registered, timezone "
        "FROM users WHERE user_id = ?",
        (user.id,)
    )[0]
    
    full_name, email, phone, joined_date, is_registered, timezone = user_info
    
    # بررسی وضعیت ثبت‌نام کاربر
    if not is_registered:
        register_text = get_text("profile.not_registered", user_lang)
        
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.register", user_lang), callback_data="register")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text=register_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # دریافت اطلاعات اشتراک کاربر
    subscription_info = db.execute(
        "SELECT subscription_type, start_date, expiry_date "
        "FROM subscriptions WHERE user_id = ? AND expiry_date > CURRENT_TIMESTAMP "
        "ORDER BY expiry_date DESC LIMIT 1",
        (user.id,)
    )
    
    # متن پروفایل
    profile_text = f"👤 *اطلاعات پروفایل*\n\n"
    profile_text += f"📝 *نام*: {full_name or '---'}\n"
    profile_text += f"📧 *ایمیل*: {email or '---'}\n"
    profile_text += f"📱 *شماره تلفن*: {phone or '---'}\n"
    profile_text += f"🌐 *منطقه زمانی*: {timezone or 'Asia/Tehran'}\n"
    profile_text += f"📅 *تاریخ عضویت*: {joined_date.strftime('%Y-%m-%d') if joined_date else '---'}\n"
    
    # اطلاعات اشتراک
    if subscription_info:
        sub_type, start_date, expiry_date = subscription_info[0]
        days_left = (expiry_date - get_current_datetime()).days
        
        profile_text += f"\n💎 *اشتراک فعال*: {sub_type}\n"
        profile_text += f"📅 *تاریخ شروع*: {start_date.strftime('%Y-%m-%d')}\n"
        profile_text += f"📅 *تاریخ انقضا*: {expiry_date.strftime('%Y-%m-%d')}\n"
        profile_text += f"⏱ *روزهای باقیمانده*: {days_left}\n"
    else:
        profile_text += f"\n⚠️ *بدون اشتراک فعال*\n"
    
    # دکمه‌های پروفایل
    keyboard = [
        [
            InlineKeyboardButton(get_text("button.edit_profile", user_lang), callback_data="setting_profile"),
            InlineKeyboardButton(get_text("button.subscribe", user_lang), callback_data="subscribe")
        ],
        [
            InlineKeyboardButton(get_text("button.transaction_history", user_lang), callback_data="show_transactions")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام پروفایل
    await update.message.reply_text(
        text=profile_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def change_language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    دستور تغییر زبان.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # متن تغییر زبان
    message_text = get_text("settings.choose_language", user_lang)
    
    # دکمه‌های انتخاب زبان
    keyboard = []
    available_languages = get_available_languages()
    
    # تقسیم دکمه‌ها به ردیف‌های دو تایی
    row = []
    for lang_code, lang_name in available_languages.items():
        if len(row) < 2:
            row.append(InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}"))
        else:
            keyboard.append(row)
            row = [InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}")]
    
    if row:  # اضافه کردن آخرین ردیف اگر کامل نشده باشد
        keyboard.append(row)
    
    # دکمه لغو
    keyboard.append([
        InlineKeyboardButton(get_text("button.cancel", user_lang), callback_data="cancel_settings")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def contact_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    تماس با پشتیبانی.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        استیت بعدی مکالمه
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # متن راهنمای تماس با پشتیبانی
    contact_text = get_text("contact.instructions", user_lang)
    
    # دکمه لغو
    keyboard = [
        [
            InlineKeyboardButton(get_text("button.cancel", user_lang), callback_data="cancel_contact")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text=contact_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return 1  # مرحله بعدی برای دریافت پیام کاربر

async def process_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    پردازش پیام ارسالی کاربر به پشتیبانی.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        END برای خاتمه مکالمه
    """
    user = update.effective_user
    db = context.bot_data.get('db')
    config = context.bot_data.get('config')
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # دریافت پیام کاربر
    user_message = update.message.text
    
    # ثبت پیام در دیتابیس
    db.execute(
        "INSERT INTO support_messages (user_id, message, created_at) VALUES (?, ?, ?)",
        (user.id, user_message, get_current_datetime())
    )
    
    # ارسال پیام به ادمین‌ها
    admin_text = f"📨 *پیام جدید از کاربر*\n\n" \
               f"👤 کاربر: {user.first_name} {user.last_name or ''} (@{user.username or 'بدون نام کاربری'})\n" \
               f"🆔 شناسه: `{user.id}`\n" \
               f"⏰ زمان: {get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}\n\n" \
               f"📝 پیام:\n{user_message}"
               
    admin_keyboard = [
        [
            InlineKeyboardButton("پاسخ", callback_data=f"reply_{user.id}")
        ]
    ]
    
    admin_markup = InlineKeyboardMarkup(admin_keyboard)
    
    for admin_id in config.get_list('telegram', 'admin_ids'):
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                reply_markup=admin_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"خطا در ارسال پیام پشتیبانی به ادمین {admin_id}: {e}")
    
    # پیام تایید به کاربر
    success_text = get_text("contact.message_sent", user_lang)
    
    await update.message.reply_text(
        text=success_text,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return ConversationHandler.END

async def cancel_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    لغو تماس با پشتیبانی.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
        
    Returns:
        END برای خاتمه مکالمه
    """
    # بررسی آیا از طریق دکمه لغو شده یا دستور
    query = update.callback_query
    user_lang = context.user_data.get('language', 'fa')
    
    # پیام لغو تماس با پشتیبانی
    cancel_text = get_text("contact.cancelled", user_lang)
    
    if query:
        await query.answer()
        await query.edit_message_text(
            text=cancel_text,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            text=cancel_text,
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    دستور نمایش اطلاعات درباره ما.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # متن درباره ما
    about_text = get_text("about.main", user_lang)
    
    # دکمه‌های درباره ما
    keyboard = [
        [
            InlineKeyboardButton(get_text("button.about_team", user_lang), callback_data="about_team"),
            InlineKeyboardButton(get_text("button.about_services", user_lang), callback_data="about_services")
        ],
        [
            InlineKeyboardButton(get_text("button.terms", user_lang), callback_data="about_terms"),
            InlineKeyboardButton(get_text("button.privacy", user_lang), callback_data="about_privacy")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text=about_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_about_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    هندلر برای پردازش کلیک‌های کاربر در منوی درباره ما.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    callback_data = query.data
    
    # دکمه برگشت به منوی اصلی درباره ما
    back_button = [
        [InlineKeyboardButton(get_text("button.back", user_lang), callback_data="about_main")]
    ]
    
    if callback_data == "about_main":
        # منوی اصلی درباره ما
        about_text = get_text("about.main", user_lang)
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.about_team", user_lang), callback_data="about_team"),
                InlineKeyboardButton(get_text("button.about_services", user_lang), callback_data="about_services")
            ],
            [
                InlineKeyboardButton(get_text("button.terms", user_lang), callback_data="about_terms"),
                InlineKeyboardButton(get_text("button.privacy", user_lang), callback_data="about_privacy")
            ]
        ]
    
    elif callback_data == "about_team":
        # اطلاعات تیم
        about_text = get_text("about.team", user_lang)
        keyboard = back_button
    
    elif callback_data == "about_services":
        # اطلاعات خدمات
        about_text = get_text("about.services", user_lang)
        keyboard = back_button
    
    elif callback_data == "about_terms":
        # قوانین و مقررات
        about_text = get_text("about.terms", user_lang)
        keyboard = back_button
    
    elif callback_data == "about_privacy":
        # حریم خصوصی
        about_text = get_text("about.privacy", user_lang)
        keyboard = back_button
    
    else:
        return
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=about_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def terms_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    دستور نمایش قوانین و مقررات.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # متن قوانین
    terms_text = get_text("about.terms", user_lang)
    
    await update.message.reply_text(
        text=terms_text,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش استیکرهای ارسالی توسط کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # پاسخ به استیکر
    sticker_response = get_text("messages.sticker_response", user_lang)
    
    await update.message.reply_text(
        text=sticker_response,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش تصاویر ارسالی توسط کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # پاسخ به تصویر
    photo_response = get_text("messages.photo_response", user_lang)
    
    await update.message.reply_text(
        text=photo_response,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش فایل‌های ارسالی توسط کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # پاسخ به فایل
    document_response = get_text("messages.document_response", user_lang)
    
    await update.message.reply_text(
        text=document_response,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش موقعیت مکانی ارسال شده توسط کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # پاسخ به موقعیت مکانی
    location_response = get_text("messages.location_response", user_lang)
    
    await update.message.reply_text(
        text=location_response,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # دریافت مختصات موقعیت
    latitude = update.message.location.latitude
    longitude = update.message.location.longitude
    
    # می‌توان از این مختصات برای اهداف مختلف استفاده کرد
    # مثلاً یافتن نزدیک‌ترین نقاط خدماتی
    # فعلاً صرفاً موقعیت را لاگ می‌کنیم
    logger.info(f"موقعیت دریافت شده از کاربر {user.id}: lat={latitude}, lon={longitude}")

async def handle_unrecognized_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش دستورهای ناشناخته که هندلر مشخصی برای آنها تعریف نشده است.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    db = context.bot_data.get('db')
    
    # دریافت زبان کاربر
    user_lang = context.user_data.get('language')
    if not user_lang:
        user_data = db.execute(
            "SELECT language_code FROM users WHERE user_id = ?", 
            (user.id,)
        )
        user_lang = user_data[0][0] if user_data else (user.language_code or 'fa')
        context.user_data['language'] = user_lang
    
    # پاسخ به دستور ناشناخته
    unknown_command = get_text("messages.unknown_command", user_lang)
    
    keyboard = [
        [
            InlineKeyboardButton(get_text("button.help", user_lang), callback_data="help_main")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text=unknown_command,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_user_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش پیام صوتی ارسال شده توسط کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # پاسخ به پیام صوتی
    voice_response = get_text("messages.voice_response", user_lang)
    
    await update.message.reply_text(
        text=voice_response,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # در نسخه‌های آینده می‌توان با استفاده از API تبدیل صوت به متن
    # پیام‌های صوتی کاربر را پردازش کرد

async def handle_user_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش ویدیوی ارسال شده توسط کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # پاسخ به ویدیو
    video_response = get_text("messages.video_response", user_lang)
    
    await update.message.reply_text(
        text=video_response,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_user_animation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش انیمیشن GIF ارسال شده توسط کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # پاسخ به انیمیشن GIF
    animation_response = get_text("messages.animation_response", user_lang)
    
    await update.message.reply_text(
        text=animation_response,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_user_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش نظرسنجی ارسال شده توسط کاربر.
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: آبجکت کانتکست هندلر
    """
    user = update.effective_user
    user_lang = context.user_data.get('language', user.language_code or 'fa')
    
    # پاسخ به نظرسنجی
    poll_response = get_text("messages.poll_response", user_lang)
    
    await update.message.reply_text(
        text=poll_response,
        parse_mode=ParseMode.MARKDOWN
    )

async def send_welcome_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_lang: str) -> None:
    """
    ارسال پیام خوشامدگویی به کاربر جدید.
    
    Args:
        context: آبجکت کانتکست هندلر
        chat_id: شناسه چت کاربر
        user_lang: زبان کاربر
    """
    welcome_text = get_text("welcome.initial", user_lang)
    
    # دکمه‌های شروع
    keyboard = [
        [
            InlineKeyboardButton(get_text("button.register", user_lang), callback_data="register"),
            InlineKeyboardButton(get_text("button.help", user_lang), callback_data="help_main")
        ],
        [
            InlineKeyboardButton(get_text("button.language", user_lang), callback_data="setting_language")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"خطا در ارسال پیام خوشامدگویی به کاربر {chat_id}: {e}")

async def send_inactive_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    تابع زمان‌بندی شده برای یادآوری به کاربران غیرفعال.
    این تابع به صورت دوره‌ای اجرا می‌شود.
    
    Args:
        context: آبجکت کانتکست هندلر
    """
    db = context.bot_data.get('db')
    config = context.bot_data.get('config')
    
    # تعیین بازه زمانی برای غیرفعال محسوب شدن کاربر (مثلاً 30 روز)
    inactivity_threshold = get_current_datetime() - timedelta(days=30)
    
    # یافتن کاربران غیرفعال که پیام یادآوری دریافت نکرده‌اند
    inactive_users = db.execute(
        "SELECT user_id, language_code FROM users WHERE is_active = 1 AND last_activity < ? "
        "AND (last_reminder IS NULL OR last_reminder < ?)",
        (inactivity_threshold, get_current_datetime() - timedelta(days=7))  # ارسال یادآوری هر 7 روز
    )
    
    for user_id, language_code in inactive_users:
        user_lang = language_code or 'fa'
        
        # متن یادآوری
        reminder_text = get_text("reminder.inactive_user", user_lang)
        
        # دکمه‌های یادآوری
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.services", user_lang), callback_data="show_services"),
                InlineKeyboardButton(get_text("button.help", user_lang), callback_data="help_main")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            # ارسال پیام یادآوری
            await context.bot.send_message(
                chat_id=user_id,
                text=reminder_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # به‌روزرسانی زمان آخرین یادآوری
            db.execute(
                "UPDATE users SET last_reminder = ? WHERE user_id = ?",
                (get_current_datetime(), user_id)
            )
            
            logger.info(f"پیام یادآوری به کاربر غیرفعال {user_id} ارسال شد")
            
        except Exception as e:
            logger.error(f"خطا در ارسال یادآوری به کاربر {user_id}: {e}")

async def send_subscription_expiry_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    تابع زمان‌بندی شده برای یادآوری انقضای اشتراک کاربران.
    این تابع به صورت دوره‌ای اجرا می‌شود.
    
    Args:
        context: آبجکت کانتکست هندلر
    """
    db = context.bot_data.get('db')
    
    # تاریخ فعلی برای مقایسه
    current_date = get_current_datetime()
    
    # تاریخ 7 روز آینده برای هشدار
    warning_date = current_date + timedelta(days=7)
    
    # یافتن کاربرانی که اشتراک‌شان ظرف 7 روز آینده منقضی می‌شود
    expiring_subscriptions = db.execute(
        "SELECT u.user_id, u.language_code, s.subscription_type, s.expiry_date "
        "FROM users u JOIN subscriptions s ON u.user_id = s.user_id "
        "WHERE s.expiry_date > ? AND s.expiry_date <= ? "
        "AND (s.expiry_reminded = 0 OR s.expiry_reminded IS NULL)",
        (current_date, warning_date)
    )
    
    for user_id, language_code, sub_type, expiry_date in expiring_subscriptions:
        user_lang = language_code or 'fa'
        
        # محاسبه روزهای باقیمانده
        days_left = (expiry_date - current_date).days
        
        # متن یادآوری انقضای اشتراک
        expiry_text = get_text("reminder.subscription_expiry", user_lang).format(
            subscription_type=sub_type,
            days_left=days_left,
            expiry_date=expiry_date.strftime('%Y-%m-%d')
        )
        
        # دکمه‌های تمدید اشتراک
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.extend_subscription", user_lang), callback_data="subscribe")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            # ارسال پیام یادآوری
            await context.bot.send_message(
                chat_id=user_id,
                text=expiry_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # به‌روزرسانی وضعیت یادآوری
            db.execute(
                "UPDATE subscriptions SET expiry_reminded = 1 WHERE user_id = ? AND expiry_date = ?",
                (user_id, expiry_date)
            )
            
            logger.info(f"پیام یادآوری انقضای اشتراک به کاربر {user_id} ارسال شد")
            
        except Exception as e:
            logger.error(f"خطا در ارسال یادآوری انقضای اشتراک به کاربر {user_id}: {e}")

async def process_welcome_back(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """
    پردازش پیام خوشامدگویی بازگشت برای کاربرانی که پس از مدتی طولانی برگشته‌اند.
    
    Args:
        context: آبجکت کانتکست هندلر
        user_id: شناسه کاربر
    """
    db = context.bot_data.get('db')
    
    # بررسی زمان آخرین فعالیت کاربر
    user_info = db.execute(
        "SELECT language_code, last_activity FROM users WHERE user_id = ?",
        (user_id,)
    )
    
    if not user_info:
        return
    
    language_code, last_activity = user_info[0]
    user_lang = language_code or 'fa'
    
    # اگر آخرین فعالیت بیش از 30 روز پیش باشد، پیام خوشامدگویی بازگشت ارسال کن
    if last_activity and (get_current_datetime() - last_activity).days > 30:
        welcome_back_text = get_text("welcome.returning_after_long_time", user_lang)
        
        # دکمه‌های خوشامدگویی بازگشت
        keyboard = [
            [
                InlineKeyboardButton(get_text("button.services", user_lang), callback_data="show_services"),
                InlineKeyboardButton(get_text("button.help", user_lang), callback_data="help_main")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=welcome_back_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"پیام خوشامدگویی بازگشت به کاربر {user_id} ارسال شد")
            
        except Exception as e:
            logger.error(f"خطا در ارسال پیام خوشامدگویی بازگشت به کاربر {user_id}: {e}")
    
    # به‌روزرسانی زمان آخرین فعالیت کاربر
    db.execute(
        "UPDATE users SET last_activity = ? WHERE user_id = ?",
        (get_current_datetime(), user_id)
    )