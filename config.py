import os
from pathlib import Path

# المسار الرئيسي للمشروع
BASE_DIR = Path(__file__).resolve().parent

# بيانات الاتصال بخادم البريد الافتراضية
DEFAULT_CONFIG = {
    "server": "mail.egcloud.gov.eg",
    "email": "luxortechoffice@eha.gov.eg",
    "password": "inGodwetrustjuly2026",
    "auth_type": "NTLM",
    "sync_limit_default": 100,  # عدد الرسائل الافتراضي للسحب
}

# مسارات الملفات والمجلدات
ATTACHMENTS_DIR = BASE_DIR / "attachments"
EXCEL_FILE_PATH = BASE_DIR / "emails_registry.xlsx"
CACHE_FILE_PATH = BASE_DIR / "data_cache.json"

# التأكد من وجود مجلد المرفقات
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
