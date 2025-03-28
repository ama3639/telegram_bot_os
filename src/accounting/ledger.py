#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول دفتر کل حسابداری برای مدیریت حساب‌ها و تراکنش‌های مالی.
این ماژول امکان ایجاد، ثبت و گزارش‌گیری از تراکنش‌های مالی را فراهم می‌کند.
"""


from datetime import timezone
import logging
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime
from utils.timezone_utils import get_current_datetime, timezone, timedelta
from enum import Enum, auto
import uuid
import json
from dataclasses import dataclass, asdict, field

from utils.security import encrypt_sensitive_data, decrypt_sensitive_data
from utils.timezone_utils import get_user_timezone, convert_to_user_timezone

logger = logging.getLogger('accounting.ledger')

class AccountType(Enum):
    """
    انواع حساب‌های مالی
    """
    ASSET = auto()        # دارایی
    LIABILITY = auto()    # بدهی
    EQUITY = auto()       # سرمایه
    REVENUE = auto()      # درآمد
    EXPENSE = auto()      # هزینه 

class TransactionType(Enum):
    """
    انواع تراکنش‌های مالی
    """
    DEPOSIT = auto()      # واریز
    WITHDRAWAL = auto()   # برداشت
    TRANSFER = auto()     # انتقال
    PAYMENT = auto()      # پرداخت
    REFUND = auto()       # استرداد
    ADJUSTMENT = auto()   # تعدیل
    FEE = auto()          # کارمزد

@dataclass
class Account:
    """
    کلاس نماینده یک حساب مالی
    """
    account_id: str
    name: str
    account_type: AccountType
    currency: str = "IRR"  # ارز پیش‌فرض ریال ایران
    description: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    balance: float = 0.0
    user_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create(cls, name: str, account_type: AccountType, currency: str = "IRR", 
               description: str = "", user_id: Optional[int] = None) -> 'Account':
        """
        ایجاد یک حساب جدید
        
        Args:
            name: نام حساب
            account_type: نوع حساب
            currency: ارز حساب
            description: توضیحات
            user_id: شناسه کاربر مالک حساب (اختیاری)
            
        Returns:
            Account: آبجکت حساب جدید
        """
        return cls(
            account_id=str(uuid.uuid4()),
            name=name,
            account_type=account_type,
            currency=currency,
            description=description,
            is_active=True,
            created_at=get_current_datetime(),
            balance=0.0,
            user_id=user_id,
            metadata={}
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        تبدیل حساب به دیکشنری
        
        Returns:
            Dict[str, Any]: دیکشنری حاوی اطلاعات حساب
        """
        result = asdict(self)
        # تبدیل فیلدهای Enum به رشته
        result['account_type'] = self.account_type.name
        # تبدیل تاریخ‌ها به رشته
        result['created_at'] = self.created_at.isoformat()
        return result

@dataclass
class Transaction:
    """
    کلاس نماینده یک تراکنش مالی
    """
    transaction_id: str
    transaction_type: TransactionType
    amount: float
    currency: str
    description: str
    source_account_id: Optional[str]
    destination_account_id: Optional[str]
    user_id: Optional[int]
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "pending"  # وضعیت‌های: pending, completed, failed, cancelled
    reference_id: Optional[str] = None  # شناسه مرجع خارجی
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create(cls, transaction_type: TransactionType, amount: float, currency: str,
              description: str, source_account_id: Optional[str] = None, 
              destination_account_id: Optional[str] = None, user_id: Optional[int] = None,
              reference_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> 'Transaction':
        """
        ایجاد یک تراکنش جدید
        
        Args:
            transaction_type: نوع تراکنش
            amount: مبلغ تراکنش
            currency: ارز تراکنش
            description: توضیحات
            source_account_id: شناسه حساب مبدأ (اختیاری)
            destination_account_id: شناسه حساب مقصد (اختیاری)
            user_id: شناسه کاربر (اختیاری)
            reference_id: شناسه مرجع خارجی (اختیاری)
            metadata: متادیتای اضافی (اختیاری)
            
        Returns:
            Transaction: آبجکت تراکنش جدید
        """
        if amount <= 0:
            raise ValueError("مبلغ تراکنش باید بزرگتر از صفر باشد")
            
        # بررسی منطقی بودن نوع تراکنش و حساب‌ها
        if transaction_type in [TransactionType.DEPOSIT, TransactionType.REFUND] and not destination_account_id:
            raise ValueError(f"تراکنش از نوع {transaction_type.name} نیاز به حساب مقصد دارد")
            
        if transaction_type in [TransactionType.WITHDRAWAL, TransactionType.PAYMENT] and not source_account_id:
            raise ValueError(f"تراکنش از نوع {transaction_type.name} نیاز به حساب مبدأ دارد")
            
        if transaction_type == TransactionType.TRANSFER and (not source_account_id or not destination_account_id):
            raise ValueError("تراکنش از نوع انتقال نیاز به حساب مبدأ و مقصد دارد")
        
        return cls(
            transaction_id=str(uuid.uuid4()),
            transaction_type=transaction_type,
            amount=amount,
            currency=currency,
            description=description,
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            user_id=user_id,
            created_at=get_current_datetime(),
            status="pending",
            reference_id=reference_id,
            metadata=metadata or {}
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        تبدیل تراکنش به دیکشنری
        
        Returns:
            Dict[str, Any]: دیکشنری حاوی اطلاعات تراکنش
        """
        result = asdict(self)
        # تبدیل فیلدهای Enum به رشته
        result['transaction_type'] = self.transaction_type.name
        # تبدیل تاریخ‌ها به رشته
        result['created_at'] = self.created_at.isoformat()
        return result

class Ledger:
    """
    کلاس دفتر کل برای مدیریت حساب‌ها و تراکنش‌ها
    """
    
    def __init__(self, db):
        """
        مقداردهی اولیه دفتر کل
        
        Args:
            db: آبجکت دیتابیس
        """
        self.db = db
        self._accounts_cache = {}  # کش حساب‌ها برای بهبود عملکرد
    
    def create_account(self, name: str, account_type: AccountType, currency: str = "IRR", 
                      description: str = "", user_id: Optional[int] = None) -> Account:
        """
        ایجاد یک حساب جدید و ذخیره در دیتابیس
        
        Args:
            name: نام حساب
            account_type: نوع حساب
            currency: ارز حساب
            description: توضیحات
            user_id: شناسه کاربر مالک حساب (اختیاری)
            
        Returns:
            Account: آبجکت حساب ایجاد شده
        """
        account = Account.create(name, account_type, currency, description, user_id)
        
        try:
            # ذخیره حساب در دیتابیس
            self.db.execute(
                "INSERT INTO accounts (account_id, name, account_type, currency, description, "
                "is_active, created_at, balance, user_id, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    account.account_id,
                    account.name,
                    account.account_type.name,
                    account.currency,
                    account.description,
                    int(account.is_active),
                    account.created_at,
                    account.balance,
                    account.user_id,
                    json.dumps(account.metadata)
                )
            )
            
            # افزودن به کش
            self._accounts_cache[account.account_id] = account
            
            logger.info(f"حساب جدید ایجاد شد: {account.account_id} - {account.name}")
            return account
            
        except Exception as e:
            logger.error(f"خطا در ایجاد حساب: {e}")
            raise
    
    def get_account(self, account_id: str) -> Optional[Account]:
        """
        دریافت اطلاعات یک حساب با شناسه آن
        
        Args:
            account_id: شناسه حساب
            
        Returns:
            Optional[Account]: آبجکت حساب یا None در صورت عدم وجود
        """
        # بررسی کش
        if account_id in self._accounts_cache:
            return self._accounts_cache[account_id]
        
        try:
            # دریافت از دیتابیس
            account_data = self.db.execute(
                "SELECT account_id, name, account_type, currency, description, "
                "is_active, created_at, balance, user_id, metadata "
                "FROM accounts WHERE account_id = ?",
                (account_id,)
            )
            
            if not account_data:
                return None
            
            # ساخت آبجکت حساب
            account_row = account_data[0]
            
            account = Account(
                account_id=account_row[0],
                name=account_row[1],
                account_type=AccountType[account_row[2]],  # تبدیل نام به Enum
                currency=account_row[3],
                description=account_row[4],
                is_active=bool(account_row[5]),
                created_at=account_row[6] if isinstance(account_row[6], datetime) else datetime.fromisoformat(account_row[6]),
                balance=account_row[7],
                user_id=account_row[8],
                metadata=json.loads(account_row[9]) if account_row[9] else {}
            )
            
            # افزودن به کش
            self._accounts_cache[account_id] = account
            
            return account
            
        except Exception as e:
            logger.error(f"خطا در دریافت حساب {account_id}: {e}")
            return None
    
    def update_account_balance(self, account_id: str, amount: float, is_credit: bool = True) -> bool:
        """
        به‌روزرسانی موجودی یک حساب
        
        Args:
            account_id: شناسه حساب
            amount: مبلغ تغییر
            is_credit: آیا افزایش موجودی است (True) یا کاهش (False)
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        try:
            account = self.get_account(account_id)
            if not account:
                logger.error(f"حساب {account_id} یافت نشد")
                return False
                
            # محاسبه موجودی جدید
            if is_credit:
                new_balance = account.balance + amount
            else:
                new_balance = account.balance - amount
                if new_balance < 0 and account.account_type != AccountType.LIABILITY:
                    logger.error(f"برداشت بیش از موجودی برای حساب {account_id}")
                    return False
            
            # به‌روزرسانی در دیتابیس
            self.db.execute(
                "UPDATE accounts SET balance = ? WHERE account_id = ?",
                (new_balance, account_id)
            )
            
            # به‌روزرسانی در کش
            account.balance = new_balance
            self._accounts_cache[account_id] = account
            
            logger.info(f"موجودی حساب {account_id} به‌روزرسانی شد: {account.balance}")
            return True
            
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی موجودی حساب {account_id}: {e}")
            return False
    
    def create_transaction(self, transaction_type: TransactionType, amount: float, currency: str,
                          description: str, source_account_id: Optional[str] = None, 
                          destination_account_id: Optional[str] = None, user_id: Optional[int] = None,
                          reference_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[Transaction]:
        """
        ایجاد یک تراکنش جدید
        
        Args:
            transaction_type: نوع تراکنش
            amount: مبلغ تراکنش
            currency: ارز تراکنش
            description: توضیحات
            source_account_id: شناسه حساب مبدأ (اختیاری)
            destination_account_id: شناسه حساب مقصد (اختیاری)
            user_id: شناسه کاربر (اختیاری)
            reference_id: شناسه مرجع خارجی (اختیاری)
            metadata: متادیتای اضافی (اختیاری)
            
        Returns:
            Optional[Transaction]: آبجکت تراکنش ایجاد شده یا None در صورت خطا
        """
        try:
            # ایجاد تراکنش
            transaction = Transaction.create(
                transaction_type, amount, currency, description,
                source_account_id, destination_account_id, user_id,
                reference_id, metadata
            )
            
            # ذخیره تراکنش در دیتابیس
            self.db.execute(
                "INSERT INTO transactions (transaction_id, transaction_type, amount, currency, "
                "description, source_account_id, destination_account_id, user_id, created_at, "
                "status, reference_id, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    transaction.transaction_id,
                    transaction.transaction_type.name,
                    transaction.amount,
                    transaction.currency,
                    transaction.description,
                    transaction.source_account_id,
                    transaction.destination_account_id,
                    transaction.user_id,
                    transaction.created_at,
                    transaction.status,
                    transaction.reference_id,
                    json.dumps(transaction.metadata)
                )
            )
            
            logger.info(f"تراکنش جدید ایجاد شد: {transaction.transaction_id}")
            return transaction
            
        except Exception as e:
            logger.error(f"خطا در ایجاد تراکنش: {e}")
            return None
    
    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """
        دریافت اطلاعات یک تراکنش با شناسه آن
        
        Args:
            transaction_id: شناسه تراکنش
            
        Returns:
            Optional[Transaction]: آبجکت تراکنش یا None در صورت عدم وجود
        """
        try:
            # دریافت از دیتابیس
            transaction_data = self.db.execute(
                "SELECT transaction_id, transaction_type, amount, currency, description, "
                "source_account_id, destination_account_id, user_id, created_at, "
                "status, reference_id, metadata FROM transactions WHERE transaction_id = ?",
                (transaction_id,)
            )
            
            if not transaction_data:
                return None
            
            # ساخت آبجکت تراکنش
            transaction_row = transaction_data[0]
            
            transaction = Transaction(
                transaction_id=transaction_row[0],
                transaction_type=TransactionType[transaction_row[1]],  # تبدیل نام به Enum
                amount=transaction_row[2],
                currency=transaction_row[3],
                description=transaction_row[4],
                source_account_id=transaction_row[5],
                destination_account_id=transaction_row[6],
                user_id=transaction_row[7],
                created_at=transaction_row[8] if isinstance(transaction_row[8], datetime) else datetime.fromisoformat(transaction_row[8]),
                status=transaction_row[9],
                reference_id=transaction_row[10],
                metadata=json.loads(transaction_row[11]) if transaction_row[11] else {}
            )
            
            return transaction
            
        except Exception as e:
            logger.error(f"خطا در دریافت تراکنش {transaction_id}: {e}")
            return None
    
    def process_transaction(self, transaction_id: str) -> bool:
        """
        پردازش یک تراکنش و اعمال آن روی حساب‌ها
        
        Args:
            transaction_id: شناسه تراکنش
            
        Returns:
            bool: True در صورت موفقیت، False در صورت شکست
        """
        try:
            # دریافت اطلاعات تراکنش
            transaction = self.get_transaction(transaction_id)
            if not transaction:
                logger.error(f"تراکنش {transaction_id} یافت نشد")
                return False
                
            # بررسی وضعیت تراکنش
            if transaction.status != "pending":
                logger.error(f"تراکنش {transaction_id} قبلاً پردازش شده است: {transaction.status}")
                return False
            
            # پردازش بر اساس نوع تراکنش
            if transaction.transaction_type in [TransactionType.DEPOSIT, TransactionType.REFUND]:
                # واریز به حساب مقصد
                success = self.update_account_balance(
                    transaction.destination_account_id,
                    transaction.amount,
                    is_credit=True
                )
                
            elif transaction.transaction_type in [TransactionType.WITHDRAWAL, TransactionType.PAYMENT]:
                # برداشت از حساب مبدأ
                success = self.update_account_balance(
                    transaction.source_account_id,
                    transaction.amount,
                    is_credit=False
                )
                
            elif transaction.transaction_type == TransactionType.TRANSFER:
                # برداشت از حساب مبدأ
                success1 = self.update_account_balance(
                    transaction.source_account_id,
                    transaction.amount,
                    is_credit=False
                )
                
                # واریز به حساب مقصد
                success2 = self.update_account_balance(
                    transaction.destination_account_id,
                    transaction.amount,
                    is_credit=True
                )
                
                success = success1 and success2
                
            elif transaction.transaction_type == TransactionType.FEE:
                # برداشت کارمزد از حساب مبدأ
                success = self.update_account_balance(
                    transaction.source_account_id,
                    transaction.amount,
                    is_credit=False
                )
                
            elif transaction.transaction_type == TransactionType.ADJUSTMENT:
                # تعدیل حساب (می‌تواند افزایش یا کاهش باشد)
                is_credit = transaction.metadata.get('is_credit', True) if transaction.metadata else True
                account_id = transaction.destination_account_id if is_credit else transaction.source_account_id
                
                success = self.update_account_balance(
                    account_id,
                    transaction.amount,
                    is_credit=is_credit
                )
                
            else:
                logger.error(f"نوع تراکنش {transaction.transaction_type.name} پشتیبانی نشده است")
                success = False
            
            # به‌روزرسانی وضعیت تراکنش
            if success:
                self.db.execute(
                    "UPDATE transactions SET status = ? WHERE transaction_id = ?",
                    ("completed", transaction_id)
                )
                logger.info(f"تراکنش {transaction_id} با موفقیت پردازش شد")
            else:
                self.db.execute(
                    "UPDATE transactions SET status = ? WHERE transaction_id = ?",
                    ("failed", transaction_id)
                )
                logger.error(f"پردازش تراکنش {transaction_id} با خطا مواجه شد")
            
            return success
            
        except Exception as e:
            logger.error(f"خطا در پردازش تراکنش {transaction_id}: {e}")
            
            # ثبت وضعیت خطا برای تراکنش
            try:
                self.db.execute(
                    "UPDATE transactions SET status = ? WHERE transaction_id = ?",
                    ("failed", transaction_id)
                )
            except:
                pass
                
            return False
    
    def get_user_transactions(self, user_id: int, start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None, status: Optional[str] = None,
                             limit: int = 50) -> List[Transaction]:
        """
        دریافت تراکنش‌های یک کاربر
        
        Args:
            user_id: شناسه کاربر
            start_date: تاریخ شروع (اختیاری)
            end_date: تاریخ پایان (اختیاری)
            status: وضعیت تراکنش (اختیاری)
            limit: محدودیت تعداد نتایج
            
        Returns:
            List[Transaction]: لیست تراکنش‌ها
        """
        try:
            # ساخت شرط SQL
            conditions = ["user_id = ?"]
            params = [user_id]
            
            if start_date:
                conditions.append("created_at >= ?")
                params.append(start_date)
                
            if end_date:
                conditions.append("created_at <= ?")
                params.append(end_date)
                
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            # ساخت کوئری
            query = f"""
                SELECT transaction_id, transaction_type, amount, currency, description,
                source_account_id, destination_account_id, user_id, created_at,
                status, reference_id, metadata FROM transactions
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC LIMIT ?
            """
            params.append(limit)
            
            # اجرای کوئری
            transaction_data = self.db.execute(query, params)
            
            # تبدیل به آبجکت‌های تراکنش
            transactions = []
            for row in transaction_data:
                transaction = Transaction(
                    transaction_id=row[0],
                    transaction_type=TransactionType[row[1]],
                    amount=row[2],
                    currency=row[3],
                    description=row[4],
                    source_account_id=row[5],
                    destination_account_id=row[6],
                    user_id=row[7],
                    created_at=row[8] if isinstance(row[8], datetime) else datetime.fromisoformat(row[8]),
                    status=row[9],
                    reference_id=row[10],
                    metadata=json.loads(row[11]) if row[11] else {}
                )
                transactions.append(transaction)
                
            return transactions
            
        except Exception as e:
            logger.error(f"خطا در دریافت تراکنش‌های کاربر {user_id}: {e}")
            return []
    
    def get_account_transactions(self, account_id: str, start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None, status: Optional[str] = None,
                               limit: int = 50) -> List[Transaction]:
        """
        دریافت تراکنش‌های یک حساب
        
        Args:
            account_id: شناسه حساب
            start_date: تاریخ شروع (اختیاری)
            end_date: تاریخ پایان (اختیاری)
            status: وضعیت تراکنش (اختیاری)
            limit: محدودیت تعداد نتایج
            
        Returns:
            List[Transaction]: لیست تراکنش‌ها
        """
        try:
            # ساخت شرط SQL
            conditions = ["(source_account_id = ? OR destination_account_id = ?)"]
            params = [account_id, account_id]
            
            if start_date:
                conditions.append("created_at >= ?")
                params.append(start_date)
                
            if end_date:
                conditions.append("created_at <= ?")
                params.append(end_date)
                
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            # ساخت کوئری
            query = f"""
                SELECT transaction_id, transaction_type, amount, currency, description,
                source_account_id, destination_account_id, user_id, created_at,
                status, reference_id, metadata FROM transactions
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC LIMIT ?
            """
            params.append(limit)
            
            # اجرای کوئری
            transaction_data = self.db.execute(query, params)
            
            # تبدیل به آبجکت‌های تراکنش
            transactions = []
            for row in transaction_data:
                transaction = Transaction(
                    transaction_id=row[0],
                    transaction_type=TransactionType[row[1]],
                    amount=row[2],
                    currency=row[3],
                    description=row[4],
                    source_account_id=row[5],
                    destination_account_id=row[6],
                    user_id=row[7],
                    created_at=row[8] if isinstance(row[8], datetime) else datetime.fromisoformat(row[8]),
                    status=row[9],
                    reference_id=row[10],
                    metadata=json.loads(row[11]) if row[11] else {}
                )
                transactions.append(transaction)
                
            return transactions
            
        except Exception as e:
            logger.error(f"خطا در دریافت تراکنش‌های حساب {account_id}: {e}")
            return []
    
    def get_user_accounts(self, user_id: int, is_active: bool = True) -> List[Account]:
        """
        دریافت حساب‌های یک کاربر
        
        Args:
            user_id: شناسه کاربر
            is_active: آیا فقط حساب‌های فعال دریافت شوند
            
        Returns:
            List[Account]: لیست حساب‌ها
        """
        try:
            # ساخت شرط SQL
            conditions = ["user_id = ?"]
            params = [user_id]
            
            if is_active:
                conditions.append("is_active = 1")
            
            # ساخت کوئری
            query = f"""
                SELECT account_id, name, account_type, currency, description,
                is_active, created_at, balance, user_id, metadata
                FROM accounts WHERE {' AND '.join(conditions)}
                ORDER BY name
            """
            
            # اجرای کوئری
            account_data = self.db.execute(query, params)
            
            # تبدیل به آبجکت‌های حساب
            accounts = []
            for row in account_data:
                account = Account(
                    account_id=row[0],
                    name=row[1],
                    account_type=AccountType[row[2]],
                    currency=row[3],
                    description=row[4],
                    is_active=bool(row[5]),
                    created_at=row[6] if isinstance(row[6], datetime) else datetime.fromisoformat(row[6]),
                    balance=row[7],
                    user_id=row[8],
                    metadata=json.loads(row[9]) if row[9] else {}
                )
                accounts.append(account)
                
                # افزودن به کش
                self._accounts_cache[account.account_id] = account
                
            return accounts
            
        except Exception as e:
            logger.error(f"خطا در دریافت حساب‌های کاربر {user_id}: {e}")
            return []
    
    def get_account_balance_history(self, account_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        دریافت تاریخچه موجودی یک حساب
        
        Args:
            account_id: شناسه حساب
            days: تعداد روزهای گذشته
            
        Returns:
            List[Dict[str, Any]]: لیست داده‌های تاریخچه موجودی
        """
        try:
            # دریافت حساب
            account = self.get_account(account_id)
            if not account:
                logger.error(f"حساب {account_id} یافت نشد")
                return []
            
            # تاریخ شروع
            start_date = get_current_datetime() - timedelta(days=days)
            
            # دریافت تراکنش‌های حساب
            transactions = self.get_account_transactions(
                account_id, 
                start_date=start_date,
                status="completed"
            )
            
            # ایجاد دیکشنری تاریخ-موجودی
            balance_history = {}
            current_balance = account.balance
            
            # تنظیم موجودی فعلی
            today = get_current_datetime().date()
            balance_history[today.isoformat()] = current_balance
            
            # محاسبه موجودی برای روزهای گذشته
            for transaction in reversed(transactions):  # از قدیمی‌ترین به جدیدترین
                transaction_date = transaction.created_at.date()
                
                # تنظیم موجودی برای روزهای بین آخرین تراکنش تا این تراکنش
                current_date = today
                while current_date > transaction_date:
                    balance_history[current_date.isoformat()] = current_balance
                    current_date -= timedelta(days=1)
                
                # تغییر موجودی بر اساس نوع تراکنش
                if transaction.source_account_id == account_id:
                    # برداشت از حساب
                    current_balance += transaction.amount  # برگشت به عقب، پس افزایش موجودی
                elif transaction.destination_account_id == account_id:
                    # واریز به حساب
                    current_balance -= transaction.amount  # برگشت به عقب، پس کاهش موجودی
            
            # تبدیل به لیست برای خروجی
            result = []
            for date_str, balance in sorted(balance_history.items()):
                result.append({
                    "date": date_str,
                    "balance": balance
                })
                
            return result
            
        except Exception as e:
            logger.error(f"خطا در دریافت تاریخچه موجودی حساب {account_id}: {e}")
            return []
    
    def create_transfer(self, source_account_id: str, destination_account_id: str,
                       amount: float, description: str, user_id: Optional[int] = None,
                       reference_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[Transaction]:
        """
        ایجاد و پردازش یک تراکنش انتقال بین دو حساب
        
        Args:
            source_account_id: شناسه حساب مبدأ
            destination_account_id: شناسه حساب مقصد
            amount: مبلغ انتقال
            description: توضیحات
            user_id: شناسه کاربر (اختیاری)
            reference_id: شناسه مرجع خارجی (اختیاری)
            metadata: متادیتای اضافی (اختیاری)
            
        Returns:
            Optional[Transaction]: آبجکت تراکنش ایجاد شده یا None در صورت خطا
        """
        try:
            # دریافت حساب‌ها
            source_account = self.get_account(source_account_id)
            destination_account = self.get_account(destination_account_id)
            
            if not source_account or not destination_account:
                logger.error(f"حساب مبدأ یا مقصد یافت نشد")
                return None
                
            # بررسی موجودی کافی
            if source_account.balance < amount:
                logger.error(f"موجودی حساب مبدأ {source_account_id} کافی نیست")
                return None
                
            # بررسی ارز یکسان
            if source_account.currency != destination_account.currency:
                logger.error(f"ارز حساب‌های مبدأ و مقصد متفاوت است")
                return None
                
            # ایجاد تراکنش
            transaction = self.create_transaction(
                TransactionType.TRANSFER,
                amount,
                source_account.currency,
                description,
                source_account_id,
                destination_account_id,
                user_id,
                reference_id,
                metadata
            )
            
            if not transaction:
                return None
                
            # پردازش تراکنش
            success = self.process_transaction(transaction.transaction_id)
            
            if not success:
                logger.error(f"پردازش تراکنش انتقال {transaction.transaction_id} با خطا مواجه شد")
                return None
                
            # دریافت تراکنش به‌روزشده
            return self.get_transaction(transaction.transaction_id)
            
        except Exception as e:
            logger.error(f"خطا در ایجاد تراکنش انتقال: {e}")
            return None
    
    def create_deposit(self, account_id: str, amount: float, currency: str,
                    description: str, user_id: Optional[int] = None,
                    reference_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[Transaction]:
        """
        ایجاد و پردازش یک تراکنش واریز به حساب
        
        Args:
            account_id: شناسه حساب مقصد
            amount: مبلغ واریز
            currency: ارز واریز
            description: توضیحات
            user_id: شناسه کاربر (اختیاری)
            reference_id: شناسه مرجع خارجی (اختیاری)
            metadata: متادیتای اضافی (اختیاری)
            
        Returns:
            Optional[Transaction]: آبجکت تراکنش ایجاد شده یا None در صورت خطا
        """
        try:
            # دریافت حساب
            account = self.get_account(account_id)
            
            if not account:
                logger.error(f"حساب {account_id} یافت نشد")
                return None
                
            # بررسی ارز یکسان
            if account.currency != currency:
                logger.error(f"ارز حساب و واریز متفاوت است")
                return None
                
            # ایجاد تراکنش
            transaction = self.create_transaction(
                TransactionType.DEPOSIT,
                amount,
                currency,
                description,
                None,
                account_id,
                user_id,
                reference_id,
                metadata
            )
            
            if not transaction:
                return None
                
            # پردازش تراکنش
            success = self.process_transaction(transaction.transaction_id)
            
            if not success:
                logger.error(f"پردازش تراکنش واریز {transaction.transaction_id} با خطا مواجه شد")
                return None
                
            # دریافت تراکنش به‌روزشده
            return self.get_transaction(transaction.transaction_id)
            
        except Exception as e:
            logger.error(f"خطا در ایجاد تراکنش واریز: {e}")
            return None
    
    def create_withdrawal(self, account_id: str, amount: float,
                       description: str, user_id: Optional[int] = None,
                       reference_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[Transaction]:
        """
        ایجاد و پردازش یک تراکنش برداشت از حساب
        
        Args:
            account_id: شناسه حساب مبدأ
            amount: مبلغ برداشت
            description: توضیحات
            user_id: شناسه کاربر (اختیاری)
            reference_id: شناسه مرجع خارجی (اختیاری)
            metadata: متادیتای اضافی (اختیاری)
            
        Returns:
            Optional[Transaction]: آبجکت تراکنش ایجاد شده یا None در صورت خطا
        """
        try:
            # دریافت حساب
            account = self.get_account(account_id)
            
            if not account:
                logger.error(f"حساب {account_id} یافت نشد")
                return None
                
            # بررسی موجودی کافی
            if account.balance < amount:
                logger.error(f"موجودی حساب {account_id} کافی نیست")
                return None
                
            # ایجاد تراکنش
            transaction = self.create_transaction(
                TransactionType.WITHDRAWAL,
                amount,
                account.currency,
                description,
                account_id,
                None,
                user_id,
                reference_id,
                metadata
            )
            
            if not transaction:
                return None
                
            # پردازش تراکنش
            success = self.process_transaction(transaction.transaction_id)
            
            if not success:
                logger.error(f"پردازش تراکنش برداشت {transaction.transaction_id} با خطا مواجه شد")
                return None
                
            # دریافت تراکنش به‌روزشده
            return self.get_transaction(transaction.transaction_id)
            
        except Exception as e:
            logger.error(f"خطا در ایجاد تراکنش برداشت: {e}")
            return None