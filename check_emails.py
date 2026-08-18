import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('data_cache.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

print("=== INBOX EMAILS ===")
for i, e in enumerate(d.get('inbox', []), 1):
    status = e.get('status')
    subj = e.get('subject')
    sender = e.get('sender_name') or e.get('sender_email')
    dt = e.get('datetime_received')
    actions = e.get('actions', [])
    print(f"{i}. [{status}] {subj}\n   From: {sender} | Date: {dt}")
    if actions:
        print(f"   Actions required: {actions[:1]}")

print("\n=== SENT EMAILS ===")
for i, e in enumerate(d.get('sent', [])[:15], 1):
    subj = e.get('subject')
    to = e.get('to_recipients_names') or e.get('to_recipients_emails')
    dt = e.get('datetime_sent')
    print(f"{i}. {subj}\n   To: {to} | Date: {dt}")
