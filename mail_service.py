import os
import re
import sys
import urllib3
from pathlib import Path
from datetime import datetime
from exchangelib import Credentials, Account, Configuration, DELEGATE, NTLM, FileAttachment, EWSDateTime, EWSTimeZone

# ضبط ترميز الإخراج على ويندوز
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import DEFAULT_CONFIG, ATTACHMENTS_DIR
from analyzer import summarize_email, detect_reply_status_bidirectional, clean_html_text
from excel_manager import write_excel_registry, load_cache_data

# تعطيل تحذيرات SSL للشهادات الداخلية
urllib3.disable_warnings()

# متغير عام لحفظ حالة التقدم الحالية
SYNC_PROGRESS = {
    "is_running": False,
    "current_step": "جاهز",
    "percentage": 0,
    "processed_count": 0,
    "total_count": 0,
    "last_error": None,
    "success": False
}

def sanitize_filename(name: str) -> str:
    """تنظيف اسم الملف أو المجلد من الرموز الممنوعة في نظام التشغيل والتأكد من توافقه مع ويندوز"""
    if not name:
        return "unnamed"
    cleaned = re.sub(r'[\\/*?:"<>|]', '_', name)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ._')
    return cleaned[:80].rstrip(' ._') or "unnamed"

def connect_exchange(email_addr=None, password=None, server=None):
    """إنشاء اتصال آمن بـ Exchange EWS"""
    email_addr = email_addr or DEFAULT_CONFIG["email"]
    password = password or DEFAULT_CONFIG["password"]
    server = server or DEFAULT_CONFIG["server"]
    
    creds = Credentials(username=email_addr, password=password)
    config = Configuration(server=server, credentials=creds, auth_type=NTLM)
    account = Account(
        primary_smtp_address=email_addr, 
        config=config, 
        autodiscover=False, 
        access_type=DELEGATE
    )
    return account

def update_progress(step: str, percentage: int, processed=0, total=0, error=None, success=False, callback=None):
    global SYNC_PROGRESS
    SYNC_PROGRESS["current_step"] = step
    SYNC_PROGRESS["percentage"] = percentage
    SYNC_PROGRESS["processed_count"] = processed
    SYNC_PROGRESS["total_count"] = total
    SYNC_PROGRESS["last_error"] = error
    SYNC_PROGRESS["success"] = success
    if error:
        SYNC_PROGRESS["is_running"] = False
    if callback:
        try:
            callback(SYNC_PROGRESS)
        except Exception:
            pass

def parse_ews_date(dt_str, is_end=False):
    """تحويل نص التاريخ (YYYY-MM-DD) إلى EWSDateTime بتوقيت UTC"""
    if not dt_str:
        return None
    try:
        tz = EWSTimeZone('UTC')
        d = datetime.strptime(str(dt_str)[:10], '%Y-%m-%d')
        if is_end:
            return EWSDateTime(d.year, d.month, d.day, 23, 59, 59, tzinfo=tz)
        return EWSDateTime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)
    except Exception as e:
        print(f"Error parsing date {dt_str}: {e}")
        return None

def fetch_and_process_emails(limit=100, download_files=True, start_date=None, end_date=None, merge_existing=True, progress_callback=None):
    """
    سحب الرسائل من الوارد والمرسل، وتنزيل المرفقات، وتلخيصها، وحصر الردود، وكتابتها في ملف الإكسيل:
    - يدعم تحديد الحد الأقصى (limit=None أو 0 لسحب كافة الرسائل).
    - يدعم الفلترة بنطاق زمني (start_date, end_date) لسحب الرسائل القديمة أو فترة محددة.
    - يدعم دمج الرسائل الجديدة والقديمة (merge_existing=True) دون مسح الرسائل المحفوظة سابقاً.
    """
    global SYNC_PROGRESS
    SYNC_PROGRESS["is_running"] = True
    update_progress("جاري الاتصال بخادم البريد الحكومي...", 5, callback=progress_callback)

    try:
        account = connect_exchange()
        
        # تحويل حدود التاريخ
        ews_start = parse_ews_date(start_date, is_end=False)
        ews_end = parse_ews_date(end_date, is_end=True)

        # تحويل limit
        parsed_limit = None
        if limit and str(limit).lower() not in ['0', 'none', 'all', 'الكل']:
            try:
                parsed_limit = int(limit)
                if parsed_limit <= 0:
                    parsed_limit = None
            except Exception:
                parsed_limit = None

        # -------------------------------------------------------------
        # 1. جلب الرسائل الصادرة (Sent Items)
        # -------------------------------------------------------------
        update_progress("جاري قراءة وتحليل البريد الصادر من الخادم...", 12, callback=progress_callback)
        
        sent_qs = account.sent.all()
        if ews_start and ews_end:
            sent_qs = account.sent.filter(datetime_sent__gte=ews_start, datetime_sent__lte=ews_end)
        elif ews_start:
            sent_qs = account.sent.filter(datetime_sent__gte=ews_start)
        elif ews_end:
            sent_qs = account.sent.filter(datetime_sent__lte=ews_end)

        sent_fields = [
            'subject', 'datetime_sent', 'to_recipients', 'sender', 
            'conversation_id', 'message_id', 'in_reply_to', 'references', 'has_attachments', 'text_body'
        ]
        
        sent_qs = sent_qs.only(*sent_fields).order_by('-datetime_sent')
        if parsed_limit:
            sent_limit = max(parsed_limit, 50)
            sent_items_list = list(sent_qs[:sent_limit])
        else:
            sent_items_list = list(sent_qs)

        total_sent = len(sent_items_list)
        update_progress(f"تم جلب {total_sent} رسالة صادرة، جاري استخراج الملخصات...", 20, 0, total_sent, callback=progress_callback)

        raw_sent = []
        for idx, s_item in enumerate(sent_items_list, 1):
            try:
                s_subj = s_item.subject or "(بدون موضوع)"
                s_body = s_item.text_body or s_item.body or ""
                s_summary_info = summarize_email(s_subj, s_body)
                
                to_names = [r.name for r in s_item.to_recipients if r and r.name] if s_item.to_recipients else []
                to_emails = [r.email_address for r in s_item.to_recipients if r and r.email_address] if s_item.to_recipients else []
                dt_sent = s_item.datetime_sent.isoformat() if s_item.datetime_sent else ""
                
                raw_sent.append({
                    "id": str(s_item.id) if hasattr(s_item, "id") and s_item.id else f"sent_{idx}",
                    "message_id": getattr(s_item, 'message_id', '') or '',
                    "conversation_id": str(getattr(s_item, 'conversation_id', '')) if getattr(s_item, 'conversation_id', None) else '',
                    "in_reply_to": getattr(s_item, 'in_reply_to', '') or '',
                    "references": getattr(s_item, 'references', '') or '',
                    "subject": s_subj,
                    "datetime_sent": dt_sent,
                    "to_recipients_names": to_names,
                    "to_recipients_emails": to_emails,
                    "sender_name": s_item.sender.name if s_item.sender else "",
                    "sender_email": s_item.sender.email_address if s_item.sender else "",
                    "summary": s_summary_info["summary"],
                    "clean_body": s_summary_info["clean_body"],
                    "body": s_body,
                    "attachments": [],
                    "folder": "Sent"
                })
            except Exception as e_s:
                pass

        # -------------------------------------------------------------
        # 2. جلب رسائل صندوق الوارد (Inbox Items)
        # -------------------------------------------------------------
        update_progress("جاري قراءة رسائل صندوق الوارد من الخادم...", 30, callback=progress_callback)
        
        inbox_qs = account.inbox.all()
        if ews_start and ews_end:
            inbox_qs = account.inbox.filter(datetime_received__gte=ews_start, datetime_received__lte=ews_end)
        elif ews_start:
            inbox_qs = account.inbox.filter(datetime_received__gte=ews_start)
        elif ews_end:
            inbox_qs = account.inbox.filter(datetime_received__lte=ews_end)

        inbox_fields = [
            'subject', 'datetime_received', 'sender', 'conversation_id', 
            'message_id', 'has_attachments', 'text_body', 'attachments'
        ]
        
        inbox_qs = inbox_qs.only(*inbox_fields).order_by('-datetime_received')
        if parsed_limit:
            inbox_items_list = list(inbox_qs[:parsed_limit])
        else:
            inbox_items_list = list(inbox_qs)

        total_inbox = len(inbox_items_list)
        update_progress(f"تم جلب {total_inbox} رسالة واردة، جاري المعالجة والمرفقات...", 35, 0, total_inbox, callback=progress_callback)

        raw_inbox = []
        all_attachments = []

        for idx, in_item in enumerate(inbox_items_list, 1):
            if idx % 10 == 0 or idx == total_inbox:
                pct = int(35 + (idx / total_inbox) * 45) if total_inbox > 0 else 50
                update_progress(f"معالجة الوارد ({idx}/{total_inbox})...", pct, idx, total_inbox, callback=progress_callback)

            try:
                in_subj = in_item.subject or "(بدون موضوع)"
                in_body = in_item.text_body or in_item.body or ""
                sender_name = in_item.sender.name if in_item.sender else ""
                sender_email = in_item.sender.email_address if in_item.sender else ""
                dt_recv = in_item.datetime_received.isoformat() if in_item.datetime_received else ""
                
                saved_attachments_for_item = []
                att_names_list = []
                
                if in_item.attachments:
                    date_prefix = in_item.datetime_received.strftime("%Y-%m-%d") if in_item.datetime_received else "undated"
                    folder_name = sanitize_filename(f"{date_prefix}_{sender_name or sender_email}_{in_subj}")[:80]
                    email_att_dir = ATTACHMENTS_DIR / folder_name
                    
                    for att in in_item.attachments:
                        if isinstance(att, FileAttachment) and att.name:
                            att_name = sanitize_filename(att.name)
                            att_names_list.append(att_name)
                            
                            file_saved_path = ""
                            if download_files:
                                try:
                                    email_att_dir.mkdir(parents=True, exist_ok=True)
                                    target_file = email_att_dir / att_name
                                    if not target_file.exists() and hasattr(att, 'content') and att.content:
                                        with open(target_file, 'wb') as f_out:
                                            f_out.write(att.content)
                                        file_saved_path = str(target_file.resolve())
                                    elif target_file.exists():
                                        file_saved_path = str(target_file.resolve())
                                except Exception as att_err:
                                    print(f"Error saving attachment {att.name}: {att_err}")
                                    
                            att_info = {
                                "name": att.name,
                                "extension": Path(att.name).suffix.lower(),
                                "size_bytes": getattr(att, 'size', 0) or 0,
                                "file_path": file_saved_path,
                                "email_id": str(in_item.id) if hasattr(in_item, "id") and in_item.id else "",
                                "email_subject": in_subj,
                                "email_date": dt_recv,
                                "email_sender": sender_name or sender_email
                            }
                            saved_attachments_for_item.append(att_info)
                            all_attachments.append(att_info)

                in_summary_info = summarize_email(in_subj, in_body, att_names_list)

                raw_inbox.append({
                    "id": str(in_item.id) if hasattr(in_item, "id") and in_item.id else f"inbox_{idx}",
                    "message_id": getattr(in_item, 'message_id', '') or '',
                    "conversation_id": str(getattr(in_item, 'conversation_id', '')) if getattr(in_item, 'conversation_id', None) else '',
                    "subject": in_subj,
                    "datetime_received": dt_recv,
                    "sender_name": sender_name,
                    "sender_email": sender_email,
                    "summary": in_summary_info["summary"],
                    "actions": in_summary_info["actions"],
                    "deadlines": in_summary_info["deadlines"],
                    "clean_body": in_summary_info["clean_body"],
                    "body": in_body,
                    "attachments": saved_attachments_for_item,
                    "attachment_names": att_names_list,
                    "folder": "Inbox"
                })
            except Exception as e_in:
                print(f"Error processing inbox item {idx}: {e_in}")

        # -------------------------------------------------------------
        # 3. دمج مع البيانات السابقة بالكاش (Incremental Merging)
        # -------------------------------------------------------------
        final_inbox = raw_inbox
        final_sent = raw_sent
        final_attachments = all_attachments

        if merge_existing:
            update_progress("جاري دمج الرسائل الجديدة مع الرسائل المحفوظة سابقاً...", 82, callback=progress_callback)
            prev_data = load_cache_data()
            prev_inbox = prev_data.get("inbox", [])
            prev_sent = prev_data.get("sent", [])
            prev_att = prev_data.get("attachments", [])

            # دمج الوارد
            inbox_map = {}
            for item in prev_inbox:
                key = item.get("message_id") or item.get("id") or f"{item.get('subject')}_{item.get('datetime_received')}"
                inbox_map[key] = item
            for item in raw_inbox:
                key = item.get("message_id") or item.get("id") or f"{item.get('subject')}_{item.get('datetime_received')}"
                inbox_map[key] = item
            final_inbox = list(inbox_map.values())
            final_inbox.sort(key=lambda x: x.get("datetime_received") or "", reverse=True)

            # دمج الصادر
            sent_map = {}
            for item in prev_sent:
                key = item.get("message_id") or item.get("id") or f"{item.get('subject')}_{item.get('datetime_sent')}"
                sent_map[key] = item
            for item in raw_sent:
                key = item.get("message_id") or item.get("id") or f"{item.get('subject')}_{item.get('datetime_sent')}"
                sent_map[key] = item
            final_sent = list(sent_map.values())
            final_sent.sort(key=lambda x: x.get("datetime_sent") or "", reverse=True)

            # دمج المرفقات
            att_map = {}
            for att in prev_att:
                key = att.get("file_path") or f"{att.get('email_id')}_{att.get('name')}"
                att_map[key] = att
            for att in all_attachments:
                key = att.get("file_path") or f"{att.get('email_id')}_{att.get('name')}"
                att_map[key] = att
            final_attachments = list(att_map.values())

        # -------------------------------------------------------------
        # 4. تشغيل خوارزمية حصر الردود ثنائية الاتجاه على الأرشيف المدمج بالكامل
        # -------------------------------------------------------------
        update_progress("جاري حصر ومطابقة الردود بين الوارد والصادر...", 88, len(final_inbox), len(final_inbox), callback=progress_callback)
        processed_inbox, processed_sent = detect_reply_status_bidirectional(final_inbox, final_sent)

        # -------------------------------------------------------------
        # 5. كتابة البيانات في ملف الإكسيل وحفظ الكاش الشامل
        # -------------------------------------------------------------
        update_progress("جاري كتابة وتنسيق ملف الإكسيل الرئيسي (emails_registry.xlsx)...", 94, len(final_inbox), len(final_inbox), callback=progress_callback)
        excel_path = write_excel_registry(processed_inbox, processed_sent, final_attachments)

        update_progress(f"تم اكتمال المزامنة بنجاح! إجمالي الرسائل: وارد ({len(processed_inbox)}) - صادر ({len(processed_sent)})", 100, len(processed_inbox), len(processed_inbox), success=True, callback=progress_callback)
        SYNC_PROGRESS["is_running"] = False

        return {
            "success": True,
            "excel_path": excel_path,
            "inbox_count": len(processed_inbox),
            "sent_count": len(processed_sent),
            "attachments_count": len(final_attachments)
        }

    except Exception as e:
        print(f"Sync error: {e}")
        update_progress(f"حدث خطأ أثناء المزامنة: {e}", 0, error=str(e), success=False, callback=progress_callback)
        raise e
