import os
import sys
import json
import threading
import subprocess
from pathlib import Path

# ضبط ترميز الإخراج على ويندوز
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_cors import CORS

from config import EXCEL_FILE_PATH, ATTACHMENTS_DIR, CACHE_FILE_PATH, DEFAULT_CONFIG
from excel_manager import load_cache_data
from mail_service import fetch_and_process_emails, SYNC_PROGRESS
from analyzer import compare_emails

app = Flask(__name__)
CORS(app)

# قفل لمنع تشغيل عمليتي مزامنة في نفس اللحظة
sync_lock = threading.Lock()

@app.route('/')
def index():
    """الصفحة الرئيسية للوحة التحكم"""
    return render_template('index.html')

@app.route('/report')
def view_report():
    """صفحة تقرير الحصر الشامل مع التصفية بالتواريخ والتجميع الزمني"""
    data = load_cache_data()
    inbox = data.get("inbox", [])
    sent = data.get("sent", [])
    
    start_date = request.args.get('start', '').strip()
    end_date = request.args.get('end', '').strip()
    rep_type = request.args.get('type', 'all_unreplied').strip()
    
    inbox_unreplied = [e for e in inbox if e.get("status_code") == "inbox_unreplied"]
    sent_unreplied = [e for e in sent if e.get("status_code") == "sent_unreplied"]
    inbox_replied = [e for e in inbox if e.get("status_code") == "inbox_replied"]
    sent_replied = [e for e in sent if e.get("status_code") == "sent_replied"]
    
    # تطبيق فلترة التواريخ
    if start_date:
        inbox_unreplied = [e for e in inbox_unreplied if (e.get("datetime_received") or "")[:10] >= start_date]
        sent_unreplied = [e for e in sent_unreplied if (e.get("datetime_sent") or "")[:10] >= start_date]
    if end_date:
        inbox_unreplied = [e for e in inbox_unreplied if (e.get("datetime_received") or "")[:10] <= end_date]
        sent_unreplied = [e for e in sent_unreplied if (e.get("datetime_sent") or "")[:10] <= end_date]

    # تجميع زمني حسب الأيام
    from collections import defaultdict
    inbox_by_day = defaultdict(list)
    for e in inbox_unreplied:
        day = (e.get("datetime_received") or "")[:10] or "غير محدد"
        inbox_by_day[day].append(e)

    sent_by_day = defaultdict(list)
    for e in sent_unreplied:
        day = (e.get("datetime_sent") or "")[:10] or "غير محدد"
        sent_by_day[day].append(e)

    return render_template(
        'report.html',
        inbox_unreplied=inbox_unreplied,
        sent_unreplied=sent_unreplied,
        inbox_by_day=dict(sorted(inbox_by_day.items(), reverse=True)),
        sent_by_day=dict(sorted(sent_by_day.items(), reverse=True)),
        inbox_replied=inbox_replied,
        sent_replied=sent_replied,
        total_inbox=len(inbox),
        total_sent=len(sent),
        start_date=start_date,
        end_date=end_date,
        rep_type=rep_type,
        last_sync=data.get("last_sync")
    )

@app.route('/api/chronological-report', methods=['GET'])
def get_chronological_report():
    """API لاسترجاع التقرير الزمني المجمع بالتواريخ مع الفلاتر"""
    data = load_cache_data()
    start_date = request.args.get('start', '').strip()
    end_date = request.args.get('end', '').strip()
    rep_type = request.args.get('type', 'all_unreplied').strip() # all_unreplied, inbox_unreplied, sent_unreplied

    inbox = [e for e in data.get("inbox", []) if e.get("status_code") == "inbox_unreplied"]
    sent = [e for e in data.get("sent", []) if e.get("status_code") == "sent_unreplied"]

    if start_date:
        inbox = [e for e in inbox if (e.get("datetime_received") or "")[:10] >= start_date]
        sent = [e for e in sent if (e.get("datetime_sent") or "")[:10] >= start_date]
    if end_date:
        inbox = [e for e in inbox if (e.get("datetime_received") or "")[:10] <= end_date]
        sent = [e for e in sent if (e.get("datetime_sent") or "")[:10] <= end_date]

    from collections import defaultdict
    grouped = defaultdict(lambda: {"inbox": [], "sent": []})

    if rep_type in ['all_unreplied', 'inbox_unreplied']:
        for i in inbox:
            day = (i.get("datetime_received") or "")[:10] or "غير محدد"
            grouped[day]["inbox"].append(i)

    if rep_type in ['all_unreplied', 'sent_unreplied']:
        for s in sent:
            day = (s.get("datetime_sent") or "")[:10] or "غير محدد"
            grouped[day]["sent"].append(s)

    sorted_dates = sorted(grouped.keys(), reverse=True)
    report_timeline = []
    for d in sorted_dates:
        report_timeline.append({
            "date": d,
            "inbox_count": len(grouped[d]["inbox"]),
            "sent_count": len(grouped[d]["sent"]),
            "inbox_items": grouped[d]["inbox"],
            "sent_items": grouped[d]["sent"]
        })

    return jsonify({
        "timeline": report_timeline,
        "total_inbox_unreplied": len(inbox),
        "total_sent_unreplied": len(sent),
        "start_date": start_date,
        "end_date": end_date
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """استرجاع الإحصائيات الشاملة وحصر الردود للوارد والصادر"""
    data = load_cache_data()
    inbox = data.get("inbox", [])
    sent = data.get("sent", [])
    attachments = data.get("attachments", [])
    
    inbox_replied = len([e for e in inbox if e.get("status_code") == "inbox_replied"])
    inbox_unreplied = len([e for e in inbox if e.get("status_code") == "inbox_unreplied"])
    
    sent_replied = len([e for e in sent if e.get("status_code") == "sent_replied"])
    sent_unreplied = len([e for e in sent if e.get("status_code") == "sent_unreplied"])
    
    total_inbox = len(inbox)
    total_sent = len(sent)
    
    inbox_reply_rate = round((inbox_replied / total_inbox * 100), 1) if total_inbox > 0 else 0
    sent_reply_rate = round((sent_replied / total_sent * 100), 1) if total_sent > 0 else 0
    
    return jsonify({
        "total_inbox": total_inbox,
        "total_sent": total_sent,
        "inbox_replied_count": inbox_replied,
        "inbox_unreplied_count": inbox_unreplied,
        "sent_replied_count": sent_replied,
        "sent_unreplied_count": sent_unreplied,
        "inbox_reply_rate": inbox_reply_rate,
        "sent_reply_rate": sent_reply_rate,
        "total_attachments": len(attachments),
        "last_sync": data.get("last_sync"),
        "excel_exists": EXCEL_FILE_PATH.exists()
    })

@app.route('/api/emails', methods=['GET'])
def get_emails():
    """
    استرجاع قائمة الإيميلات مع البحث والفلترة:
    - tab:
        - inbox_unreplied (وارد لم يتم الرد عليه)
        - sent_unreplied (صادر بانتظار رد الجهات)
        - inbox_replied (وارد تم الرد عليه)
        - sent_replied (صادر تم استلام رده)
        - inbox_all (كافة الوارد)
        - sent_all (كافة الصادر)
        - has_attachments (به مرفقات)
        - all (الكل مجمع)
    """
    data = load_cache_data()
    tab = request.args.get('tab', 'inbox_unreplied')
    search_query = request.args.get('query', '').strip().lower()
    start_date = request.args.get('start', '').strip()
    end_date = request.args.get('end', '').strip()
    exact_date = request.args.get('exact_date', '').strip()
    party = request.args.get('party', '').strip().lower()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 25))

    inbox = data.get("inbox", [])
    sent = data.get("sent", [])

    if tab == 'inbox_unreplied' or tab == 'unreplied':
        items = [e for e in inbox if e.get("status_code") == "inbox_unreplied"]
    elif tab == 'sent_unreplied':
        items = [e for e in sent if e.get("status_code") == "sent_unreplied"]
    elif tab == 'inbox_replied' or tab == 'replied':
        items = [e for e in inbox if e.get("status_code") == "inbox_replied"]
    elif tab == 'sent_replied':
        items = [e for e in sent if e.get("status_code") == "sent_replied"]
    elif tab == 'inbox_all':
        items = list(inbox)
    elif tab == 'sent_all' or tab == 'sent':
        items = list(sent)
    elif tab == 'has_attachments':
        items = [e for e in (inbox + sent) if len(e.get("attachments", [])) > 0 or len(e.get("attachment_names", [])) > 0]
    else:
        # الكل مجمع ومرتب بالتاريخ
        items = list(inbox + sent)
        items.sort(key=lambda x: x.get("datetime_received") or x.get("datetime_sent") or "", reverse=True)

    # تطبيق فلترة التواريخ
    if start_date:
        items = [e for e in items if (e.get("datetime_received") or e.get("datetime_sent") or "")[:10] >= start_date]
    if end_date:
        items = [e for e in items if (e.get("datetime_received") or e.get("datetime_sent") or "")[:10] <= end_date]
    if exact_date:
        items = [e for e in items if (e.get("datetime_received") or e.get("datetime_sent") or "")[:10] == exact_date]

    if party:
        filtered = []
        for item in items:
            searchable = f"{item.get('sender_name', '')} {item.get('sender_email', '')} {' '.join(item.get('to_recipients_names', []))} {' '.join(item.get('to_recipients_emails', []))}".lower()
            if party in searchable:
                filtered.append(item)
        items = filtered

    # تطبيق البحث النصي الذكي
    if search_query:
        filtered = []
        for item in items:
            searchable = f"{item.get('subject', '')} {item.get('sender_name', '')} {item.get('sender_email', '')} {' '.join(item.get('to_recipients_names', []))} {item.get('summary', '')} {item.get('clean_body', '')}".lower()
            if search_query in searchable:
                filtered.append(item)
        items = filtered

    total_items = len(items)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_items = items[start_idx:end_idx]

    return jsonify({
        "items": paginated_items,
        "total": total_items,
        "page": page,
        "limit": limit,
        "total_pages": (total_items + limit - 1) // limit if limit > 0 else 1
    })

@app.route('/api/email/<path:email_id>', methods=['GET'])
@app.route('/api/email', methods=['GET'])
def get_email_detail(email_id=None):
    """استرجاع التفاصيل الكاملة لإيميل معين"""
    if not email_id:
        email_id = request.args.get('id')
    data = load_cache_data()
    all_emails = data.get("inbox", []) + data.get("sent", [])
    for e in all_emails:
        if str(e.get("id")) == str(email_id):
            return jsonify(e)
    return jsonify({"error": "الرسالة غير موجودة"}), 404

@app.route('/api/sync', methods=['POST'])
def trigger_sync():
    """بدء عملية السحب والمزامنة في الخلفية"""
    if SYNC_PROGRESS.get("is_running"):
        return jsonify({"message": "المزامنة قيد التشغيل حالياً...", "status": "running"}), 400

    req_data = request.get_json(silent=True) or {}
    raw_limit = req_data.get('limit', 100)
    limit = None if raw_limit in [None, 0, '0', 'all', 'الكل'] else int(raw_limit)
    download_files = bool(req_data.get('download_files', True))
    start_date = req_data.get('start_date') or '2026-01-01'
    end_date = req_data.get('end_date') or None
    merge_existing = bool(req_data.get('merge_existing', True))

    def run_sync():
        with sync_lock:
            try:
                fetch_and_process_emails(
                    limit=limit, 
                    download_files=download_files,
                    start_date=start_date,
                    end_date=end_date,
                    merge_existing=merge_existing
                )
            except Exception as e:
                print(f"Sync error: {e}")

    thread = threading.Thread(target=run_sync)
    thread.daemon = True
    thread.start()

    return jsonify({"message": "تم بدء المزامنة بنجاح", "status": "started"})

@app.route('/api/sync-status', methods=['GET'])
def get_sync_status():
    """معرفة نسبة الإنجاز والخطوة الحالية للمزامنة"""
    return jsonify(SYNC_PROGRESS)

@app.route('/api/compare', methods=['POST'])
def api_compare():
    """مقارنة إيميلين جنباً إلى جنب"""
    req_data = request.get_json() or {}
    id_a = req_data.get('id_a')
    id_b = req_data.get('id_b')

    data = load_cache_data()
    all_emails = {str(e.get("id")): e for e in (data.get("inbox", []) + data.get("sent", []))}

    email_a = all_emails.get(str(id_a))
    email_b = all_emails.get(str(id_b))

    if not email_a or not email_b:
        return jsonify({"error": "يرجى تحديد إيميلين صحيحين للمقارنة"}), 400

    comparison_result = compare_emails(email_a, email_b)
    return jsonify(comparison_result)

@app.route('/api/open-excel', methods=['POST'])
def open_excel_desktop():
    """فتح ملف الإكسيل مباشرة في نظام التشغيل"""
    if EXCEL_FILE_PATH.exists():
        try:
            if sys.platform == "win32":
                os.startfile(str(EXCEL_FILE_PATH.resolve()))
            else:
                subprocess.Popen(["xdg-open", str(EXCEL_FILE_PATH)])
            return jsonify({"success": True, "message": "تم فتح ملف الإكسيل في Excel"})
        except Exception as e:
            return jsonify({"error": f"تعذر فتح الملف: {e}"}), 500
    return jsonify({"error": "ملف الإكسيل غير موجود حتى الآن. يرجى بدء المزامنة أولاً."}), 404

@app.route('/api/open-folder', methods=['POST'])
def open_attachments_folder():
    """فتح مجلد المرفقات في متصفح الملفات Windows Explorer"""
    try:
        ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(ATTACHMENTS_DIR.resolve()))
        else:
            subprocess.Popen(["xdg-open", str(ATTACHMENTS_DIR)])
        return jsonify({"success": True, "message": "تم فتح مجلد المرفقات"})
    except Exception as e:
        return jsonify({"error": f"تعذر فتح المجلد: {e}"}), 500

@app.route('/api/open-file', methods=['POST'])
def open_local_file():
    """فتح مرفق محدد مباشرة"""
    req_data = request.get_json() or {}
    fpath = req_data.get('file_path')
    if fpath and os.path.exists(fpath):
        try:
            if sys.platform == "win32":
                os.startfile(fpath)
            else:
                subprocess.Popen(["xdg-open", fpath])
            return jsonify({"success": True, "message": "تم فتح الملف"})
        except Exception as e:
            return jsonify({"error": f"تعذر فتح الملف: {e}"}), 500
    return jsonify({"error": "الملف غير موجود على الجهاز"}), 404

@app.route('/api/export-excel', methods=['GET'])
def download_excel():
    """تنزيل نسخة من ملف الإكسيل عبر المتصفح"""
    if EXCEL_FILE_PATH.exists():
        return send_file(
            EXCEL_FILE_PATH,
            as_attachment=True,
            download_name=f"EHA_Emails_Registry_{Path(EXCEL_FILE_PATH).stem}.xlsx"
        )
    return jsonify({"error": "لم يتم إنشاء ملف الإكسيل بعد"}), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5050))
    print(f"🚀 بدء تشغيل نظام إدارة البريد على: http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
