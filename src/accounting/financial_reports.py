#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول گزارش‌های مالی

این ماژول برای تولید انواع گزارش‌های مالی از داده‌های ذخیره شده در سیستم
استفاده می‌شود.
"""

import os
import enum
import json
import csv
import datetime
from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

from core.database import Database
from core.config import Config
from utils.logger import get_logger
from utils.timezone_utils import get_current_datetime
from .ledger import Ledger, TransactionType

# تنظیم لاگر
logger = get_logger(__name__)


class ReportType(enum.Enum):
    """
    انواع گزارش‌های مالی قابل تولید
    """
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class FinancialReport:
    """
    کلاس تولید گزارش‌های مالی
    """
    def __init__(
        self, 
        config: Config, 
        db: Database,
        ledger: Optional[Ledger] = None
    ):
        """
        مقداردهی اولیه کلاس گزارش مالی
        
        :param config: تنظیمات پیکربندی
        :param db: شیء پایگاه داده
        :param ledger: شیء دفتر کل (اختیاری)
        """
        self.config = config
        self.db = db
        self.ledger = ledger or Ledger(db)
        
        # مسیر ذخیره‌سازی گزارش‌ها
        self.reports_dir = Path(config.get("REPORTS_DIR", "data/reports"))
        self._ensure_report_dirs()
        
        logger.info("سیستم گزارش‌های مالی راه‌اندازی شد")
    
    def _ensure_report_dirs(self) -> None:
        """
        اطمینان از وجود دایرکتوری‌های لازم برای ذخیره گزارش‌ها
        """
        dirs = [
            self.reports_dir,
            self.reports_dir / "csv",
            self.reports_dir / "json",
            self.reports_dir / "charts"
        ]
        
        for dir_path in dirs:
            os.makedirs(dir_path, exist_ok=True)
    
    def _get_date_range(
        self, 
        report_type: ReportType,
        custom_start_date: Optional[datetime.datetime] = None,
        custom_end_date: Optional[datetime.datetime] = None
    ) -> Tuple[datetime.datetime, datetime.datetime]:
        """
        محاسبه محدوده تاریخ برای گزارش بر اساس نوع آن
        
        :param report_type: نوع گزارش
        :param custom_start_date: تاریخ شروع دلخواه (برای گزارش CUSTOM)
        :param custom_end_date: تاریخ پایان دلخواه (برای گزارش CUSTOM)
        :return: تاپل شامل تاریخ شروع و پایان
        """
        end_date = get_current_datetime()
        start_date = end_date
        
        if report_type == ReportType.DAILY:
            # گزارش روزانه - از ابتدای روز تا کنون
            start_date = datetime.datetime(
                end_date.year, end_date.month, end_date.day, 0, 0, 0,
                tzinfo=end_date.tzinfo
            )
            
        elif report_type == ReportType.WEEKLY:
            # گزارش هفتگی - از 7 روز قبل تا کنون
            start_date = end_date - datetime.timedelta(days=7)
            
        elif report_type == ReportType.MONTHLY:
            # گزارش ماهانه - از ابتدای ماه تا کنون
            start_date = datetime.datetime(
                end_date.year, end_date.month, 1, 0, 0, 0,
                tzinfo=end_date.tzinfo
            )
            
        elif report_type == ReportType.QUARTERLY:
            # گزارش سه‌ماهه - از ابتدای فصل تا کنون
            quarter_month = ((end_date.month - 1) // 3) * 3 + 1
            start_date = datetime.datetime(
                end_date.year, quarter_month, 1, 0, 0, 0,
                tzinfo=end_date.tzinfo
            )
            
        elif report_type == ReportType.YEARLY:
            # گزارش سالانه - از ابتدای سال تا کنون
            start_date = datetime.datetime(
                end_date.year, 1, 1, 0, 0, 0,
                tzinfo=end_date.tzinfo
            )
            
        elif report_type == ReportType.CUSTOM:
            # گزارش دلخواه - استفاده از تاریخ‌های ورودی
            if custom_start_date and custom_end_date:
                start_date = custom_start_date
                end_date = custom_end_date
                
        return start_date, end_date
    
    def _get_transactions_data(
        self, 
        start_date: datetime.datetime,
        end_date: datetime.datetime
    ) -> List[Dict[str, Any]]:
        """
        دریافت داده‌های تراکنش‌ها برای بازه زمانی مشخص
        
        :param start_date: تاریخ شروع
        :param end_date: تاریخ پایان
        :return: لیست دیکشنری‌های حاوی اطلاعات تراکنش‌ها
        """
        query = """
        SELECT * FROM transactions 
        WHERE timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp ASC
        """
        
        results = self.db.fetchall(
            query, 
            (start_date.isoformat(), end_date.isoformat())
        )
        
        transactions = []
        for result in results:
            result_dict = dict(result)
            
            # تبدیل متادیتا از رشته JSON به دیکشنری
            result_dict['metadata'] = json.loads(result_dict['metadata']) if result_dict['metadata'] else {}
            
            transactions.append(result_dict)
            
        return transactions
    
    def generate_transaction_report(
        self,
        report_type: ReportType = ReportType.MONTHLY,
        output_format: str = "json",
        include_chart: bool = False,
        custom_start_date: Optional[datetime.datetime] = None,
        custom_end_date: Optional[datetime.datetime] = None
    ) -> Dict[str, Any]:
        """
        تولید گزارش تراکنش‌ها
        
        :param report_type: نوع گزارش (روزانه، هفتگی، ماهانه و غیره)
        :param output_format: فرمت خروجی (json یا csv)
        :param include_chart: آیا نمودار هم تولید شود
        :param custom_start_date: تاریخ شروع دلخواه (برای گزارش CUSTOM)
        :param custom_end_date: تاریخ پایان دلخواه (برای گزارش CUSTOM)
        :return: دیکشنری حاوی اطلاعات گزارش و مسیرهای فایل‌های تولید شده
        """
        start_date, end_date = self._get_date_range(
            report_type, custom_start_date, custom_end_date
        )
        
        # دریافت تراکنش‌ها
        transactions = self._get_transactions_data(start_date, end_date)
        
        if not transactions:
            logger.warning(f"هیچ تراکنشی برای گزارش {report_type.value} یافت نشد")
            return {
                "status": "warning",
                "message": f"هیچ تراکنشی برای گزارش {report_type.value} یافت نشد",
                "report_type": report_type.value,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "transaction_count": 0,
                "files": {}
            }
            
        logger.info(f"تولید گزارش {report_type.value} با {len(transactions)} تراکنش")
        
        # محاسبه خلاصه تراکنش‌ها
        summary = self._calculate_transaction_summary(transactions)
        
        # زمان تولید گزارش
        report_time = get_current_datetime()
        timestamp_str = report_time.strftime("%Y%m%d_%H%M%S")
        
        # نام فایل گزارش
        report_name = f"transaction_report_{report_type.value}_{timestamp_str}"
        
        # ذخیره خروجی گزارش
        files = {}
        
        # ذخیره به فرمت JSON
        if output_format in ["json", "all"]:
            json_data = {
                "report_type": report_type.value,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "generated_at": report_time.isoformat(),
                "summary": summary,
                "transactions": transactions
            }
            
            json_path = self.reports_dir / "json" / f"{report_name}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
                
            files["json"] = str(json_path)
            logger.info(f"گزارش JSON در {json_path} ذخیره شد")
            
        # ذخیره به فرمت CSV
        if output_format in ["csv", "all"]:
            csv_path = self.reports_dir / "csv" / f"{report_name}.csv"
            
            # آماده‌سازی داده‌ها برای CSV
            csv_data = []
            for transaction in transactions:
                # حذف متادیتا از خروجی CSV
                transaction_copy = transaction.copy()
                transaction_copy.pop('metadata', None)
                csv_data.append(transaction_copy)
                
            # نوشتن فایل CSV
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                if csv_data:
                    writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
                    writer.writeheader()
                    writer.writerows(csv_data)
                    
            files["csv"] = str(csv_path)
            logger.info(f"گزارش CSV در {csv_path} ذخیره شد")
            
        # تولید نمودار
        if include_chart:
            chart_path = self._generate_transaction_chart(
                transactions, 
                report_type, 
                start_date, 
                end_date, 
                report_name
            )
            
            if chart_path:
                files["chart"] = str(chart_path)
                logger.info(f"نمودار گزارش در {chart_path} ذخیره شد")
        
        # خروجی نهایی
        result = {
            "status": "success",
            "message": f"گزارش {report_type.value} با موفقیت تولید شد",
            "report_type": report_type.value,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "transaction_count": len(transactions),
            "summary": summary,
            "files": files
        }
        
        return result
    
    def _calculate_transaction_summary(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        محاسبه خلاصه و آمار از تراکنش‌ها
        
        :param transactions: لیست تراکنش‌ها
        :return: دیکشنری حاوی خلاصه آماری
        """
        if not transactions:
            return {
                "total_transactions": 0,
                "total_amount": 0,
                "average_amount": 0,
                "currency_breakdown": {},
                "type_breakdown": {},
                "status_breakdown": {},
                "user_breakdown": {}
            }
            
        # تبدیل به DataFrame برای تحلیل آسان‌تر
        df = pd.DataFrame(transactions)
        
        # محاسبه تعداد کل تراکنش‌ها
        total_transactions = len(df)
        
        # محاسبه مجموع و میانگین مبالغ
        # فقط تراکنش‌های با وضعیت "completed" را در نظر می‌گیریم
        completed_df = df[df['status'] == 'completed']
        
        # بررسی برای داشتن حداقل یک تراکنش completed
        if len(completed_df) > 0:
            # گروه‌بندی بر اساس ارز برای جمع مبالغ
            currency_groups = completed_df.groupby('currency')
            total_by_currency = currency_groups['amount'].sum().to_dict()
            avg_by_currency = currency_groups['amount'].mean().to_dict()
            
            # کل مبلغ (فقط برای نمایش، جمع مبالغ با ارزهای مختلف معنای اقتصادی ندارد)
            total_amount = completed_df['amount'].sum()
            avg_amount = completed_df['amount'].mean()
        else:
            total_by_currency = {}
            avg_by_currency = {}
            total_amount = 0
            avg_amount = 0
        
        # شکست بر اساس نوع تراکنش
        type_counts = df['transaction_type'].value_counts().to_dict()
        
        # شکست بر اساس وضعیت تراکنش
        status_counts = df['status'].value_counts().to_dict()
        
        # شکست بر اساس کاربر
        user_counts = df['user_id'].value_counts().to_dict()
        # تبدیل کلیدها (user_id) از عدد به رشته برای خروجی JSON
        user_counts = {str(k): v for k, v in user_counts.items()}
        
        return {
            "total_transactions": total_transactions,
            "completed_transactions": len(completed_df),
            "total_amount_all": total_amount,  # این عدد معنای اقتصادی ندارد
            "average_amount_all": float(avg_amount),  # این عدد معنای اقتصادی ندارد
            "currency_breakdown": {
                "totals": total_by_currency,
                "averages": {k: float(v) for k, v in avg_by_currency.items()}
            },
            "type_breakdown": type_counts,
            "status_breakdown": status_counts,
            "user_breakdown": user_counts
        }
    
    def _generate_transaction_chart(
        self,
        transactions: List[Dict[str, Any]],
        report_type: ReportType,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        report_name: str
    ) -> Optional[Path]:
        """
        تولید نمودار گرافیکی برای تراکنش‌ها
        
        :param transactions: لیست تراکنش‌ها
        :param report_type: نوع گزارش
        :param start_date: تاریخ شروع
        :param end_date: تاریخ پایان
        :param report_name: نام گزارش
        :return: مسیر فایل نمودار یا None در صورت خطا
        """
        try:
            if not transactions:
                logger.warning("داده‌ای برای تولید نمودار وجود ندارد")
                return None
                
            # تبدیل به DataFrame
            df = pd.DataFrame(transactions)
            
            # تبدیل ستون timestamp به datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # فیلتر تراکنش‌های با وضعیت "completed"
            completed_df = df[df['status'] == 'completed']
            
            if len(completed_df) == 0:
                logger.warning("هیچ تراکنش تکمیل شده‌ای برای نمودار وجود ندارد")
                return None
                
            # تنظیم اندازه و سبک نمودار
            plt.style.use('seaborn-v0_8-whitegrid')
            fig, axs = plt.subplots(2, 1, figsize=(12, 10))
            
            # ---- نمودار 1: روند تراکنش‌ها بر اساس زمان ----
            
            # تنظیم میزان گروه‌بندی زمانی بر اساس نوع گزارش
            if report_type == ReportType.DAILY:
                time_grouper = pd.Grouper(key='timestamp', freq='H')  # ساعتی
                time_format = "%H:%M"
            elif report_type == ReportType.WEEKLY:
                time_grouper = pd.Grouper(key='timestamp', freq='D')  # روزانه
                time_format = "%m-%d"
            elif report_type == ReportType.MONTHLY:
                time_grouper = pd.Grouper(key='timestamp', freq='D')  # روزانه
                time_format = "%m-%d"
            elif report_type == ReportType.QUARTERLY:
                time_grouper = pd.Grouper(key='timestamp', freq='W')  # هفتگی
                time_format = "%m-%d"
            elif report_type == ReportType.YEARLY:
                time_grouper = pd.Grouper(key='timestamp', freq='M')  # ماهانه
                time_format = "%Y-%m"
            else:
                # انتخاب بر اساس فاصله زمانی
                days_diff = (end_date - start_date).days
                if days_diff <= 2:
                    time_grouper = pd.Grouper(key='timestamp', freq='H')
                    time_format = "%m-%d %H:%M"
                elif days_diff <= 31:
                    time_grouper = pd.Grouper(key='timestamp', freq='D')
                    time_format = "%m-%d"
                elif days_diff <= 90:
                    time_grouper = pd.Grouper(key='timestamp', freq='W')
                    time_format = "%m-%d"
                else:
                    time_grouper = pd.Grouper(key='timestamp', freq='M')
                    time_format = "%Y-%m"
            
            # گروه‌بندی و شمارش تراکنش‌ها
            time_counts = completed_df.groupby([time_grouper, 'transaction_type']).size().unstack(fill_value=0)
            
            # رسم نمودار
            time_counts.plot(kind='line', ax=axs[0], marker='o')
            
            # تنظیمات نمودار
            axs[0].set_title('روند تراکنش‌ها بر اساس زمان و نوع', fontsize=14)
            axs[0].set_xlabel('تاریخ/زمان', fontsize=12)
            axs[0].set_ylabel('تعداد تراکنش', fontsize=12)
            axs[0].grid(True)
            
            # فرمت محور X
            if hasattr(time_counts.index, 'strftime'):
                axs[0].xaxis.set_major_formatter(mdates.DateFormatter(time_format))
            
            axs[0].legend(title='نوع تراکنش')
            
            # ---- نمودار 2: شکست بر اساس نوع تراکنش (نمودار دایره‌ای) ----
            
            # گروه‌بندی بر اساس نوع تراکنش
            type_counts = completed_df['transaction_type'].value_counts()
            
            # رسم نمودار دایره‌ای
            axs[1].pie(
                type_counts, 
                labels=type_counts.index,
                autopct='%1.1f%%', 
                startangle=90,
                shadow=True
            )
            
            axs[1].set_title('توزیع تراکنش‌ها بر اساس نوع', fontsize=14)
            axs[1].axis('equal')  # نسبت ابعاد مساوی برای دایره کامل
            
            # تنظیم فاصله بین نمودارها
            plt.tight_layout()
            
            # ذخیره نمودار
            chart_path = self.reports_dir / "charts" / f"{report_name}.png"
            plt.savefig(chart_path, dpi=100, bbox_inches='tight')
            plt.close(fig)
            
            return chart_path
            
        except Exception as e:
            logger.error(f"خطا در تولید نمودار: {str(e)}")
            return None
    
    def generate_revenue_report(
        self,
        report_type: ReportType = ReportType.MONTHLY,
        include_chart: bool = True,
        custom_start_date: Optional[datetime.datetime] = None,
        custom_end_date: Optional[datetime.datetime] = None
    ) -> Dict[str, Any]:
        """
        تولید گزارش درآمد
        
        :param report_type: نوع گزارش (روزانه، هفتگی، ماهانه و غیره)
        :param include_chart: آیا نمودار هم تولید شود
        :param custom_start_date: تاریخ شروع دلخواه (برای گزارش CUSTOM)
        :param custom_end_date: تاریخ پایان دلخواه (برای گزارش CUSTOM)
        :return: دیکشنری حاوی اطلاعات گزارش و مسیرهای فایل‌های تولید شده
        """
        start_date, end_date = self._get_date_range(
            report_type, custom_start_date, custom_end_date
        )
        
        # دریافت تراکنش‌های درآمدی در بازه زمانی
        query = """
        SELECT * FROM transactions 
        WHERE timestamp >= ? AND timestamp <= ?
        AND transaction_type IN ('subscription_payment', 'service_fee')
        AND status = 'completed'
        ORDER BY timestamp ASC
        """
        
        results = self.db.fetchall(
            query, 
            (start_date.isoformat(), end_date.isoformat())
        )
        
        transactions = []
        for result in results:
            result_dict = dict(result)
            # تبدیل متادیتا از رشته JSON به دیکشنری
            result_dict['metadata'] = json.loads(result_dict['metadata']) if result_dict['metadata'] else {}
            transactions.append(result_dict)
            
        if not transactions:
            logger.warning(f"هیچ تراکنش درآمدی برای گزارش {report_type.value} یافت نشد")
            return {
                "status": "warning",
                "message": f"هیچ تراکنش درآمدی برای گزارش {report_type.value} یافت نشد",
                "report_type": report_type.value,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "transaction_count": 0,
                "files": {}
            }
            
        logger.info(f"تولید گزارش درآمد {report_type.value} با {len(transactions)} تراکنش")
        
        # تبدیل به DataFrame
        df = pd.DataFrame(transactions)
        
        # گروه‌بندی بر اساس ارز و نوع تراکنش
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        revenue_by_currency = df.groupby(['currency', 'transaction_type'])['amount'].agg(['sum', 'count'])
        
        # محاسبه کل درآمد به تفکیک ارز
        total_by_currency = df.groupby('currency')['amount'].sum().to_dict()
        
        # محاسبه کل درآمد به تفکیک نوع تراکنش
        total_by_type = df.groupby('transaction_type')['amount'].sum().to_dict()
        
        # زمان تولید گزارش
        report_time = get_current_datetime()
        timestamp_str = report_time.strftime("%Y%m%d_%H%M%S")
        
        # نام فایل گزارش
        report_name = f"revenue_report_{report_type.value}_{timestamp_str}"
        
        # خلاصه گزارش
        summary = {
            "transaction_count": len(transactions),
            "total_by_currency": total_by_currency,
            "total_by_type": total_by_type,
            "detailed_breakdown": revenue_by_currency.reset_index().to_dict(orient='records')
        }
        
        # ذخیره به فرمت JSON
        json_data = {
            "report_type": report_type.value,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "generated_at": report_time.isoformat(),
            "summary": summary,
            "transactions": transactions
        }
        
        json_path = self.reports_dir / "json" / f"{report_name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
            
        files = {"json": str(json_path)}
        logger.info(f"گزارش درآمد JSON در {json_path} ذخیره شد")
        
        # تولید نمودار
        if include_chart:
            chart_path = self._generate_revenue_chart(
                df, 
                report_type, 
                start_date, 
                end_date, 
                report_name
            )
            
            if chart_path:
                files["chart"] = str(chart_path)
                logger.info(f"نمودار گزارش درآمد در {chart_path} ذخیره شد")
        
        # خروجی نهایی
        result = {
            "status": "success",
            "message": f"گزارش درآمد {report_type.value} با موفقیت تولید شد",
            "report_type": report_type.value,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "transaction_count": len(transactions),
            "summary": summary,
            "files": files
        }
        
        return result
    
    def _generate_revenue_chart(
        self,
        df: pd.DataFrame,
        report_type: ReportType,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        report_name: str
    ) -> Optional[Path]:
        """
        تولید نمودار گرافیکی برای گزارش درآمد
        
        :param df: DataFrame حاوی تراکنش‌های درآمدی
        :param report_type: نوع گزارش
        :param start_date: تاریخ شروع
        :param end_date: تاریخ پایان
        :param report_name: نام گزارش
        :return: مسیر فایل نمودار یا None در صورت خطا
        """
        try:
            if len(df) == 0:
                logger.warning("داده‌ای برای تولید نمودار درآمد وجود ندارد")
                return None
                
            # تنظیم اندازه و سبک نمودار
            plt.style.use('seaborn-v0_8-whitegrid')
            fig, axs = plt.subplots(2, 1, figsize=(12, 10))
            
            # تنظیم میزان گروه‌بندی زمانی بر اساس نوع گزارش
            if report_type == ReportType.DAILY:
                time_grouper = pd.Grouper(key='timestamp', freq='H')  # ساعتی
                time_format = "%H:%M"
            elif report_type == ReportType.WEEKLY:
                time_grouper = pd.Grouper(key='timestamp', freq='D')  # روزانه
                time_format = "%m-%d"
            elif report_type == ReportType.MONTHLY:
                time_grouper = pd.Grouper(key='timestamp', freq='D')  # روزانه
                time_format = "%m-%d"
            elif report_type == ReportType.QUARTERLY:
                time_grouper = pd.Grouper(key='timestamp', freq='W')  # هفتگی
                time_format = "%m-%d"
            elif report_type == ReportType.YEARLY:
                time_grouper = pd.Grouper(key='timestamp', freq='M')  # ماهانه
                time_format = "%Y-%m"
            else:
                # انتخاب بر اساس فاصله زمانی
                days_diff = (end_date - start_date).days
                if days_diff <= 2:
                    time_grouper = pd.Grouper(key='timestamp', freq='H')
                    time_format = "%m-%d %H:%M"
                elif days_diff <= 31:
                    time_grouper = pd.Grouper(key='timestamp', freq='D')
                    time_format = "%m-%d"
                elif days_diff <= 90:
                    time_grouper = pd.Grouper(key='timestamp', freq='W')
                    time_format = "%m-%d"
                else:
                    time_grouper = pd.Grouper(key='timestamp', freq='M')
                    time_format = "%Y-%m"
            
            # ----- نمودار 1: روند درآمد بر اساس زمان -----
            
            # باید برای هر ارز جداگانه گروه‌بندی کنیم
            currencies = df['currency'].unique()
            
            # ایجاد یک DataFrame جدید برای هر ارز
            for currency in currencies:
                currency_df = df[df['currency'] == currency]
                # گروه‌بندی بر اساس زمان و محاسبه مجموع
                currency_time_sum = currency_df.groupby([time_grouper])['amount'].sum()
                
                # رسم نمودار خطی
                currency_time_sum.plot(
                    kind='line', 
                    ax=axs[0], 
                    marker='o', 
                    label=currency
                )
            
            # تنظیمات نمودار
            axs[0].set_title('روند درآمد بر اساس زمان', fontsize=14)
            axs[0].set_xlabel('تاریخ/زمان', fontsize=12)
            axs[0].set_ylabel('مقدار درآمد', fontsize=12)
            axs[0].grid(True)
            
            # فرمت محور X
            axs[0].xaxis.set_major_formatter(mdates.DateFormatter(time_format))
            
            axs[0].legend(title='ارز')
            
            # ----- نمودار 2: توزیع درآمد بر اساس نوع تراکنش -----
            
            # گروه‌بندی بر اساس نوع تراکنش و ارز
            type_currency_sum = df.groupby(['transaction_type', 'currency'])['amount'].sum().unstack(fill_value=0)
            
            # رسم نمودار میله‌ای
            type_currency_sum.plot(
                kind='bar', 
                ax=axs[1],
                width=0.7
            )
            
            axs[1].set_title('درآمد بر اساس نوع تراکنش و ارز', fontsize=14)
            axs[1].set_xlabel('نوع تراکنش', fontsize=12)
            axs[1].set_ylabel('مقدار درآمد', fontsize=12)
            axs[1].grid(True, axis='y')
            axs[1].legend(title='ارز')
            
            # تنظیم فاصله بین نمودارها
            plt.tight_layout()
            
            #  ذخ یره نمودار
            chart_path = self.reports_dir / "charts" / f"{report_name}.png"
            plt.savefig(chart_path, dpi=100, bbox_inches='tight')
            plt.close(fig)
            
            return chart_path
            
        except Exception as e:
            logger.error(f"خطا در تولید نمودار درآمد: {str(e)}")
            return None