#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ماژول تولید نمودار

این ماژول شامل توابع متنوعی برای تولید انواع نمودارهای گرافیکی
با استفاده از کتابخانه matplotlib است.
"""

import os
import base64
import io
from typing import Dict, List, Optional, Tuple, Union, Any
from pathlib import Path
import datetime
import logging

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # تنظیم backend برای استفاده بدون نمایشگر
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import matplotlib.ticker as ticker
from mpl_finance import candlestick_ohlc

from src.utils.logger import get_logger

# تنظیم لاگر
logger = get_logger(__name__)

# تنظیمات پیش‌فرض نمودارها
DEFAULT_CHART_DPI = 100
DEFAULT_CHART_WIDTH = 10
DEFAULT_CHART_HEIGHT = 6
DEFAULT_CHART_STYLE = 'seaborn-v0_8-whitegrid'


def generate_line_chart(
    data: Dict[str, List[Union[int, float]]],
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    colors: Optional[List[str]] = None,
    markers: Optional[List[str]] = None,
    x_labels: Optional[List[str]] = None,
    figsize: Tuple[int, int] = (DEFAULT_CHART_WIDTH, DEFAULT_CHART_HEIGHT),
    grid: bool = True,
    legend_loc: str = 'best'
) -> Figure:
    """
    تولید نمودار خطی
    
    :param data: دیکشنری داده‌ها (کلید: نام سری، مقدار: لیست مقادیر)
    :param title: عنوان نمودار
    :param xlabel: برچسب محور X
    :param ylabel: برچسب محور Y
    :param colors: لیست رنگ‌ها برای هر سری داده
    :param markers: لیست نشانگرها برای هر سری داده
    :param x_labels: برچسب‌های محور X
    :param figsize: اندازه نمودار (عرض، ارتفاع)
    :param grid: نمایش خطوط شبکه
    :param legend_loc: موقعیت راهنما
    :return: شیء Figure
    """
    try:
        # تنظیم استایل نمودار
        plt.style.use(DEFAULT_CHART_STYLE)
        
        # ایجاد نمودار
        fig, ax = plt.subplots(figsize=figsize)
        
        # رنگ‌های پیش‌فرض
        if colors is None:
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                     '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        
        # نشانگرهای پیش‌فرض
        if markers is None:
            markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h']
        
        # رسم داده‌ها
        for i, (label, values) in enumerate(data.items()):
            color_index = i % len(colors)
            marker_index = i % len(markers)
            
            if x_labels:
                ax.plot(range(len(values)), values, label=label, 
                       color=colors[color_index], marker=markers[marker_index], 
                       linewidth=2, markersize=5)
                
                # تنظیم برچسب‌های محور X
                ax.set_xticks(range(len(x_labels)))
                ax.set_xticklabels(x_labels, rotation=45)
            else:
                ax.plot(values, label=label, color=colors[color_index], 
                       marker=markers[marker_index], linewidth=2, markersize=5)
        
        # تنظیم عنوان و برچسب‌ها
        ax.set_title(title, fontsize=14)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        
        # تنظیم خطوط شبکه
        ax.grid(grid)
        
        # افزودن راهنما
        ax.legend(loc=legend_loc)
        
        # تنظیم فاصله بین محتوا و حاشیه‌ها
        plt.tight_layout()
        
        return fig
        
    except Exception as e:
        logger.error(f"خطا در تولید نمودار خطی: {str(e)}")
        # ایجاد یک نمودار خطا
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, f"خطا در تولید نمودار: {str(e)}", 
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=12, color='red')
        ax.axis('off')
        return fig


def generate_bar_chart(
    data: Dict[str, List[Union[int, float]]],
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    colors: Optional[List[str]] = None,
    x_labels: Optional[List[str]] = None,
    figsize: Tuple[int, int] = (DEFAULT_CHART_WIDTH, DEFAULT_CHART_HEIGHT),
    grid: bool = True,
    horizontal: bool = False,
    legend_loc: str = 'best'
) -> Figure:
    """
    تولید نمودار میله‌ای
    
    :param data: دیکشنری داده‌ها (کلید: نام سری، مقدار: لیست مقادیر)
    :param title: عنوان نمودار
    :param xlabel: برچسب محور X
    :param ylabel: برچسب محور Y
    :param colors: لیست رنگ‌ها برای هر سری داده
    :param x_labels: برچسب‌های محور X
    :param figsize: اندازه نمودار (عرض، ارتفاع)
    :param grid: نمایش خطوط شبکه
    :param horizontal: نمودار افقی (True) یا عمودی (False)
    :param legend_loc: موقعیت راهنما
    :return: شیء Figure
    """
    try:
        # تنظیم استایل نمودار
        plt.style.use(DEFAULT_CHART_STYLE)
        
        # ایجاد نمودار
        fig, ax = plt.subplots(figsize=figsize)
        
        # رنگ‌های پیش‌فرض
        if colors is None:
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                     '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        
        # تعیین تعداد گروه‌ها و سری‌ها
        n_groups = max(len(values) for values in data.values())
        n_series = len(data)
        
        # محاسبه عرض میله‌ها و فاصله بین گروه‌ها
        bar_width = 0.8 / n_series
        
        # رسم داده‌ها
        for i, (label, values) in enumerate(data.items()):
            color_index = i % len(colors)
            x_positions = np.arange(n_groups) + (i - n_series/2 + 0.5) * bar_width
            
            if horizontal:
                ax.barh(x_positions, values, height=bar_width, label=label, color=colors[color_index])
            else:
                ax.bar(x_positions, values, width=bar_width, label=label, color=colors[color_index])
        
        # تنظیم برچسب‌های محور X
        if x_labels:
            if horizontal:
                ax.set_yticks(np.arange(n_groups))
                ax.set_yticklabels(x_labels)
            else:
                ax.set_xticks(np.arange(n_groups))
                ax.set_xticklabels(x_labels, rotation=45, ha='right')
        
        # تنظیم عنوان و برچسب‌ها
        ax.set_title(title, fontsize=14)
        if horizontal:
            ax.set_xlabel(ylabel, fontsize=12)
            ax.set_ylabel(xlabel, fontsize=12)
        else:
            ax.set_xlabel(xlabel, fontsize=12)
            ax.set_ylabel(ylabel, fontsize=12)
        
        # تنظیم خطوط شبکه
        if grid:
            if horizontal:
                ax.grid(True, axis='x')
            else:
                ax.grid(True, axis='y')
        
        # افزودن راهنما
        if n_series > 1:
            ax.legend(loc=legend_loc)
        
        # تنظیم فاصله بین محتوا و حاشیه‌ها
        plt.tight_layout()
        
        return fig
        
    except Exception as e:
        logger.error(f"خطا در تولید نمودار میله‌ای: {str(e)}")
        # ایجاد یک نمودار خطا
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, f"خطا در تولید نمودار: {str(e)}", 
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=12, color='red')
        ax.axis('off')
        return fig


def generate_pie_chart(
    data: Dict[str, Union[int, float]],
    title: str = "",
    colors: Optional[List[str]] = None,
    explode: Optional[List[float]] = None,
    show_values: bool = True,
    show_labels: bool = True,
    figsize: Tuple[int, int] = (DEFAULT_CHART_WIDTH, DEFAULT_CHART_HEIGHT),
    shadow: bool = False,
    startangle: int = 0
) -> Figure:
    """
    تولید نمودار دایره‌ای
    
    :param data: دیکشنری داده‌ها (کلید: برچسب، مقدار: مقدار عددی)
    :param title: عنوان نمودار
    :param colors: لیست رنگ‌ها برای هر بخش
    :param explode: لیست مقادیر جدا کردن هر بخش از مرکز
    :param show_values: نمایش مقادیر عددی
    :param show_labels: نمایش برچسب‌ها
    :param figsize: اندازه نمودار (عرض، ارتفاع)
    :param shadow: اعمال سایه
    :param startangle: زاویه شروع (درجه)
    :return: شیء Figure
    """
    try:
        # تنظیم استایل نمودار
        plt.style.use(DEFAULT_CHART_STYLE)
        
        # ایجاد نمودار
        fig, ax = plt.subplots(figsize=figsize)
        
        # آماده‌سازی داده‌ها
        labels = list(data.keys())
        values = list(data.values())
        
        # تنظیم رنگ‌ها
        if colors is None:
            colors = [
                '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
                '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
                '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5'
            ]
        
        # تنظیم explode
        if explode is None:
            explode = [0] * len(data)
        
        # فرمت نمایش مقادیر
        autopct = '%1.1f%%' if show_values else None
        
        # رسم نمودار دایره‌ای
        wedges, texts, autotexts = ax.pie(
            values, 
            explode=explode, 
            labels=labels if show_labels else None, 
            colors=colors,
            autopct=autopct,
            shadow=shadow,
            startangle=startangle,
            wedgeprops={'edgecolor': 'w', 'linewidth': 1}
        )
        
        # تنظیم فونت متن‌ها
        if show_values:
            for autotext in autotexts:
                autotext.set_fontsize(10)
                autotext.set_color('white')
        
        if show_labels:
            for text in texts:
                text.set_fontsize(10)
        
        # تنظیم عنوان
        ax.set_title(title, fontsize=14)
        
        # تنظیم نسبت ابعاد مساوی برای دایره کامل
        ax.axis('equal')
        
        # تنظیم فاصله بین محتوا و حاشیه‌ها
        plt.tight_layout()
        
        return fig
        
    except Exception as e:
        logger.error(f"خطا در تولید نمودار دایره‌ای: {str(e)}")
        # ایجاد یک نمودار خطا
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, f"خطا در تولید نمودار: {str(e)}", 
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=12, color='red')
        ax.axis('off')
        return fig


def generate_stacked_bar_chart(
    data: Dict[str, Dict[str, Union[int, float]]],
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    colors: Optional[List[str]] = None,
    figsize: Tuple[int, int] = (DEFAULT_CHART_WIDTH, DEFAULT_CHART_HEIGHT),
    grid: bool = True,
    horizontal: bool = False,
    legend_loc: str = 'best'
) -> Figure:
    """
    تولید نمودار میله‌ای انباشته
    
    :param data: دیکشنری دو سطحی داده‌ها (کلید اول: گروه، کلید دوم: دسته، مقدار: عدد)
    :param title: عنوان نمودار
    :param xlabel: برچسب محور X
    :param ylabel: برچسب محور Y
    :param colors: لیست رنگ‌ها برای هر دسته
    :param figsize: اندازه نمودار (عرض، ارتفاع)
    :param grid: نمایش خطوط شبکه
    :param horizontal: نمودار افقی (True) یا عمودی (False)
    :param legend_loc: موقعیت راهنما
    :return: شیء Figure
    """
    try:
        # تنظیم استایل نمودار
        plt.style.use(DEFAULT_CHART_STYLE)
        
        # ایجاد نمودار
        fig, ax = plt.subplots(figsize=figsize)
        
        # رنگ‌های پیش‌فرض
        if colors is None:
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                     '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        
        # تبدیل داده‌ها به DataFrame برای سهولت در رسم
        df = pd.DataFrame(data)
        
        # رسم نمودار
        if horizontal:
            df.plot(kind='barh', stacked=True, ax=ax, color=colors)
        else:
            df.plot(kind='bar', stacked=True, ax=ax, color=colors)
        
        # تنظیم عنوان و برچسب‌ها
        ax.set_title(title, fontsize=14)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        
        # تنظیم خطوط شبکه
        if grid:
            if horizontal:
                ax.grid(True, axis='x')
            else:
                ax.grid(True, axis='y')
        
        # چرخش برچسب‌های محور X برای خوانایی بهتر
        if not horizontal:
            plt.xticks(rotation=45, ha='right')
        
        # افزودن راهنما
        ax.legend(loc=legend_loc)
        
        # تنظیم فاصله بین محتوا و حاشیه‌ها
        plt.tight_layout()
        
        return fig
        
    except Exception as e:
        logger.error(f"خطا در تولید نمودار میله‌ای انباشته: {str(e)}")
        # ایجاد یک نمودار خطا
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, f"خطا در تولید نمودار: {str(e)}", 
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=12, color='red')
        ax.axis('off')
        return fig


def generate_candlestick_chart(
    data: List[Tuple[float, float, float, float, float]],
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    dates: Optional[List[datetime.datetime]] = None,
    figsize: Tuple[int, int] = (DEFAULT_CHART_WIDTH, DEFAULT_CHART_HEIGHT),
    grid: bool = True,
    volume_data: Optional[List[float]] = None
) -> Figure:
    """
    تولید نمودار شمعی (کندل استیک) برای داده‌های مالی
    
    :param data: لیست تاپل‌های داده‌ها (تاریخ/شاخص، باز، بالا، پایین، بسته)
    :param title: عنوان نمودار
    :param xlabel: برچسب محور X
    :param ylabel: برچسب محور Y
    :param dates: لیست تاریخ‌ها برای محور X
    :param figsize: اندازه نمودار (عرض، ارتفاع)
    :param grid: نمایش خطوط شبکه
    :param volume_data: داده‌های حجم معاملات (اختیاری)
    :return: شیء Figure
    """
    try:
        # تنظیم استایل نمودار
        plt.style.use(DEFAULT_CHART_STYLE)
        
        # ایجاد نمودار
        fig = plt.figure(figsize=figsize)
        
        # تعیین تعداد زیرنمودارها: 1 یا 2 (با/بدون حجم معاملات)
        if volume_data:
            ax1 = plt.subplot2grid((6, 1), (0, 0), rowspan=4, colspan=1)
            ax2 = plt.subplot2grid((6, 1), (4, 0), rowspan=2, colspan=1, sharex=ax1)
            axes = [ax1, ax2]
        else:
            ax1 = plt.subplot2grid((1, 1), (0, 0), rowspan=1, colspan=1)
            axes = [ax1]
        
        # رسم نمودار شمعی
        candlestick_ohlc(ax1, data, width=0.6, colorup='g', colordown='r')
        
        # تنظیم فرمت محور X
        if dates:
            # تبدیل تاریخ‌ها به شاخص عددی
            dates_float = mdates.date2num(dates)
            date_formatter = mdates.DateFormatter('%Y-%m-%d')
            ax1.xaxis.set_major_formatter(date_formatter)
            
            # تنظیم تاریخ‌ها در محور X
            ax1.set_xticks(dates_float[::max(1, len(dates)//10)])  # هر 10 داده یک برچسب
        
        # رسم حجم معاملات (اگر ارائه شده باشد)
        if volume_data and len(volume_data) == len(data):
            ax2.bar([item[0] for item in data], volume_data, width=0.6, alpha=0.7, color='b')
            ax2.set_ylabel('حجم', fontsize=10)
            ax2.grid(grid)
        
        # تنظیم عنوان و برچسب‌ها
        ax1.set_title(title, fontsize=14)
        ax1.set_ylabel(ylabel, fontsize=12)
        
        # تنظیم برچسب محور X فقط در زیرنمودار آخر
        axes[-1].set_xlabel(xlabel, fontsize=12)
        
        # تنظیم خطوط شبکه
        ax1.grid(grid)
        
        # تنظیم چرخش برچسب‌های محور X
        for label in axes[-1].get_xticklabels():
            label.set_rotation(45)
            label.set_horizontalalignment('right')
        
        # تنظیم فاصله بین محتوا و حاشیه‌ها
        plt.tight_layout()
        
        return fig
        
    except Exception as e:
        logger.error(f"خطا در تولید نمودار شمعی: {str(e)}")
        # ایجاد یک نمودار خطا
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, f"خطا در تولید نمودار: {str(e)}", 
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=12, color='red')
        ax.axis('off')
        return fig


def save_chart_to_file(
    fig: Figure,
    filename: str,
    dpi: int = DEFAULT_CHART_DPI,
    directory: Optional[str] = None,
    format: str = 'png'
) -> str:
    """
    ذخیره نمودار در فایل
    
    :param fig: شیء Figure
    :param filename: نام فایل
    :param dpi: وضوح تصویر (نقطه در اینچ)
    :param directory: مسیر دایرکتوری برای ذخیره
    :param format: فرمت فایل خروجی (png, jpg, svg, pdf)
    :return: مسیر کامل فایل ذخیره شده
    """
    try:
        # ایجاد دایرکتوری اگر وجود نداشته باشد
        if directory:
            os.makedirs(directory, exist_ok=True)
            filepath = os.path.join(directory, filename)
        else:
            filepath = filename
        
        # اضافه کردن پسوند فایل اگر نداشته باشد
        if not filepath.lower().endswith(f'.{format.lower()}'):
            filepath = f"{filepath}.{format.lower()}"
        
        # ذخیره نمودار
        fig.savefig(filepath, dpi=dpi, bbox_inches='tight', format=format)
        
        # بستن شیء Figure برای آزادسازی حافظه
        plt.close(fig)
        
        logger.info(f"نمودار با موفقیت در {filepath} ذخیره شد")
        return filepath
        
    except Exception as e:
        logger.error(f"خطا در ذخیره نمودار: {str(e)}")
        return ""


def chart_to_base64(
    fig: Figure,
    format: str = 'png',
    dpi: int = DEFAULT_CHART_DPI
) -> str:
    """
    تبدیل نمودار به رشته base64 برای استفاده در HTML
    
    :param fig: شیء Figure
    :param format: فرمت تصویر (png, jpg, svg)
    :param dpi: وضوح تصویر (نقطه در اینچ)
    :return: رشته base64 تصویر نمودار
    """
    try:
        # ایجاد بافر حافظه برای ذخیره تصویر
        buf = io.BytesIO()
        
        # ذخیره نمودار در بافر
        fig.savefig(buf, format=format, dpi=dpi, bbox_inches='tight')
        
        # بستن شیء Figure برای آزادسازی حافظه
        plt.close(fig)
        
        # تبدیل بافر به رشته base64
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        
        return f"data:image/{format};base64,{img_base64}"
        
    except Exception as e:
        logger.error(f"خطا در تبدیل نمودار به base64: {str(e)}")
        return ""


def get_chart_image_for_telegram(
    fig: Figure,
    dpi: int = DEFAULT_CHART_DPI
) -> Optional[bytes]:
    """
    تهیه تصویر نمودار برای ارسال از طریق تلگرام
    
    :param fig: شیء Figure
    :param dpi: وضوح تصویر (نقطه در اینچ)
    :return: داده‌های باینری تصویر یا None در صورت خطا
    """
    try:
        # ایجاد بافر حافظه برای ذخیره تصویر
        buf = io.BytesIO()
        
        # ذخیره نمودار در بافر
        fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight')
        
        # بستن شیء Figure برای آزادسازی حافظه
        plt.close(fig)
        
        # آماده‌سازی داده‌های باینری
        buf.seek(0)
        return buf.getvalue()
        
    except Exception as e:
        logger.error(f"خطا در تهیه تصویر نمودار برای تلگرام: {str(e)}")
        return None


def generate_multi_axis_chart(
    data_left: Dict[str, List[Union[int, float]]],
    data_right: Dict[str, List[Union[int, float]]],
    title: str = "",
    xlabel: str = "",
    ylabel_left: str = "",
    ylabel_right: str = "",
    colors_left: Optional[List[str]] = None,
    colors_right: Optional[List[str]] = None,
    markers: Optional[List[str]] = None,
    x_labels: Optional[List[str]] = None,
    figsize: Tuple[int, int] = (DEFAULT_CHART_WIDTH, DEFAULT_CHART_HEIGHT),
    grid: bool = True
) -> Figure:
    """
    تولید نمودار با دو محور Y برای نمایش داده‌ها با مقیاس‌های متفاوت
    
    :param data_left: دیکشنری داده‌ها برای محور چپ
    :param data_right: دیکشنری داده‌ها برای محور راست
    :param title: عنوان نمودار
    :param xlabel: برچسب محور X
    :param ylabel_left: برچسب محور Y چپ
    :param ylabel_right: برچسب محور Y راست
    :param colors_left: لیست رنگ‌ها برای داده‌های محور چپ
    :param colors_right: لیست رنگ‌ها برای داده‌های محور راست
    :param markers: لیست نشانگرها
    :param x_labels: برچسب‌های محور X
    :param figsize: اندازه نمودار (عرض، ارتفاع)
    :param grid: نمایش خطوط شبکه
    :return: شیء Figure
    """
    try:
        # تنظیم استایل نمودار
        plt.style.use(DEFAULT_CHART_STYLE)
        
        # ایجاد نمودار با دو محور Y
        fig, ax1 = plt.subplots(figsize=figsize)
        ax2 = ax1.twinx()
        
        # رنگ‌های پیش‌فرض
        if colors_left is None:
            colors_left = ['#1f77b4', '#2ca02c', '#9467bd', '#8c564b', '#e377c2']
        
        if colors_right is None:
            colors_right = ['#ff7f0e', '#d62728', '#7f7f7f', '#bcbd22', '#17becf']
        
        # نشانگرهای پیش‌فرض
        if markers is None:
            markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h']
        
        # رسم داده‌ها برای محور چپ
        for i, (label, values) in enumerate(data_left.items()):
            color_index = i % len(colors_left)
            marker_index = i % len(markers)
            
            if x_labels:
                ax1.plot(range(len(values)), values, label=f"{label} (چپ)", 
                        color=colors_left[color_index], marker=markers[marker_index], 
                        linewidth=2, markersize=5)
                
                # تنظیم برچسب‌های محور X
                ax1.set_xticks(range(len(x_labels)))
                ax1.set_xticklabels(x_labels, rotation=45)
            else:
                ax1.plot(values, label=f"{label} (چپ)", color=colors_left[color_index], 
                        marker=markers[marker_index], linewidth=2, markersize=5)
        
        # رسم داده‌ها برای محور راست
        for i, (label, values) in enumerate(data_right.items()):
            color_index = i % len(colors_right)
            marker_index = (i + len(data_left)) % len(markers)
            
            if x_labels:
                ax2.plot(range(len(values)), values, label=f"{label} (راست)", 
                        color=colors_right[color_index], marker=markers[marker_index], 
                        linewidth=2, markersize=5, linestyle='--')
            else:
                ax2.plot(values, label=f"{label} (راست)", color=colors_right[color_index], 
                        marker=markers[marker_index], linewidth=2, markersize=5, linestyle='--')
        
        # تنظیم عنوان و برچسب‌ها
        ax1.set_title(title, fontsize=14)
        ax1.set_xlabel(xlabel, fontsize=12)
        ax1.set_ylabel(ylabel_left, fontsize=12, color=colors_left[0])
        ax2.set_ylabel(ylabel_right, fontsize=12, color=colors_right[0])
        
        # تنظیم رنگ تیک‌های محور Y
        ax1.tick_params(axis='y', labelcolor=colors_left[0])
        ax2.tick_params(axis='y', labelcolor=colors_right[0])
        
        # تنظیم خطوط شبکه
        ax1.grid(grid)
        
        # ترکیب راهنماهای هر دو محور
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')
        
        # تنظیم فاصله بین محتوا و حاشیه‌ها
        plt.tight_layout()
        
        return fig
        
    except Exception as e:
        logger.error(f"خطا در تولید نمودار با دو محور: {str(e)}")
        # ایجاد یک نمودار خطا
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, f"خطا در تولید نمودار: {str(e)}", 
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=12, color='red')
        ax.axis('off')
        return fig 