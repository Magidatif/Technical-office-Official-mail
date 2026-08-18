import re
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

def clean_html_text(html_or_text: str) -> str:
    """تنظيف النص من وسوم HTML والتواقيع المكررة وحواشي الخادم"""
    if not html_or_text:
        return ""
    
    # تحويل HTML إلى نص عادي
    if "<" in html_or_text and ">" in html_or_text:
        try:
            soup = BeautifulSoup(html_or_text, "html.parser")
            # إزالة النصوص البرمجية والأنماط
            for element in soup(["script", "style", "head", "title", "meta"]):
                element.decompose()
            text = soup.get_text(separator="\n")
        except Exception:
            text = html_or_text
    else:
        text = html_or_text

    # تنظيف الفراغات والأسطر الفارغة الزائدة
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned_lines = []
    
    # حذف حواشي البريد الرسمية المتكررة مثل disclaimer
    disclaimer_keywords = [
        "this e-mail and any files transmitted with it are confidential",
        "تنبيه: هذا البريد الإلكتروني ومرفقاته سري للغاية",
        "save a tree",
        "before printing this email",
        "eha.gov.eg",
        "disclaimer:",
        "الهيئة العامة للرعاية الصحية",
    ]
    
    for line in lines:
        line_lower = line.lower()
        # تخطي الأسطر التي تحتوي فقط على تنبيهات الحماية والسرية المكررة إذا كانت في النهاية
        if any(dkw in line_lower for dkw in disclaimer_keywords) and len(cleaned_lines) > 3:
            continue
        cleaned_lines.append(line)
        
    return "\n".join(cleaned_lines)

def summarize_email(subject: str, body: str, attachment_names: list = None) -> dict:
    """
    محرك تلخيص ذكي متطور للمحتوى العربي:
    - تخطي ترويسات وأسماء التحية المبدئية (مثل: تحية طيبة وبعد، السيد الدكتور / ...)
    - استخراج الهدف الحقيقي للرسالة
    - استخراج التكليفات والطلبات (Action Items)
    - استخراج المواعيد والتواريخ
    - دعم الإيميلات التي يكون محتواها في المرفقات
    """
    clean_body = clean_html_text(body)
    
    # الكلمات الدلالية للطلبات والتكليفات
    action_triggers = [
        "برجاء", "يرجى", "مطلوب", "تكليف", "موافاتنا", "التكرم", "إرسال", "تجهيز", 
        "حصر", "متابعة", "سرعة", "للعلم والإحاطة", "إفادتنا", "للتوجيه", "للاتخاذ اللازم",
        "نحيطكم علماً", "نرجو", "التنسيق", "العرض على", "المستندات المطلوبة", "حضور اجتماع", "توجيه مندوب"
    ]
    
    # كلمات المواعيد
    deadline_triggers = [
        "في موعد أقصاه", "خلال موعد غايته", "قبل يوم", "تاريخ", "موعد أقصاه", "خلال اليوم", 
        "عاجل وهام", "أقصاه يوم", "موعد نهائي", "الساعة", "الموافق"
    ]

    # أسطر يجب استبعادها كملخص (مثل التحيات وتوجيه الخطاب)
    greeting_starters = [
        "السيد الدكتور", "السيد الأستاذ", "السادة الزملاء", "تحية طيبة وبعد", "السلام عليكم",
        "عناية السيد", "إلى السيد", "الزملاء الأعزاء", "dear all", "hello", "good morning"
    ]
    
    lines = [l.strip() for l in clean_body.splitlines() if len(l.strip()) > 3]
    
    extracted_actions = []
    extracted_deadlines = []
    content_lines = []
    
    for line in lines:
        line_clean = line.strip()
        # فحص التكليفات
        for trig in action_triggers:
            if trig in line_clean and line_clean not in extracted_actions:
                extracted_actions.append(line_clean)
                break
                
        # فحص المواعيد
        for dtrig in deadline_triggers:
            if dtrig in line_clean and line_clean not in extracted_deadlines:
                extracted_deadlines.append(line_clean)
                break
                
        # فحص إذا كان السطر يمثل متناً حقيقياً وليس تحية
        is_greeting = any(line_clean.startswith(g) or line_clean.lower().startswith(g) for g in greeting_starters)
        if not is_greeting and len(line_clean) > 10:
            content_lines.append(line_clean)

    # بناء الملخص
    summary_parts = []
    if content_lines:
        # نأخذ أول سطرين جوهريين
        summary_parts.append(content_lines[0])
        if len(content_lines) > 1 and len(content_lines[0]) < 80:
            summary_parts.append(content_lines[1])
    elif extracted_actions:
        summary_parts.append(extracted_actions[0])
    elif lines:
        summary_parts.append(lines[0])
    else:
        # إذا كان الإيميل فارغاً ومحتواه في المرفق
        if attachment_names and len(attachment_names) > 0:
            summary_parts.append(f"المحتوى مدرج بالمرفقات: ({', '.join(attachment_names[:2])})")
        else:
            summary_parts.append(subject or "رسالة بدون محتوى نصي")

    if extracted_deadlines and not any(d in " ".join(summary_parts) for d in extracted_deadlines[:1]):
        summary_parts.append("⏳ " + extracted_deadlines[0])
        
    executive_summary = " - ".join(summary_parts)
    if len(executive_summary) > 400:
        executive_summary = executive_summary[:397] + "..."
        
    return {
        "summary": executive_summary or subject or "لا يوجد ملخص",
        "actions": extracted_actions[:5],
        "deadlines": extracted_deadlines[:3],
        "clean_body": clean_body
    }

def normalize_subject(subject: str) -> str:
    """تجريد الموضوع من بادئات الرد والتوجيه للمطابقة الدقيقة"""
    if not subject:
        return ""
    sub = subject.strip()
    # إزالة البادئات بالإنجليزية والعربية
    patterns = [
        r'^(re|fw|fwd|رد|توجيه|اعادة توجيه|إعادة توجيه)\s*:\s*',
        r'^\[(external|eha|spam|outbound|inbound)\]\s*',
        r'^\s*:\s*'
    ]
    changed = True
    while changed:
        changed = False
        for p in patterns:
            new_sub = re.sub(p, '', sub, flags=re.IGNORECASE).strip()
            if new_sub != sub:
                sub = new_sub
                changed = True
    return sub.strip()

def detect_reply_status_bidirectional(inbox_emails: list, sent_emails: list) -> tuple:
    """
    خوارزمية حصر ومطابقة الردود ثنائية الاتجاه (الوارد والصادر):
    1. حصر الوارد:
       - تم الرد عليه من المكتب الفني
       - لم يتم الرد عليه (معلق لدى المكتب الفني)
    2. حصر الصادر:
       - تم استلام رد عليه من الجهات المعنية
       - بانتظار رد الجهة (معلق لدى الجهات الخارجية/المستشفيات/الإدارات)
    """
    # -------------------------------------------------------------
    # خرائط فهرسة الرسائل الصادرة والواردة
    # -------------------------------------------------------------
    sent_by_conv = {}
    sent_by_subj = {}
    sent_by_mid = {}

    inbox_by_conv = {}
    inbox_by_subj = {}
    inbox_by_mid = {}

    for s in sent_emails:
        cid = s.get("conversation_id")
        if cid: sent_by_conv.setdefault(cid, []).append(s)
        mid = s.get("message_id")
        if mid: sent_by_mid.setdefault(mid, []).append(s)
        norm_subj = normalize_subject(s.get("subject", "")).lower()
        if norm_subj and len(norm_subj) > 3:
            sent_by_subj.setdefault(norm_subj, []).append(s)

    for i in inbox_emails:
        cid = i.get("conversation_id")
        if cid: inbox_by_conv.setdefault(cid, []).append(i)
        mid = i.get("message_id")
        if mid: inbox_by_mid.setdefault(mid, []).append(i)
        norm_subj = normalize_subject(i.get("subject", "")).lower()
        if norm_subj and len(norm_subj) > 3:
            inbox_by_subj.setdefault(norm_subj, []).append(i)

    # -------------------------------------------------------------
    # 1. معالجة وتصنيف صندوق الوارد (Inbox)
    # -------------------------------------------------------------
    processed_inbox = []
    for email in inbox_emails:
        item = dict(email)
        cid = item.get("conversation_id")
        mid = item.get("message_id")
        norm_subj = normalize_subject(item.get("subject", "")).lower()
        recv_dt = item.get("datetime_received")
        sender_email = (item.get("sender_email") or "").lower()

        matched_reply = None

        # مطابقة بـ Conversation ID
        if cid and cid in sent_by_conv:
            candidates = [s for s in sent_by_conv[cid] if not recv_dt or not s.get("datetime_sent") or s.get("datetime_sent") >= recv_dt]
            if candidates: matched_reply = candidates[0]

        # مطابقة بـ In-Reply-To / References
        if not matched_reply and mid:
            for s in sent_emails:
                if mid in (s.get("in_reply_to") or "") or mid in (s.get("references") or ""):
                    matched_reply = s
                    break

        # مطابقة بالموضوع والمستلم
        if not matched_reply and norm_subj and norm_subj in sent_by_subj:
            for s in sent_by_subj[norm_subj]:
                s_recips = [r.lower() for r in (s.get("to_recipients_emails") or [])]
                s_sent = s.get("datetime_sent")
                is_after = (not recv_dt or not s_sent or s_sent >= recv_dt)
                is_to_sender = (sender_email in s_recips) or not sender_email
                if is_after and is_to_sender:
                    matched_reply = s
                    break

        if matched_reply:
            item["status"] = "تم الرد عليه"
            item["status_code"] = "inbox_replied"
            item["reply_id"] = matched_reply.get("id")
            item["reply_subject"] = matched_reply.get("subject")
            item["reply_datetime"] = matched_reply.get("datetime_sent")
            item["replied_by"] = matched_reply.get("sender_name") or matched_reply.get("sender_email")
        else:
            subj_lower = item.get("subject", "").lower()
            if any(k in subj_lower for k in ["نشرة", "إعلامي", "newsletter", "no-reply", "noreply"]):
                item["status"] = "إعلامي / دوري"
                item["status_code"] = "circular"
            else:
                item["status"] = "لم يتم الرد عليه (معلق)"
                item["status_code"] = "inbox_unreplied"
            item["reply_id"] = ""
            item["reply_subject"] = ""
            item["reply_datetime"] = ""
            item["replied_by"] = ""

        processed_inbox.append(item)

    # -------------------------------------------------------------
    # 2. معالجة وتصنيف البريد الصادر (Sent)
    # -------------------------------------------------------------
    processed_sent = []
    for s_email in sent_emails:
        s_item = dict(s_email)
        cid = s_item.get("conversation_id")
        mid = s_item.get("message_id")
        norm_subj = normalize_subject(s_item.get("subject", "")).lower()
        sent_dt = s_item.get("datetime_sent")
        recips = [r.lower() for r in (s_item.get("to_recipients_emails") or [])]

        matched_incoming = None

        # مطابقة بـ Conversation ID
        if cid and cid in inbox_by_conv:
            candidates = [i for i in inbox_by_conv[cid] if not sent_dt or not i.get("datetime_received") or i.get("datetime_received") >= sent_dt]
            if candidates: matched_incoming = candidates[0]

        # مطابقة بـ In-Reply-To
        if not matched_incoming and mid:
            for i in inbox_emails:
                if mid in (i.get("in_reply_to") or "") or mid in (i.get("references") or ""):
                    matched_incoming = i
                    break

        # مطابقة بالموضوع
        if not matched_incoming and norm_subj and norm_subj in inbox_by_subj:
            for i in inbox_by_subj[norm_subj]:
                i_sender = (i.get("sender_email") or "").lower()
                i_recv = i.get("datetime_received")
                is_after = (not sent_dt or not i_recv or i_recv >= sent_dt)
                is_from_recip = (i_sender in recips) or not recips
                if is_after and is_from_recip:
                    matched_incoming = i
                    break

        if matched_incoming:
            s_item["status"] = "تم استلام الرد"
            s_item["status_code"] = "sent_replied"
            s_item["response_from"] = matched_incoming.get("sender_name") or matched_incoming.get("sender_email")
            s_item["response_date"] = matched_incoming.get("datetime_received")
            s_item["response_subject"] = matched_incoming.get("subject")
        else:
            s_item["status"] = "بانتظار رد الجهة"
            s_item["status_code"] = "sent_unreplied"
            s_item["response_from"] = ""
            s_item["response_date"] = ""
            s_item["response_subject"] = ""

        processed_sent.append(s_item)

    return processed_inbox, processed_sent

def compare_emails(email_a: dict, email_b: dict) -> dict:
    """مقارنة تفصيلية بين إيميلين لكشف التشابهات والفروقات في النصوص والمرفقات"""
    body_a = email_a.get("clean_body") or clean_html_text(email_a.get("body", ""))
    body_b = email_b.get("clean_body") or clean_html_text(email_b.get("body", ""))
    
    # حساب نسبة التشابه النصي
    similarity_ratio = round(SequenceMatcher(None, body_a, body_b).ratio() * 100, 1)
    
    # مقارنة المرفقات
    att_a = set(email_a.get("attachment_names", []))
    att_b = set(email_b.get("attachment_names", []))
    
    common_attachments = list(att_a.intersection(att_b))
    unique_to_a = list(att_a - att_b)
    unique_to_b = list(att_b - att_a)
    
    return {
        "similarity_score_pct": similarity_ratio,
        "email_a": {
            "id": email_a.get("id"),
            "subject": email_a.get("subject"),
            "sender": email_a.get("sender_name") or email_a.get("sender_email"),
            "datetime": email_a.get("datetime_received") or email_a.get("datetime_sent"),
            "summary": email_a.get("summary"),
            "attachments": list(att_a),
            "attachments_count": len(att_a),
            "body": body_a
        },
        "email_b": {
            "id": email_b.get("id"),
            "subject": email_b.get("subject"),
            "sender": email_b.get("sender_name") or email_b.get("sender_email"),
            "datetime": email_b.get("datetime_received") or email_b.get("datetime_sent"),
            "summary": email_b.get("summary"),
            "attachments": list(att_b),
            "attachments_count": len(att_b),
            "body": body_b
        },
        "attachments_comparison": {
            "common": common_attachments,
            "unique_to_first": unique_to_a,
            "unique_to_second": unique_to_b
        }
    }
