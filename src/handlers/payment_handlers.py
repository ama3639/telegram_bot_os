#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول هندلرهای پرداخت.

این ماژول شامل هندلرهای تلگرام برای پردازش پرداخت‌ها، مدیریت اشتراک‌ها 
و سایر عملیات مالی است.

تاریخ ایجاد: ۱۴۰۴/۰۱/۰۷
"""

import logging
import json
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from utils.timezone_utils import get_current_datetime, timedelta
import time
import uuid
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from core.database import Database
from utils.cache import Cache
from utils.localization import get_message
from utils.notification import send_typing_action
from utils.logger import log_execution_time

logger = logging.getLogger(__name__)

# کلیدهای کالبک پرداخت
PAYMENT_CALLBACK_PREFIX = "payment:"
PAYMENT_CALLBACK_PLAN = "payment:plan:"
PAYMENT_CALLBACK_METHOD = "payment:method:"
PAYMENT_CALLBACK_CONFIRM = "payment:confirm:"
PAYMENT_CALLBACK_CANCEL = "payment:cancel"
PAYMENT_CALLBACK_CHECK = "payment:check:"
PAYMENT_CALLBACK_CRYPTO = "payment:crypto:"

class PaymentManager:
    """
    کلاس مدیریت پرداخت‌ها و اشتراک‌ها.
    """
    
    def __init__(self, database: Database, config: Dict[str, Any], cache: Cache):
        """
        مقداردهی اولیه کلاس مدیریت پرداخت.
         
        پارامترها:
            database: شیء پایگاه داده
            config: تنظیمات برنامه
            cache: سیستم کش
        """
        self.database = database
        self.config = config
        self.cache = cache
        self.subscription_plans = config.get('SUBSCRIPTION_PLANS', {})
        
        # درگاه‌های پرداخت موجود
        self.payment_gateways = {
            'zarinpal': 'زرین‌پال',
            'idpay': 'آیدی پی',
            'cryptocurrency': 'ارز دیجیتال',
            'manual': 'پرداخت دستی'
        }
        
        logger.info("سیستم مدیریت پرداخت راه‌اندازی شد.")
    
    def get_subscription_plans(self) -> Dict[str, Dict[str, Any]]:
        """
        دریافت طرح‌های اشتراک.
        
        بازگشت:
            Dict[str, Dict[str, Any]]: طرح‌های اشتراک
        """
        return self.subscription_plans
    
    def get_payment_gateways(self) -> Dict[str, str]:
        """
        دریافت درگاه‌های پرداخت.
        
        بازگشت:
            Dict[str, str]: درگاه‌های پرداخت
        """
        return self.payment_gateways
    
    def create_payment(self, user_id: int, plan_name: str, gateway: str) -> Dict[str, Any]:
        """
        ایجاد یک پرداخت جدید.
        
        پارامترها:
            user_id: شناسه کاربر
            plan_name: نام طرح اشتراک
            gateway: درگاه پرداخت
            
        بازگشت:
            Dict[str, Any]: اطلاعات پرداخت
            
        استثناها:
            ValueError: اگر طرح اشتراک یا درگاه پرداخت نامعتبر باشد
        """
        # بررسی طرح اشتراک
        if plan_name not in self.subscription_plans:
            raise ValueError(f"طرح اشتراک '{plan_name}' نامعتبر است.")
        
        # بررسی درگاه پرداخت
        if gateway not in self.payment_gateways:
            raise ValueError(f"درگاه پرداخت '{gateway}' نامعتبر است.")
        
        # دریافت اطلاعات طرح
        plan_data = self.subscription_plans[plan_name]
        amount = plan_data.get('price', 0)
        
        # ایجاد شناسه مرجع
        reference_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{user_id}"
        
        # توضیحات پرداخت
        description = f"اشتراک {plan_name} به مدت {plan_data.get('duration', 30)} روز"
        
        # ثبت پرداخت در پایگاه داده
        payment_id = self.database.add_payment(
            user_id=user_id,
            amount=amount,
            currency='IRR',
            gateway=gateway,
            reference_id=reference_id,
            plan_name=plan_name,
            description=description
        )
        
        # بازگرداندن اطلاعات پرداخت
        return {
            'id': payment_id,
            'user_id': user_id,
            'amount': amount,
            'currency': 'IRR',
            'gateway': gateway,
            'reference_id': reference_id,
            'status': 'pending',
            'plan_name': plan_name,
            'description': description
        }
    
    async def process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        پردازش پرداخت بر اساس درگاه.
        
        پارامترها:
            payment_data: اطلاعات پرداخت
            
        بازگشت:
            Dict[str, Any]: نتیجه پردازش (شامل URL پرداخت)
            
        استثناها:
            ValueError: اگر پردازش با خطا مواجه شود
        """
        gateway = payment_data.get('gateway')
        
        # پیاده‌سازی درگاه‌های مختلف
        if gateway == 'zarinpal':
            return await self._process_zarinpal(payment_data)
        elif gateway == 'idpay':
            return await self._process_idpay(payment_data)
        elif gateway == 'cryptocurrency':
            return await self._process_crypto(payment_data)
        elif gateway == 'manual':
            return await self._process_manual(payment_data)
        else:
            raise ValueError(f"درگاه پرداخت '{gateway}' پشتیبانی نمی‌شود.")
    
    async def _process_zarinpal(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        پردازش پرداخت با درگاه زرین‌پال.
        
        پارامترها:
            payment_data: اطلاعات پرداخت
            
        بازگشت:
            Dict[str, Any]: نتیجه پردازش
        """
        # در حالت واقعی، اینجا از API زرین‌پال استفاده می‌شود
        # این پیاده‌سازی نمونه است
        
        # دریافت کلید API
        api_key = self.config.get('PAYMENT_API_KEY')
        
        if not api_key:
            raise ValueError("کلید API زرین‌پال تنظیم نشده است.")
        
        # شبیه‌سازی تأخیر شبکه
        await asyncio.sleep(1)
        
        # ساخت URL پرداخت نمونه
        payment_url = f"https://www.zarinpal.com/pg/StartPay/{payment_data['reference_id']}"
        
        return {
            'success': True,
            'payment_url': payment_url,
            'authority': payment_data['reference_id']
        }
    
    async def _process_idpay(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        پردازش پرداخت با درگاه آیدی پی.
        
        پارامترها:
            payment_data: اطلاعات پرداخت
            
        بازگشت:
            Dict[str, Any]: نتیجه پردازش
        """
        # در حالت واقعی، اینجا از API آیدی پی استفاده می‌شود
        # این پیاده‌سازی نمونه است
        
        # دریافت کلید API
        api_key = self.config.get('PAYMENT_API_KEY')
        
        if not api_key:
            raise ValueError("کلید API آیدی پی تنظیم نشده است.")
        
        # شبیه‌سازی تأخیر شبکه
        await asyncio.sleep(1)
        
        # ساخت URL پرداخت نمونه
        payment_url = f"https://idpay.ir/p/ws/{payment_data['reference_id']}"
        
        return {
            'success': True,
            'payment_url': payment_url,
            'track_id': payment_data['reference_id']
        }
    
    async def _process_crypto(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        پردازش پرداخت با ارز دیجیتال.
        
        پارامترها:
            payment_data: اطلاعات پرداخت
            
        بازگشت:
            Dict[str, Any]: نتیجه پردازش
        """
        # در حالت واقعی، اینجا از یک سرویس پرداخت ارز دیجیتال استفاده می‌شود
        # این پیاده‌سازی نمونه است
        
        # دریافت کلید API
        api_key = self.config.get('CRYPTO_PAYMENT_API_KEY')
        
        if not api_key:
            raise ValueError("کلید API پرداخت ارز دیجیتال تنظیم نشده است.")
        
        # شبیه‌سازی تأخیر شبکه
        await asyncio.sleep(1)
        
        # اطلاعات پرداخت ارز دیجیتال نمونه
        crypto_info = {
            'currency': 'USDT',
            'network': 'TRC20',
            'address': 'TY29o61dtd5BaLUMbZCmLE7pyPq9Qdpz1D',
            'amount': payment_data['amount'] / 500000,  # تبدیل تومان به دلار (نمونه)
            'expires_at': int(time.time()) + 3600  # یک ساعت
        }
        
        return {
            'success': True,
            'payment_method': 'crypto',
            'crypto_info': crypto_info
        }
    
    async def _process_manual(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        پردازش پرداخت دستی.
        
        پارامترها:
            payment_data: اطلاعات پرداخت
            
        بازگشت:
            Dict[str, Any]: نتیجه پردازش
        """
        # اطلاعات پرداخت دستی
        manual_info = {
            'bank_name': 'بانک ملت',
            'account_number': '6104-3378-9021-6541',
            'card_number': '6104337890216541',
            'owner_name': 'شرکت نمونه',
            'amount': payment_data['amount'],
            'reference_id': payment_data['reference_id']
        }
        
        return {
            'success': True,
            'payment_method': 'manual',
            'manual_info': manual_info
        }
    
    async def check_payment_status(self, payment_id: int) -> Dict[str, Any]:
        """
        بررسی وضعیت یک پرداخت.
        
        پارامترها:
            payment_id: شناسه پرداخت
            
        بازگشت:
            Dict[str, Any]: وضعیت پرداخت
            
        استثناها:
            ValueError: اگر پرداخت یافت نشود
        """
        # دریافت اطلاعات پرداخت از پایگاه داده
        payment_data = self.database.get_payment(payment_id)
        
        if not payment_data:
            raise ValueError(f"پرداخت با شناسه {payment_id} یافت نشد.")
        
        gateway = payment_data.get('gateway')
        
        # در حالت واقعی، اینجا وضعیت از درگاه پرداخت بررسی می‌شود
        # این پیاده‌سازی نمونه است با وضعیت تصادفی
        
        import random
        status_options = ['pending', 'completed', 'failed']
        status = random.choice(status_options)
        
        # به‌روزرسانی وضعیت در پایگاه داده
        if status != payment_data.get('status'):
            self.database.update_payment_status(payment_id, status)
        
        # اگر پرداخت موفق بود، اشتراک را فعال کنیم
        if status == 'completed' and payment_data.get('plan_name'):
            await self.activate_subscription(
                payment_data.get('user_id'),
                payment_data.get('plan_name')
            )
        
        return {
            'id': payment_id,
            'status': status,
            'updated': True if status != payment_data.get('status') else False
        }
    
    async def activate_subscription(self, user_id: int, plan_name: str) -> Dict[str, Any]:
        """
        فعال‌سازی اشتراک برای کاربر.
        
        پارامترها:
            user_id: شناسه کاربر
            plan_name: نام طرح اشتراک
            
        بازگشت:
            Dict[str, Any]: نتیجه فعال‌سازی
            
        استثناها:
            ValueError: اگر طرح اشتراک نامعتبر باشد
        """
        # بررسی طرح اشتراک
        if plan_name not in self.subscription_plans:
            raise ValueError(f"طرح اشتراک '{plan_name}' نامعتبر است.")
        
        # دریافت اطلاعات طرح
        plan_data = self.subscription_plans[plan_name]
        duration = plan_data.get('duration', 30)
        
        # دریافت اطلاعات کاربر
        user_data = self.database.get_user(user_id)
        
        if not user_data:
            raise ValueError(f"کاربر با شناسه {user_id} یافت نشد.")
        
        # محاسبه تاریخ انقضای جدید
        current_expiry = user_data.get('subscription_expiry')
        
        if current_expiry:
            try:
                expiry_date = datetime.fromisoformat(current_expiry.replace('Z', '+00:00'))
                if expiry_date > datetime.now(expiry_date.tzinfo):
                    # اگر اشتراک هنوز اعتبار دارد، مدت زمان را به آن اضافه می‌کنیم
                    new_expiry = expiry_date + timedelta(days=duration)
                else:
                    # اگر منقضی شده، از امروز حساب می‌کنیم
                    new_expiry = get_current_datetime().astimezone() + timedelta(days=duration)
            except ValueError:
                # اگر تاریخ معتبر نیست، از امروز حساب می‌کنیم
                new_expiry = get_current_datetime().astimezone() + timedelta(days=duration)
        else:
            # اگر اشتراکی وجود ندارد، از امروز حساب می‌کنیم
            new_expiry = get_current_datetime().astimezone() + timedelta(days=duration)
        
        # به‌روزرسانی اشتراک کاربر در پایگاه داده
        self.database.execute_query(
            "UPDATE users SET subscription_plan = ?, subscription_expiry = ? WHERE user_id = ?",
            (plan_name, new_expiry.isoformat(), user_id)
        )
        
        logger.info(f"اشتراک طرح '{plan_name}' برای کاربر {user_id} تا تاریخ {new_expiry.date()} فعال شد.")
        
        return {
            'success': True,
            'user_id': user_id,
            'plan_name': plan_name,
            'expiry_date': new_expiry.date().isoformat()
        }
    
    def check_subscription(self, user_id: int) -> Dict[str, Any]:
        """
        بررسی وضعیت اشتراک یک کاربر.
        
        پارامترها:
            user_id: شناسه کاربر
            
        بازگشت:
            Dict[str, Any]: وضعیت اشتراک
        """
        # دریافت اطلاعات کاربر
        user_data = self.database.get_user(user_id)
        
        if not user_data:
            return {
                'has_subscription': False,
                'reason': 'user_not_found'
            }
        
        # بررسی وجود اشتراک
        subscription_plan = user_data.get('subscription_plan')
        subscription_expiry = user_data.get('subscription_expiry')
        
        if not subscription_plan or not subscription_expiry:
            return {
                'has_subscription': False,
                'reason': 'no_subscription'
            }
        
        # بررسی تاریخ انقضا
        try:
            expiry_date = datetime.fromisoformat(subscription_expiry.replace('Z', '+00:00'))
            is_active = expiry_date > datetime.now(expiry_date.tzinfo)
        except ValueError:
            is_active = False
        
        if not is_active:
            return {
                'has_subscription': False,
                'reason': 'expired',
                'plan_name': subscription_plan,
                'expiry_date': subscription_expiry.split('T')[0] if subscription_expiry else None
            }
        
        # دریافت اطلاعات طرح
        plan_data = self.subscription_plans.get(subscription_plan, {})
        
        return {
            'has_subscription': True,
            'plan_name': subscription_plan,
            'expiry_date': subscription_expiry.split('T')[0] if subscription_expiry else None,
            'features': plan_data.get('features', [])
        }

# هندلرهای پرداخت و اشتراک
payment_manager = None

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش دستور /subscribe برای خرید اشتراک.
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # دریافت پایگاه داده و مدیر پرداخت از کانتکست
    database = context.bot_data.get('database')
    global payment_manager
    
    # دریافت زبان کاربر
    user_lang = database.get_user_language(user.id) or 'fa'
    
    # نمایش وضعیت تایپ برای تجربه کاربری بهتر
    await send_typing_action(context.bot, chat_id)
    
    # بررسی وضعیت فعلی اشتراک
    subscription_status = payment_manager.check_subscription(user.id)
    
    # ساخت پیام بر اساس وضعیت اشتراک
    if subscription_status['has_subscription']:
        # کاربر اشتراک فعال دارد
        message = get_message('subscription_active', user_lang).format(
            expiry_date=subscription_status['expiry_date']
        )
        
        # اضافه کردن اطلاعات ویژگی‌ها
        features = subscription_status.get('features', [])
        if features:
            message += "\n\n✨ ویژگی‌های اشتراک شما:\n"
            message += "\n".join([f"- {feature}" for feature in features])
        
        # دکمه‌های اقدام
        keyboard = [
            [InlineKeyboardButton("⬆️ ارتقای اشتراک", callback_data=f"{PAYMENT_CALLBACK_PREFIX}upgrade")],
            [InlineKeyboardButton("🔁 تمدید اشتراک", callback_data=f"{PAYMENT_CALLBACK_PREFIX}extend")]
        ]
    else:
        # کاربر اشتراک فعال ندارد
        message = get_message('subscription_plans', user_lang)
        
        # دریافت طرح‌های اشتراک
        subscription_plans = payment_manager.get_subscription_plans()
        
        # اضافه کردن اطلاعات طرح‌ها
        for plan_name, plan_data in subscription_plans.items():
            plan_message = get_message(f'plan_{plan_name}', user_lang).format(
                price=plan_data.get('price', 0),
                duration=plan_data.get('duration', 0),
                features=', '.join(plan_data.get('features', []))
            )
            message += f"\n\n{plan_message}"
        
        # دکمه‌های انتخاب طرح
        keyboard = []
        for plan_name in subscription_plans.keys():
            keyboard.append([
                InlineKeyboardButton(
                    get_message(f'plan_{plan_name}', user_lang).split('\n')[0],
                    callback_data=f"{PAYMENT_CALLBACK_PLAN}{plan_name}"
                )
            ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام
    await context.bot.send_message(
        chat_id=chat_id,
        text=message,
        reply_markup=reply_markup
    )
    
    logger.info(f"کاربر {user.id} صفحه اشتراک را مشاهده کرد.")

async def handle_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش کالبک‌های مربوط به پرداخت و اشتراک.
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
    """
    callback_query = update.callback_query
    user = callback_query.from_user
    chat_id = callback_query.message.chat_id
    message_id = callback_query.message.message_id
    callback_data = callback_query.data
    
    # دریافت پایگاه داده و مدیر پرداخت از کانتکست
    database = context.bot_data.get('database')
    global payment_manager
    
    # دریافت زبان کاربر
    user_lang = database.get_user_language(user.id) or 'fa'
    
    # پاسخ به کالبک
    await callback_query.answer()
    
    # پردازش انواع مختلف کالبک‌های پرداخت
    if callback_data.startswith(PAYMENT_CALLBACK_PLAN):
        # انتخاب طرح اشتراک
        plan_name = callback_data[len(PAYMENT_CALLBACK_PLAN):]
        await show_payment_methods(update, context, plan_name)
        
    elif callback_data.startswith(PAYMENT_CALLBACK_METHOD):
        # انتخاب روش پرداخت
        method_data = callback_data[len(PAYMENT_CALLBACK_METHOD):].split(':')
        if len(method_data) == 2:
            plan_name, gateway = method_data
            await process_payment_request(update, context, plan_name, gateway)
        
    elif callback_data.startswith(PAYMENT_CALLBACK_CONFIRM):
        # تأیید پرداخت
        payment_id = int(callback_data[len(PAYMENT_CALLBACK_CONFIRM):])
        await check_payment(update, context, payment_id)
        
    elif callback_data == PAYMENT_CALLBACK_CANCEL:
        # لغو پرداخت
        await callback_query.edit_message_text(
            text=get_message('payment_canceled', user_lang)
        )
        
    elif callback_data.startswith(PAYMENT_CALLBACK_CHECK):
        # بررسی وضعیت پرداخت
        payment_id = int(callback_data[len(PAYMENT_CALLBACK_CHECK):])
        await check_payment(update, context, payment_id, show_result=True)
        
    elif callback_data.startswith(PAYMENT_CALLBACK_CRYPTO):
        # مشاهده اطلاعات پرداخت ارز دیجیتال
        payment_id = int(callback_data[len(PAYMENT_CALLBACK_CRYPTO):])
        await show_crypto_details(update, context, payment_id)
        
    elif callback_data == f"{PAYMENT_CALLBACK_PREFIX}upgrade" or callback_data == f"{PAYMENT_CALLBACK_PREFIX}extend":
        # ارتقا یا تمدید اشتراک
        # برای هر دو حالت، به صفحه انتخاب طرح می‌رویم
        await subscribe_command(update, context)

async def show_payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_name: str) -> None:
    """
    نمایش روش‌های پرداخت.
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        plan_name: نام طرح اشتراک
    """
    callback_query = update.callback_query
    user = callback_query.from_user
    
    # دریافت پایگاه داده و مدیر پرداخت از کانتکست
    database = context.bot_data.get('database')
    global payment_manager
    
    # دریافت زبان کاربر
    user_lang = database.get_user_language(user.id) or 'fa'
    
    # دریافت اطلاعات طرح
    subscription_plans = payment_manager.get_subscription_plans()
    plan_data = subscription_plans.get(plan_name, {})
    
    if not plan_data:
        await callback_query.edit_message_text(
            text=get_message('error', user_lang).format(message="طرح انتخابی یافت نشد.")
        )
        return
    
    # ساخت پیام انتخاب روش پرداخت
    amount = plan_data.get('price', 0)
    duration = plan_data.get('duration', 0)
    
    message = f"💳 انتخاب روش پرداخت\n\n"
    message += f"🔹 طرح: {get_message(f'plan_{plan_name}', user_lang).split('\n')[0]}\n"
    message += f"💰 مبلغ: {amount:,} تومان\n"
    message += f"⏱ مدت اعتبار: {duration} روز\n\n"
    message += "لطفاً روش پرداخت را انتخاب کنید:"
    
    # دریافت درگاه‌های پرداخت
    payment_gateways = payment_manager.get_payment_gateways()
    
    # ساخت دکمه‌های درگاه‌های پرداخت
    keyboard = []
    for gateway_id, gateway_name in payment_gateways.items():
        keyboard.append([
            InlineKeyboardButton(
                gateway_name,
                callback_data=f"{PAYMENT_CALLBACK_METHOD}{plan_name}:{gateway_id}"
            )
        ])
    
    # دکمه بازگشت
    keyboard.append([InlineKeyboardButton(get_message('back', user_lang), callback_data=f"{PAYMENT_CALLBACK_PREFIX}back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام
    await callback_query.edit_message_text(
        text=message,
        reply_markup=reply_markup
    )
    
    logger.info(f"کاربر {user.id} در حال انتخاب روش پرداخت برای طرح {plan_name} است.")

async def process_payment_request(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                              plan_name: str, gateway: str) -> None:
    """
    پردازش درخواست پرداخت.
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        plan_name: نام طرح اشتراک
        gateway: درگاه پرداخت
    """
    callback_query = update.callback_query
    user = callback_query.from_user
    
    # دریافت پایگاه داده و مدیر پرداخت از کانتکست
    database = context.bot_data.get('database')
    global payment_manager
    
    # دریافت زبان کاربر
    user_lang = database.get_user_language(user.id) or 'fa'
    
    # نمایش پیام در حال پردازش
    await callback_query.edit_message_text(
        text=get_message('processing', user_lang)
    )
    
    try:
        # ایجاد پرداخت
        payment_data = payment_manager.create_payment(user.id, plan_name, gateway)
        
        # پردازش پرداخت
        result = await payment_manager.process_payment(payment_data)
        
        if not result['success']:
            raise ValueError(result.get('message', 'خطای نامشخص در پردازش پرداخت'))
        
        # نمایش اطلاعات پرداخت بر اساس نوع درگاه
        if gateway == 'cryptocurrency':
            await show_crypto_payment(update, context, payment_data['id'], result)
        elif gateway == 'manual':
            await show_manual_payment(update, context, payment_data['id'], result)
        else:
            # درگاه‌های آنلاین
            payment_url = result.get('payment_url')
            
            if not payment_url:
                raise ValueError("لینک پرداخت دریافت نشد.")
            
            # ساخت دکمه‌های پرداخت
            keyboard = [
                [InlineKeyboardButton("💳 پرداخت آنلاین", url=payment_url)],
                [InlineKeyboardButton("🔍 بررسی وضعیت پرداخت", callback_data=f"{PAYMENT_CALLBACK_CHECK}{payment_data['id']}")],
                [InlineKeyboardButton(get_message('cancel', user_lang), callback_data=PAYMENT_CALLBACK_CANCEL)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # ارسال پیام با لینک پرداخت
            await callback_query.edit_message_text(
                text=f"🔄 در حال انتقال به درگاه پرداخت...\n\n"
                     f"🔹 شناسه پرداخت: {payment_data['id']}\n"
                     f"💰 مبلغ: {payment_data['amount']:,} تومان\n\n"
                     f"پس از تکمیل پرداخت، روی دکمه «بررسی وضعیت پرداخت» کلیک کنید.",
                reply_markup=reply_markup
            )
        
        logger.info(f"کاربر {user.id} درخواست پرداخت با شناسه {payment_data['id']} و درگاه {gateway} ایجاد کرد.")
        
    except Exception as e:
        logger.error(f"خطا در پردازش پرداخت: {str(e)}")
        
        # نمایش پیام خطا
        await callback_query.edit_message_text(
            text=get_message('error', user_lang).format(message=str(e))
        )

async def show_crypto_payment(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           payment_id: int, result: Dict[str, Any]) -> None:
    """
    نمایش اطلاعات پرداخت ارز دیجیتال.
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        payment_id: شناسه پرداخت
        result: نتیجه پردازش پرداخت
    """
    callback_query = update.callback_query
    user = callback_query.from_user
    
    # دریافت پایگاه داده از کانتکست
    database = context.bot_data.get('database')
    
    # دریافت زبان کاربر
    user_lang = database.get_user_language(user.id) or 'fa'
    
    # دریافت اطلاعات ارز دیجیتال
    crypto_info = result.get('crypto_info', {})
    
    currency = crypto_info.get('currency', 'USDT')
    network = crypto_info.get('network', 'TRC20')
    address = crypto_info.get('address', '')
    amount = crypto_info.get('amount', 0)
    expires_at = crypto_info.get('expires_at', 0)
    
    # محاسبه زمان انقضا
    import datetime as dt
    expiry_time = dt.datetime.fromtimestamp(expires_at).strftime('%H:%M:%S')
    
    # ساخت پیام پرداخت ارز دیجیتال
    message = f"💰 پرداخت با ارز دیجیتال\n\n"
    message += f"🔹 شناسه پرداخت: {payment_id}\n"
    message += f"🪙 ارز: {currency}\n"
    message += f"🌐 شبکه: {network}\n"
    message += f"💵 مبلغ: {amount:.6f} {currency}\n"
    message += f"⏱ مهلت پرداخت تا ساعت: {expiry_time}\n\n"
    message += f"📝 آدرس کیف پول:\n`{address}`\n\n"
    message += "برای مشاهده جزئیات بیشتر و QR Code، روی دکمه زیر کلیک کنید."
    
    # ساخت دکمه‌ها
    keyboard = [
        [InlineKeyboardButton("🔍 جزئیات بیشتر", callback_data=f"{PAYMENT_CALLBACK_CRYPTO}{payment_id}")],
        [InlineKeyboardButton("🔍 بررسی وضعیت پرداخت", callback_data=f"{PAYMENT_CALLBACK_CHECK}{payment_id}")],
        [InlineKeyboardButton(get_message('cancel', user_lang), callback_data=PAYMENT_CALLBACK_CANCEL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام
    await callback_query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    logger.info(f"اطلاعات پرداخت ارز دیجیتال برای کاربر {user.id} نمایش داده شد.")

async def show_manual_payment(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           payment_id: int, result: Dict[str, Any]) -> None:
    """
    نمایش اطلاعات پرداخت دستی.
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        payment_id: شناسه پرداخت
        result: نتیجه پردازش پرداخت
    """
    callback_query = update.callback_query
    user = callback_query.from_user
    
    # دریافت پایگاه داده از کانتکست
    database = context.bot_data.get('database')
    
    # دریافت زبان کاربر
    user_lang = database.get_user_language(user.id) or 'fa'
    
    # دریافت اطلاعات پرداخت دستی
    manual_info = result.get('manual_info', {})
    
    bank_name = manual_info.get('bank_name', '')
    account_number = manual_info.get('account_number', '')
    card_number = manual_info.get('card_number', '')
    owner_name = manual_info.get('owner_name', '')
    amount = manual_info.get('amount', 0)
    reference_id = manual_info.get('reference_id', '')
    
    # ساخت پیام پرداخت دستی
    message = f"💰 پرداخت دستی (کارت به کارت)\n\n"
    message += f"🔹 شناسه پرداخت: {payment_id}\n"
    message += f"💰 مبلغ: {amount:,} تومان\n\n"
    message += f"🏦 نام بانک: {bank_name}\n"
    message += f"💳 شماره کارت: `{card_number}`\n"
    message += f"📝 شماره حساب: {account_number}\n"
    message += f"👤 به نام: {owner_name}\n\n"
    message += f"⚠️ مهم: لطفاً شناسه پیگیری را به عنوان توضیحات واریز وارد کنید:\n`{reference_id}`\n\n"
    message += "پس از انجام پرداخت، شناسه پیگیری بانکی را برای ادمین ارسال کنید."
    
    # ساخت دکمه‌ها
    keyboard = [
        [InlineKeyboardButton("📞 ارسال رسید به پشتیبانی", callback_data="support")],
        [InlineKeyboardButton("🔍 بررسی وضعیت پرداخت", callback_data=f"{PAYMENT_CALLBACK_CHECK}{payment_id}")],
        [InlineKeyboardButton(get_message('cancel', user_lang), callback_data=PAYMENT_CALLBACK_CANCEL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام
    await callback_query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    logger.info(f"اطلاعات پرداخت دستی برای کاربر {user.id} نمایش داده شد.")

async def show_crypto_details(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_id: int) -> None:
    """
    نمایش جزئیات بیشتر پرداخت ارز دیجیتال.
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        payment_id: شناسه پرداخت
    """
    callback_query = update.callback_query
    user = callback_query.from_user
    chat_id = callback_query.message.chat_id
    
    # دریافت پایگاه داده و مدیر پرداخت از کانتکست
    database = context.bot_data.get('database')
    global payment_manager
    
    # دریافت زبان کاربر
    user_lang = database.get_user_language(user.id) or 'fa'
    
    try:
        # دریافت اطلاعات پرداخت
        payment_data = database.get_payment(payment_id)
        
        if not payment_data or payment_data['user_id'] != user.id:
            raise ValueError("اطلاعات پرداخت یافت نشد.")
        
        # در اینجا، ما باید اطلاعات ارز دیجیتال را از پردازش مجدد یا کش بازیابی کنیم
        # برای سادگی، دوباره پردازش می‌کنیم
        result = await payment_manager.process_payment(payment_data)
        
        if not result['success'] or 'crypto_info' not in result:
            raise ValueError("اطلاعات پرداخت ارز دیجیتال یافت نشد.")
        
        crypto_info = result['crypto_info']
        
        # ساخت تصویر QR Code
        import qrcode
        from io import BytesIO
        
        address = crypto_info.get('address', '')
        amount = crypto_info.get('amount', 0)
        currency = crypto_info.get('currency', 'USDT')
        
        # ساخت متن QR که شامل آدرس و مبلغ است
        qr_text = f"{currency}:{address}?amount={amount}"
        
        # ساخت QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_text)
        qr.make(fit=True)
        
        # تبدیل به تصویر
        img = qr.make_image(fill_color="black", back_color="white")
        
        # ذخیره در حافظه
        bio = BytesIO()
        bio.name = 'crypto_payment.png'
        img.save(bio, 'PNG')
        bio.seek(0)
        
        # ارسال تصویر QR Code
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=bio,
            caption=f"🔍 QR Code پرداخت ارز دیجیتال\n\n"
                   f"🪙 ارز: {currency}\n"
                   f"💵 مبلغ: {amount:.6f} {currency}\n"
                   f"📝 آدرس: {address}"
        )
        
        logger.info(f"جزئیات QR Code پرداخت ارز دیجیتال برای کاربر {user.id} نمایش داده شد.")
        
    except Exception as e:
        logger.error(f"خطا در نمایش جزئیات ارز دیجیتال: {str(e)}")
        
        # نمایش پیام خطا
        await callback_query.answer(
            text=f"خطا: {str(e)}",
            show_alert=True
        )

async def check_payment(update: Update, context: ContextTypes.DEFAULT_TYPE,
                      payment_id: int, show_result: bool = False) -> None:
    """
    بررسی وضعیت پرداخت.
    
    پارامترها:
        update: آبجکت آپدیت تلگرام
        context: کانتکست ربات
        payment_id: شناسه پرداخت
        show_result: آیا نتیجه نمایش داده شود؟
    """
    callback_query = update.callback_query
    user = callback_query.from_user
    
    # دریافت پایگاه داده و مدیر پرداخت از کانتکست
    database = context.bot_data.get('database')
    global payment_manager
    
    # دریافت زبان کاربر
    user_lang = database.get_user_language(user.id) or 'fa'
    
    # نمایش پیام در حال بررسی
    if show_result:
        await callback_query.edit_message_text(
            text=get_message('processing', user_lang)
        )
    
    try:
        # بررسی وضعیت پرداخت
        status_result = await payment_manager.check_payment_status(payment_id)
        
        # اگر نمایش نتیجه خواسته شده
        if show_result:
            status = status_result['status']
            
            if status == 'completed':
                # پرداخت موفق
                message = get_message('payment_success', user_lang)
                
                # دریافت اطلاعات اشتراک
                subscription = payment_manager.check_subscription(user.id)
                
                if subscription['has_subscription']:
                    message += f"\n\n✅ اشتراک شما تا تاریخ {subscription['expiry_date']} فعال است."
                
                # دکمه بازگشت به منوی اصلی
                keyboard = [[InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await callback_query.edit_message_text(
                    text=message,
                    reply_markup=reply_markup
                )
                
            elif status == 'pending':
                # پرداخت در انتظار
                message = "⏳ پرداخت شما هنوز در حال پردازش است.\n\n"
                message += "لطفاً پس از چند دقیقه مجدداً وضعیت را بررسی کنید."
                
                # دکمه‌های اقدام
                keyboard = [
                    [InlineKeyboardButton("🔄 بررسی مجدد", callback_data=f"{PAYMENT_CALLBACK_CHECK}{payment_id}")],
                    [InlineKeyboardButton(get_message('cancel', user_lang), callback_data=PAYMENT_CALLBACK_CANCEL)]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await callback_query.edit_message_text(
                    text=message,
                    reply_markup=reply_markup
                )
                
            else:
                # پرداخت ناموفق
                message = get_message('payment_failed', user_lang)
                
                # دکمه‌های اقدام
                keyboard = [
                    [InlineKeyboardButton("🔄 تلاش مجدد", callback_data=f"{PAYMENT_CALLBACK_PREFIX}back")],
                    [InlineKeyboardButton("📞 تماس با پشتیبانی", callback_data="support")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await callback_query.edit_message_text(
                    text=message,
                    reply_markup=reply_markup
                )
        
        logger.info(f"وضعیت پرداخت {payment_id} برای کاربر {user.id}: {status_result['status']}")
        
    except Exception as e:
        logger.error(f"خطا در بررسی وضعیت پرداخت: {str(e)}")
        
        if show_result:
            # نمایش پیام خطا
            await callback_query.edit_message_text(
                text=get_message('error', user_lang).format(message=str(e))
            )

def register_payment_handlers(application: Application, config: Dict[str, Any], database: Database, cache: Cache) -> None:
    """
    ثبت هندلرهای پرداخت.
    
    پارامترها:
        application: آبجکت اپلیکیشن تلگرام
        config: تنظیمات برنامه
        database: شیء پایگاه داده
        cache: سیستم کش
    """
    # ایجاد مدیر پرداخت
    global payment_manager
    payment_manager = PaymentManager(database, config, cache)
    
    # ثبت هندلرهای دستورات پرداخت
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    
    # ثبت هندلر کالبک‌های پرداخت
    application.add_handler(
        CallbackQueryHandler(
            handle_payment_callback, 
            pattern=f"^{PAYMENT_CALLBACK_PREFIX}"
        )
    )
    
    logger.info("هندلرهای پرداخت با موفقیت ثبت شدند.")