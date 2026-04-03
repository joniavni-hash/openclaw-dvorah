#!/usr/bin/env python3
"""
Gett Invoice Auto-Forwarder
מחפש חשבוניות חדשות מגט ומעביר לתהילה@glb.co.il
"""
import subprocess
import json
from datetime import datetime, timedelta

GMAIL_ACCOUNT = "Joni.Avni@gmail.com"
KEYRING_PASS = "1234"
TEHILA_EMAIL = "tehila@glb.co.il"
LABEL = "forwarded-to-tehila"

env = {"GOG_KEYRING_PASSWORD": KEYRING_PASS}
import os
full_env = {**os.environ, **env}

# חפש חשבוניות מגט שלא הועברו עדיין
result = subprocess.run([
    "gog", "gmail", "list",
    f"from:gett.com subject:חשבונית -label:{LABEL}",
    "-a", GMAIL_ACCOUNT, "--json"
], capture_output=True, text=True, env=full_env)

messages = json.loads(result.stdout) if result.stdout.strip() else []
threads = messages.get("threads", []) if isinstance(messages, dict) else []

if not threads:
    print("אין חשבוניות חדשות")
    exit(0)

for thread in threads:
    msg_id = thread.get("id")
    subject = thread.get("subject", "חשבונית גט")
    
    # שלח לתהילה
    send_result = subprocess.run([
        "gog", "gmail", "send",
        "--to", TEHILA_EMAIL,
        "--subject", f"Fwd: {subject}",
        "--body", f"תהילה שלום, מצורפת חשבונית גט חדשה: {subject}. יוני",
        "--thread-id", msg_id,
        "-a", GMAIL_ACCOUNT
    ], capture_output=True, text=True, env=full_env)
    
    if send_result.returncode == 0:
        # תייג כ-forwarded
        subprocess.run([
            "gog", "gmail", "labels", "add", msg_id,
            "--label", LABEL,
            "-a", GMAIL_ACCOUNT
        ], capture_output=True, text=True, env=full_env)
        print(f"✅ הועבר: {subject}")
    else:
        print(f"❌ שגיאה: {send_result.stderr}")

