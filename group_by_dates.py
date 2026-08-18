import json
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

with open('data_cache.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

in_un = [e for e in d.get('inbox', []) if e.get('status_code') == 'inbox_unreplied']
sent_un = [e for e in d.get('sent', []) if e.get('status_code') == 'sent_unreplied']

in_by_date = defaultdict(list)
for item in in_un:
    dt = item.get('datetime_received', '')[:10] or 'غير محدد'
    in_by_date[dt].append(item)

sent_by_date = defaultdict(list)
for item in sent_un:
    dt = item.get('datetime_sent', '')[:10] or 'غير محدد'
    sent_by_date[dt].append(item)

print("=== INBOX UNREPLIED GROUPED BY DATE ===")
for dt, items in sorted(in_by_date.items(), reverse=True):
    print(f"\n📅 تاريخ {dt} (عدد: {len(items)} رسائل):")
    for it in items:
        time_str = it.get('datetime_received', '')[11:16]
        sender = it.get('sender_name') or it.get('sender_email')
        subj = it.get('subject')
        acts = it.get('actions', [])
        act = acts[0] if acts else (it.get('summary', '')[:80] + '...')
        print(f"   • [{time_str}] {subj}")
        print(f"     └─ من: {sender} | 📌 الإجراء/الملخص: {act}")

print("\n" + "="*80)
print("=== SENT UNREPLIED GROUPED BY DATE ===")
for dt, items in sorted(sent_by_date.items(), reverse=True):
    print(f"\n📅 تاريخ {dt} (عدد: {len(items)} رسائل):")
    for it in items:
        time_str = it.get('datetime_sent', '')[11:16]
        to_names = ', '.join(it.get('to_recipients_names', []) or it.get('to_recipients_emails', []))
        subj = it.get('subject')
        summ = it.get('summary', '')[:90]
        print(f"   • [{time_str}] {subj}")
        print(f"     └─ إلى: {to_names} | 📄 الموضوع: {summ}")
