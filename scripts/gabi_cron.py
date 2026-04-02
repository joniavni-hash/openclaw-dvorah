#!/usr/bin/env python3
"""
גבי — Autonomous Health Check
מריץ health check ושולח WhatsApp רק אם יש alert.
אם הכל תקין — שקט מוחלט.

Alerts:
- שירות נפל (ok=False)
- עדכון OpenClaw זמין מעל 3 ימים
- עלות יומית > $4
- שגיאות מעל 5%
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
STATE_HEALTH = WORKSPACE / "state" / "health_check.json"
STATE_ERRORS = WORKSPACE / "state" / "error_digest_latest.json"
STATE_METRICS = WORKSPACE / "state" / "metrics_latest.json"
OPENCLAW_BIN = "/home/jonia/.npm-global/bin/openclaw"
YONI = "+972543333556"

def send_whatsapp(msg: str):
    subprocess.run([
        OPENCLAW_BIN, "message", "send",
        "--channel", "whatsapp",
        "--target", YONI,
        "--message", msg
    ])

def run_health_check():
    subprocess.run([sys.executable, str(WORKSPACE / "scripts" / "health_check.py")],
                   capture_output=True)

def check_alerts() -> list[str]:
    alerts = []
    ts = datetime.now().strftime("%d/%m %H:%M")

    # 1. Services
    if STATE_HEALTH.exists():
        health = json.loads(STATE_HEALTH.read_text())
        for name, check in health.get("checks", {}).items():
            if check.get("ok") is False:
                status = check.get("status", "unknown")
                alerts.append(f"❌ שירות נפל: *{name}* ({status})")

    # 2. Update available > 3 days
    if STATE_METRICS.exists():
        try:
            metrics = json.loads(STATE_METRICS.read_text())
            update_age = metrics.get("update_available_days", 0)
            current = metrics.get("current_version", "?")
            latest = metrics.get("latest_version", "?")
            if update_age and int(update_age) >= 3 and current != latest:
                alerts.append(f"🔄 עדכון ממתין {update_age} ימים: {current} → {latest}")
        except Exception:
            pass

    # 3. Error rate > 5%
    if STATE_ERRORS.exists():
        try:
            errors = json.loads(STATE_ERRORS.read_text())
            s = errors.get("summary", {})
            rate = s.get("error_rate", 0)
            if rate > 0.05:
                alerts.append(f"⚠️ שגיאות: {rate:.0%} ({s.get('errors',0)}/{s.get('total_requests',0)})")
        except Exception:
            pass

    # 4. Daily cost > $4
    if STATE_METRICS.exists():
        try:
            metrics = json.loads(STATE_METRICS.read_text())
            cost = metrics.get("daily_cost_usd", 0)
            if float(cost) > 4.0:
                alerts.append(f"💸 עלות יומית גבוהה: ${cost:.2f}")
        except Exception:
            pass

    return alerts

def main():
    run_health_check()
    alerts = check_alerts()

    if alerts:
        ts = datetime.now().strftime("%d/%m %H:%M")
        lines = [f"🔧 *גבי — Alert* | {ts}"]
        lines.extend(alerts)
        send_whatsapp("\n".join(lines))
    # else: שקט מוחלט

if __name__ == "__main__":
    main()
