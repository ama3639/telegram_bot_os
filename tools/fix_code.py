# #!/usr/bin/env python
# # -*- coding: utf-8 -*-

# """
# اسکریپت اصلاح خودکار کد پروژه.

# این اسکریپت با دقت و احتیاط اقدام به اصلاح:
# 1. جایگزینی get_current_datetime() با get_current_datetime()
# 2. اصلاح مسیرهای import
# 3. رفع خطاهای رایج import

# تاریخ ایجاد: ۱۴۰۴/۰۱/۲۰
# """

# import os
# import re
# import ast
# import argparse
# import shutil
# from typing import Tuple, List

# def is_import_needed(content: str, import_statement: str) -> bool:
#     """تشخیص اینکه آیا import مورد نظر واقعاً مورد نیاز است."""
#     try:
#         # حذف کامنت‌ها و استخراج محتوای اصلی کد
#         cleaned_content = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
        
#         # بررسی وجود متغیرها یا توابع در import
#         module_name = import_statement.split()[-1].strip('.')
        
#         # بررسی وجود ارجاع به ماژول
#         return module_name in cleaned_content
#     except Exception:
#         return False

# def fix_datetime_now(content: str) -> Tuple[str, int]:
#     """جایگزینی get_current_datetime() با get_current_datetime()."""
#     # تشخیص وجود استفاده از get_current_datetime()
#     datetime_now_uses = re.findall(r'datetime\.now\(\)', content)
    
#     if not datetime_now_uses:
#         return content, 0
    
#     # اضافه کردن import get_current_datetime در صورت نیاز
#     if 'from utils.timezone_utils import get_current_datetime' not in content:
#         # یافتن محل مناسب برای اضافه کردن import
#         import_block_match = re.search(r'^(import.*\n|from.*\n)*', content)
#         if import_block_match:
#             content = (
#                 content[:import_block_match.end()] + 
#                 'from utils.timezone_utils import get_current_datetime\n' + 
#                 content[import_block_match.end():]
#             )
    
#     # جایگزینی get_current_datetime() با get_current_datetime()
#     content_new, replacements = re.subn(
#         r'datetime\.now\(\)', 
#         'get_current_datetime()', 
#         content
#     )
    
#     return content_new, replacements

# def fix_imports(content: str) -> Tuple[str, int]:
#     """اصلاح مسیرهای import با دقت بالا."""
#     replacements = 0
#     lines = content.split('\n')
#     new_lines = []
    
#     for line in lines:
#         # الگوهای مختلف import
#         import_patterns = [
#             (r'^from\s+src\.([\w.]+)', r'from \1'),
#             (r'^from\s+(\w+)\.src\.([\w.]+)', r'from \1.\2'),
#             (r'^from\s+src\s+import\s+([\w.]+)', r'from \1'),
#         ]
        
#         matched = False
#         for pattern, replacement in import_patterns:
#             match = re.match(pattern, line)
#             if match:
#                 new_line = re.sub(pattern, replacement, line)
#                 new_lines.append(new_line)
#                 if new_line != line:
#                     replacements += 1
#                 matched = True
#                 break
        
#         if not matched:
#             new_lines.append(line)
    
#     return '\n'.join(new_lines), replacements

# def process_file(file_path: str, backup_dir: str = None, dry_run: bool = False, verbose: bool = False) -> Tuple[int, int]:
#     """پردازش و اصلاح یک فایل Python."""
#     try:
#         with open(file_path, 'r', encoding='utf-8') as f:
#             content = f.read()
        
#         # اصلاح اولیه خطاهای رایج
#         content_new = content
#         datetime_fixes = 0
#         import_fixes = 0
        
#         # اصلاح get_current_datetime()
#         content_new, datetime_fixes = fix_datetime_now(content_new)
        
#         # اصلاح import ها
#         content_new, import_fixes = fix_imports(content_new)
        
#         # اگر تغییری ایجاد شده و در حالت dry-run نیستیم
#         total_fixes = datetime_fixes + import_fixes
#         if total_fixes > 0 and not dry_run:
#             # ایجاد نسخه پشتیبان
#             if backup_dir:
#                 os.makedirs(backup_dir, exist_ok=True)
#                 backup_path = os.path.join(
#                     backup_dir, 
#                     f"{os.path.basename(file_path)}.{get_current_datetime().strftime('%Y%m%d%H%M%S')}.bak"
#                 )
#                 shutil.copy2(file_path, backup_path)
            
#             # ذخیره فایل اصلاح شده
#             with open(file_path, 'w', encoding='utf-8') as f:
#                 f.write(content_new)
            
#             # نمایش جزئیات در صورت verbose
#             if verbose:
#                 print(f"{file_path}:")
#                 if datetime_fixes > 0:
#                     print(f"  - {datetime_fixes} مورد get_current_datetime() اصلاح شد")
#                 if import_fixes > 0:
#                     print(f"  - {import_fixes} مورد مسیر import اصلاح شد")
        
#         return datetime_fixes, import_fixes
    
#     except Exception as e:
#         print(f"خطا در پردازش فایل {file_path}: {str(e)}")
#         return 0, 0

# def main():
#     """تابع اصلی برنامه."""
#     parser = argparse.ArgumentParser(description='اصلاح خودکار کد پروژه')
#     parser.add_argument('--dir', type=str, default='.', help='مسیر دایرکتوری ریشه پروژه')
#     parser.add_argument('--backup', action='store_true', help='ایجاد نسخه پشتیبان از فایل‌ها')
#     parser.add_argument('--backup-dir', type=str, default='backups', help='مسیر دایرکتوری نسخه‌های پشتیبان')
#     parser.add_argument('--dry-run', action='store_true', help='اجرای آزمایشی بدون تغییر فایل‌ها')
#     parser.add_argument('--verbose', action='store_true', help='نمایش جزئیات بیشتر')
#     args = parser.parse_args()
    
#     root_dir = args.dir
#     backup_dir = args.backup_dir if args.backup else None
    
#     # آمار
#     total_files = 0
#     fixed_datetime_files = 0
#     fixed_import_files = 0
#     total_datetime_fixes = 0
#     total_import_fixes = 0
    
#     # پیمایش همه فایل‌های Python در پروژه
#     for root, _, files in os.walk(root_dir):
#         for file in files:
#             if file.endswith('.py'):
#                 file_path = os.path.join(root, file)
#                 total_files += 1
                
#                 datetime_fixes, import_fixes = process_file(
#                     file_path, backup_dir, args.dry_run, args.verbose
#                 )
                
#                 if datetime_fixes > 0:
#                     fixed_datetime_files += 1
#                     total_datetime_fixes += datetime_fixes
                
#                 if import_fixes > 0:
#                     fixed_import_files += 1
#                     total_import_fixes += import_fixes
    
#     # گزارش نهایی
#     print(f"\nگزارش نهایی:")
#     print(f"تعداد کل فایل‌های بررسی شده: {total_files}")
#     print(f"تعداد فایل‌های اصلاح شده برای get_current_datetime(): {fixed_datetime_files}")
#     print(f"تعداد کل موارد اصلاح شده get_current_datetime(): {total_datetime_fixes}")
#     print(f"تعداد فایل‌های اصلاح شده برای مسیرهای import: {fixed_import_files}")
#     print(f"تعداد کل موارد اصلاح شده مسیرهای import: {total_import_fixes}")
    
#     if args.dry_run:
#         print("\nتوجه: این اجرا در حالت آزمایشی بود و هیچ فایلی تغییر نکرد.")

# if __name__ == "__main__":
#     main()