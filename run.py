import os
import sys
import time
import webbrowser
import threading
from pathlib import Path

# إعداد الترميز الافتراضي للكونسول
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app import app
from config import BASE_DIR, EXCEL_FILE_PATH, CACHE_FILE_PATH

def open_browser(port):
    """فتح المتصفح تلقائياً عند بدء التشغيل"""
    time.sleep(1.5)
    url = f"http://127.0.0.1:{port}"
    print(f"\n=======================================================")
    print(f"🌟 تم تشغيل نظام متابعة وحصر البريد بنجاح!")
    print(f"🔗 افتح الرابط في المتصفح: {url}")
    print(f"📊 ملف الإكسيل الرئيسي: {EXCEL_FILE_PATH.name}")
    print(f"=======================================================\n")
    webbrowser.open(url)

if __name__ == '__main__':
    port = 5050
    # تشغيل المتصفح في خيط منفصل
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    
    # تشغيل الخادم
    app.run(host='0.0.0.0', port=port, debug=False)
