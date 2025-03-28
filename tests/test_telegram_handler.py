#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
تست‌های مربوط به هندلر تلگرام

این ماژول شامل تست‌های مختلف برای بررسی عملکرد صحیح هندلر تلگرام است،
از جمله پردازش پیام‌های ورودی، دستورات، مدیریت حالت‌ها و غیره.
"""

import os
import sys
import unittest
import json
import time
import datetime
from unittest import mock
from unittest.mock import patch, MagicMock, PropertyMock

# افزودن مسیر ریشه پروژه به sys.path برای واردسازی ماژول‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.handlers.telegram_handler import (
    TelegramHandler,
    MessageProcessor,
    process_message,
    process_callback,
    handle_command,
    get_user_state,
    set_user_state
)
from src.core.bot import Bot
from src.models.user import User
from src.utils.localization import Localization


# ساختار مجازی برای پیام تلگرام
def create_telegram_message(
    message_id=1,
    from_user=None,
    chat_id=123456,
    chat_type="private",
    text=None,
    date=None,
    **kwargs
):
    """
    ایجاد ساختار مجازی برای پیام تلگرام
    """
    if from_user is None:
        from_user = {
            "id": 123456,
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser",
            "language_code": "en"
        }
    
    if date is None:
        date = int(time.time())
    
    message = {
        "message_id": message_id,
        "from": from_user,
        "chat": {
            "id": chat_id,
            "type": chat_type,
            "first_name": from_user.get("first_name"),
            "last_name": from_user.get("last_name"),
            "username": from_user.get("username")
        },
        "date": date
    }
    
    if text:
        message["text"] = text
    
    # اضافه کردن سایر فیلدهای اختیاری
    message.update(kwargs)
    
    return message


# ساختار مجازی برای callback query تلگرام
def create_telegram_callback_query(
    query_id="123456789",
    from_user=None,
    data=None,
    message=None,
    **kwargs
):
    """
    ایجاد ساختار مجازی برای callback query تلگرام
    """
    if from_user is None:
        from_user = {
            "id": 123456,
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser",
            "language_code": "en"
        }
    
    if message is None:
        message = create_telegram_message(from_user=from_user)
    
    callback_query = {
        "id": query_id,
        "from": from_user,
        "message": message,
    }
    
    if data:
        callback_query["data"] = data
    
    # اضافه کردن سایر فیلدهای اختیاری
    callback_query.update(kwargs)
    
    return callback_query


class MockBot:
    """
    کلاس مجازی برای شبیه‌سازی ربات تلگرام
    """
    
    def __init__(self):
        """
        مقداردهی اولیه
        """
        self.sent_messages = []
        self.answered_callbacks = []
        self.edited_messages = []
        self.deleted_messages = []
    
    async def send_message(self, chat_id, text, **kwargs):
        """
        ارسال پیام
        """
        message = {
            "chat_id": chat_id,
            "text": text,
            **kwargs
        }
        self.sent_messages.append(message)
        return {
            "message_id": len(self.sent_messages),
            "chat": {"id": chat_id},
            "text": text,
            **kwargs
        }
    
    async def answer_callback_query(self, callback_query_id, **kwargs):
        """
        پاسخ به callback query
        """
        answer = {
            "callback_query_id": callback_query_id,
            **kwargs
        }
        self.answered_callbacks.append(answer)
        return True
    
    async def edit_message_text(self, chat_id, message_id, text, **kwargs):
        """
        ویرایش پیام
        """
        edit = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            **kwargs
        }
        self.edited_messages.append(edit)
        return {
            "message_id": message_id,
            "chat": {"id": chat_id},
            "text": text,
            **kwargs
        }
    
    async def delete_message(self, chat_id, message_id):
        """
        حذف پیام
        """
        delete = {
            "chat_id": chat_id,
            "message_id": message_id
        }
        self.deleted_messages.append(delete)
        return True


class MockDatabase:
    """
    کلاس مجازی برای شبیه‌سازی پایگاه داده
    """
    
    def __init__(self):
        """
        مقداردهی اولیه
        """
        self.users = {}
        self.user_states = {}
        self.subscriptions = {}
        self.saved_data = {}
    
    def get_user(self, user_id):
        """
        دریافت کاربر از پایگاه داده
        """
        return self.users.get(user_id)
    
    def save_user(self, user):
        """
        ذخیره کاربر در پایگاه داده
        """
        self.users[user.id] = user
        return user
    
    def get_user_state(self, user_id):
        """
        دریافت وضعیت کاربر
        """
        return self.user_states.get(user_id, {"state": None, "data": {}})
    
    def set_user_state(self, user_id, state, data=None):
        """
        تنظیم وضعیت کاربر
        """
        if data is None:
            data = {}
        
        self.user_states[user_id] = {"state": state, "data": data}
        return self.user_states[user_id]
    
    def get_user_subscription(self, user_id):
        """
        دریافت اشتراک کاربر
        """
        return self.subscriptions.get(user_id)
    
    def save_data(self, collection, document_id, data):
        """
        ذخیره داده در پایگاه داده
        """
        if collection not in self.saved_data:
            self.saved_data[collection] = {}
        
        self.saved_data[collection][document_id] = data
        return data
    
    def get_data(self, collection, document_id):
        """
        دریافت داده از پایگاه داده
        """
        if collection not in self.saved_data:
            return None
        
        return self.saved_data[collection].get(document_id)


class TestTelegramHandler(unittest.TestCase):
    """
    تست کلاس TelegramHandler
    """
    
    def setUp(self):
        """
        تنظیمات اولیه قبل از هر تست
        """
        # ایجاد نمونه مجازی از ربات تلگرام
        self.mock_bot = MockBot()
        
        # ایجاد نمونه مجازی از پایگاه داده
        self.mock_db = MockDatabase()
        
        # ایجاد نمونه از هندلر تلگرام
        self.handler = TelegramHandler(bot=self.mock_bot, db=self.mock_db)
        
        # ایجاد کاربر آزمایشی
        self.test_user = User(
            id=123456,
            username="testuser",
            first_name="Test",
            last_name="User",
            is_premium=False
        )
        self.mock_db.users[self.test_user.id] = self.test_user
        
        # پچ کردن کلاس Localization
        self.localization_patcher = patch('src.utils.localization.Localization')
        self.mock_localization_class = self.localization_patcher.start()
        self.mock_localization = MagicMock()
        self.mock_localization.get_message.return_value = "Test Message"
        self.mock_localization_class.return_value = self.mock_localization
    
    def tearDown(self):
        """
        پاکسازی بعد از هر تست
        """
        # خاتمه تمام پچ‌ها
        self.localization_patcher.stop()
    
    @mock.patch('src.handlers.telegram_handler.process_message')
    async def test_handle_message(self, mock_process_message):
        """
        تست پردازش پیام‌های دریافتی
        """
        # تنظیم mock
        mock_process_message.return_value = "Test Response"
        
        # ایجاد پیام آزمایشی
        message = create_telegram_message(text="/start")
        
        # فراخوانی متد
        await self.handler.handle_message(message)
        
        # بررسی فراخوانی process_message
        mock_process_message.assert_called_once()
        args, kwargs = mock_process_message.call_args
        self.assertEqual(args[0], self.handler)
        self.assertEqual(args[1], message)
        
        # بررسی ارسال پیام پاسخ
        self.assertEqual(len(self.mock_bot.sent_messages), 1)
        sent_message = self.mock_bot.sent_messages[0]
        self.assertEqual(sent_message["chat_id"], message["chat"]["id"])
        self.assertEqual(sent_message["text"], "Test Response")
    
    @mock.patch('src.handlers.telegram_handler.process_callback')
    async def test_handle_callback_query(self, mock_process_callback):
        """
        تست پردازش callback query‌های دریافتی
        """
        # تنظیم mock
        mock_process_callback.return_value = {"text": "Callback Response", "show_alert": True}
        
        # ایجاد callback query آزمایشی
        callback_query = create_telegram_callback_query(data="test_data")
        
        # فراخوانی متد
        await self.handler.handle_callback_query(callback_query)
        
        # بررسی فراخوانی process_callback
        mock_process_callback.assert_called_once()
        args, kwargs = mock_process_callback.call_args
        self.assertEqual(args[0], self.handler)
        self.assertEqual(args[1], callback_query)
        
        # بررسی پاسخ به callback query
        self.assertEqual(len(self.mock_bot.answered_callbacks), 1)
        answered_callback = self.mock_bot.answered_callbacks[0]
        self.assertEqual(answered_callback["callback_query_id"], callback_query["id"])
        self.assertEqual(answered_callback["text"], "Callback Response")
        self.assertEqual(answered_callback["show_alert"], True)
    
    async def test_command_start(self):
        """
        تست دستور /start
        """
        # ایجاد پیام آزمایشی
        message = create_telegram_message(text="/start")
        
        # فراخوانی متد
        response = await process_message(self.handler, message)
        
        # بررسی پاسخ
        self.assertIn("Test Message", response)  # از mock localization
        
        # بررسی وضعیت کاربر
        user_state = self.mock_db.get_user_state(self.test_user.id)
        self.assertEqual(user_state["state"], "main_menu")
    
    async def test_command_help(self):
        """
        تست دستور /help
        """
        # ایجاد پیام آزمایشی
        message = create_telegram_message(text="/help")
        
        # فراخوانی متد
        response = await process_message(self.handler, message)
        
        # بررسی پاسخ
        self.assertIn("Test Message", response)  # از mock localization
    
    async def test_command_settings(self):
        """
        تست دستور /settings
        """
        # ایجاد پیام آزمایشی
        message = create_telegram_message(text="/settings")
        
        # فراخوانی متد
        response = await process_message(self.handler, message)
        
        # بررسی پاسخ
        self.assertIn("Test Message", response)  # از mock localization
        
        # بررسی وضعیت کاربر
        user_state = self.mock_db.get_user_state(self.test_user.id)
        self.assertEqual(user_state["state"], "settings")
    
    async def test_process_text_message(self):
        """
        تست پردازش پیام متنی معمولی
        """
        # تنظیم وضعیت کاربر
        self.mock_db.set_user_state(self.test_user.id, "waiting_for_name")
        
        # ایجاد پیام آزمایشی
        message = create_telegram_message(text="John Doe")
        
        # فراخوانی متد
        response = await process_message(self.handler, message)
        
        # بررسی پاسخ
        self.assertIn("Test Message", response)  # از mock localization
        
        # بررسی به‌روزرسانی داده‌های وضعیت
        user_state = self.mock_db.get_user_state(self.test_user.id)
        self.assertEqual(user_state["data"].get("name"), "John Doe")
    
    async def test_process_callback_query(self):
        """
        تست پردازش callback query
        """
        # ایجاد callback query آزمایشی
        callback_query = create_telegram_callback_query(data="settings:language:fa")
        
        # فراخوانی متد
        response = await process_callback(self.handler, callback_query)
        
        # بررسی پاسخ
        self.assertIn("text", response)
        self.assertIn("Test Message", response["text"])  # از mock localization
        
        # بررسی به‌روزرسانی تنظیمات کاربر
        user = self.mock_db.get_user(self.test_user.id)
        self.assertEqual(user.language, "fa")
    
    def test_get_user_state(self):
        """
        تست دریافت وضعیت کاربر
        """
        # تنظیم داده آزمایشی
        self.mock_db.set_user_state(self.test_user.id, "test_state", {"key": "value"})
        
        # فراخوانی تابع
        state, data = get_user_state(self.mock_db, self.test_user.id)
        
        # بررسی نتایج
        self.assertEqual(state, "test_state")
        self.assertEqual(data, {"key": "value"})
    
    def test_set_user_state(self):
        """
        تست تنظیم وضعیت کاربر
        """
        # فراخوانی تابع
        set_user_state(self.mock_db, self.test_user.id, "new_state", {"key": "new_value"})
        
        # بررسی نتایج
        state, data = get_user_state(self.mock_db, self.test_user.id)
        self.assertEqual(state, "new_state")
        self.assertEqual(data, {"key": "new_value"})


class TestMessageProcessor(unittest.TestCase):
    """
    تست کلاس MessageProcessor
    """
    
    def setUp(self):
        """
        تنظیمات اولیه قبل از هر تست
        """
        # ایجاد نمونه مجازی از ربات تلگرام
        self.mock_bot = MockBot()
        
        # ایجاد نمونه مجازی از پایگاه داده
        self.mock_db = MockDatabase()
        
        # ایجاد نمونه از پردازشگر پیام
        self.processor = MessageProcessor(bot=self.mock_bot, db=self.mock_db)
        
        # ایجاد کاربر آزمایشی
        self.test_user = User(
            id=123456,
            username="testuser",
            first_name="Test",
            last_name="User",
            is_premium=False
        )
        self.mock_db.users[self.test_user.id] = self.test_user
        
        # پچ کردن کلاس Localization
        self.localization_patcher = patch('src.utils.localization.Localization')
        self.mock_localization_class = self.localization_patcher.start()
        self.mock_localization = MagicMock()
        self.mock_localization.get_message.return_value = "Test Message"
        self.mock_localization_class.return_value = self.mock_localization
    
    def tearDown(self):
        """
        پاکسازی بعد از هر تست
        """
        # خاتمه تمام پچ‌ها
        self.localization_patcher.stop()
    
    async def test_process_command(self):
        """
        تست پردازش دستور
        """
        # ایجاد پیام آزمایشی
        message = create_telegram_message(text="/test param1 param2")
        
        # پچ کردن متد handle_command
        with patch.object(self.processor, 'handle_command') as mock_handle_command:
            mock_handle_command.return_value = "Command Response"
            
            # فراخوانی متد
            response = await self.processor.process_message(message)
            
            # بررسی نتایج
            self.assertEqual(response, "Command Response")
            mock_handle_command.assert_called_once_with("test", ["param1", "param2"], message)
    
    async def test_process_text_by_state(self):
        """
        تست پردازش متن بر اساس وضعیت کاربر
        """
        # تنظیم وضعیت کاربر
        self.mock_db.set_user_state(self.test_user.id, "waiting_for_email")
        
        # ایجاد پیام آزمایشی
        message = create_telegram_message(text="test@example.com")
        
        # پچ کردن متد handle_state
        with patch.object(self.processor, 'handle_state') as mock_handle_state:
            mock_handle_state.return_value = "State Response"
            
            # فراخوانی متد
            response = await self.processor.process_message(message)
            
            # بررسی نتایج
            self.assertEqual(response, "State Response")
            mock_handle_state.assert_called_once_with("waiting_for_email", message, {})
    
    async def test_process_callback(self):
        """
        تست پردازش callback query
        """
        # ایجاد callback query آزمایشی
        callback_query = create_telegram_callback_query(data="section:action:param")
        
        # پچ کردن متد handle_callback
        with patch.object(self.processor, 'handle_callback') as mock_handle_callback:
            mock_handle_callback.return_value = {"text": "Callback Response"}
            
            # فراخوانی متد
            response = await self.processor.process_callback(callback_query)
            
            # بررسی نتایج
            self.assertEqual(response, {"text": "Callback Response"})
            mock_handle_callback.assert_called_once_with("section", "action", "param", callback_query)
    
    async def test_handle_unknown_command(self):
        """
        تست پردازش دستور ناشناخته
        """
        # ایجاد پیام آزمایشی
        message = create_telegram_message(text="/unknown")
        
        # فراخوانی متد
        response = await self.processor.process_message(message)
        
        # بررسی پاسخ
        self.assertIn("Test Message", response)  # از mock localization - پیام دستور ناشناخته
    
    @patch('src.models.user.User.get_or_create')
    async def test_handle_new_user(self, mock_get_or_create):
        """
        تست پردازش پیام از کاربر جدید
        """
        # تنظیم mock
        new_user = User(
            id=789012,
            username="newuser",
            first_name="New",
            last_name="User",
            is_premium=False
        )
        mock_get_or_create.return_value = (new_user, True)  # کاربر جدید ایجاد شده است
        
        # ایجاد پیام آزمایشی
        message = create_telegram_message(
            from_user={
                "id": 789012,
                "first_name": "New",
                "last_name": "User",
                "username": "newuser",
                "language_code": "en"
            },
            text="Hello"
        )
        
        # فراخوانی متد
        response = await self.processor.process_message(message)
        
        # بررسی پاسخ
        self.assertIn("Test Message", response)  # پیام خوش‌آمدگویی
        
        # بررسی فراخوانی get_or_create
        mock_get_or_create.assert_called_once()
        args, kwargs = mock_get_or_create.call_args
        self.assertEqual(kwargs["user_id"], 789012)
        self.assertEqual(kwargs["username"], "newuser")
        self.assertEqual(kwargs["first_name"], "New")
        self.assertEqual(kwargs["last_name"], "User")
 

if __name__ == '__main__':
    unittest.main()