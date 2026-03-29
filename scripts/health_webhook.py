#!/usr/bin/env python3
"""
Apple Health webhook endpoint for Dana.

Receives health sync data via POST /health, stores it in the fitness
health log (via HealthBridge), appends a summary to fitness_tracker.md,
and sends a WhatsApp notification to Dana.

Port: env HEALTH_WEBHOOK_PORT (default 8766)
Auth: env HEALTH_WEBHOOK_TOKEN (or from secrets/.env)

---
To run as a systemd service:
  [Unit]
  Description=OpenClaw Health Webhook
  After=network.target

  [Service]
  WorkingDirectory=/home/jonia/.openclaw/workspace
  EnvironmentFile=/home/jonia/.openclaw/workspace/secrets/.env
  ExecStart=/usr/bin/python3 /home/jonia/.openclaw/workspace/scripts/health_webhook.py
  Restart=on-failure

  [Install]
  WantedBy=multi-user.target

Or as a cron @reboot entry:
  @reboot /home/jonia/.openclaw/workspace/scripts/start_health_webhook.sh
"""

import json
import os
import subprocess
import sys
import threading
from datetime import date, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE / "agents" / "dana-fitness"))

from health_bridge import HealthBridge

FITNESS_TRACKER = WORKSPACE / "state" / "fitness_tracker.md"
SECRETS_ENV = WORKSPACE / "secrets" / ".env"

# ── config ───────────────────────────────────────────────────────────
PORT = int(os.environ.get("HEALTH_WEBHOOK_PORT", "8766"))
TOKEN = os.environ.get("HEALTH_WEBHOOK_TOKEN", "")
DANA_PHONE = "+972543333556"

# Load token from secrets/.env if not set
if not TOKEN and SECRETS_ENV.exists():
    for line in SECRETS_ENV.read_text().splitlines():
        line = line.strip()
        if line.startswith("HEALTH_WEBHOOK_TOKEN="):
            TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")
            break

VALID_FIELDS = {"type", "steps", "sleep_hours", "heart_rate", "weight_kg", "date"}

bridge = HealthBridge()


# ── helpers ──────────────────────────────────────────────────────────
def validate_payload(data: dict) -> str | None:
    """Return error string or None if valid."""
    if not isinstance(data, dict):
        return "payload must be a JSON object"
    if data.get("type") != "health_sync":
        return "type must be 'health_sync'"
    unknown = set(data.keys()) - VALID_FIELDS
    if unknown:
        return f"unknown fields: {', '.join(sorted(unknown))}"
    return None


def store_health_data(data: dict) -> dict:
    """Persist via HealthBridge and append to fitness_tracker.md."""
    day = data.get("date", date.today().isoformat())

    record = {"date": day, "source": "apple_health"}
    if "steps" in data:
        record["steps"] = int(data["steps"])
    if "sleep_hours" in data:
        record["sleep_hours"] = float(data["sleep_hours"])
    if "heart_rate" in data:
        record["resting_hr"] = int(data["heart_rate"])
    if "weight_kg" in data:
        record["weight"] = float(data["weight_kg"])

    result = bridge.upsert_day(record)

    # Append summary to fitness_tracker.md
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = []
    if "steps" in data:
        parts.append(f"צעדים: {data['steps']}")
    if "sleep_hours" in data:
        parts.append(f"שינה: {data['sleep_hours']}h")
    if "heart_rate" in data:
        parts.append(f"דופק: {data['heart_rate']}")
    if "weight_kg" in data:
        parts.append(f"משקל: {data['weight_kg']}kg")

    if parts:
        entry = f"\n## {now}\n📊 Health sync ({day}): {' | '.join(parts)}\n"
        with open(FITNESS_TRACKER, "a", encoding="utf-8") as f:
            f.write(entry)

    return result


def send_whatsapp_notification(data: dict):
    """Send WhatsApp message to Dana via openclaw CLI."""
    parts = []
    if "steps" in data:
        parts.append(f"steps={data['steps']}")
    if "sleep_hours" in data:
        parts.append(f"sleep={data['sleep_hours']}h")
    if "heart_rate" in data:
        parts.append(f"hr={data['heart_rate']}")
    if "weight_kg" in data:
        parts.append(f"weight={data['weight_kg']}kg")

    msg = f"📊 Health sync received: {' | '.join(parts)}" if parts else "📊 Health sync received (no metrics)"

    try:
        subprocess.run(
            ["openclaw", "message", "send",
             "--channel", "whatsapp",
             "-t", DANA_PHONE,
             "-m", msg],
            timeout=15,
            capture_output=True,
        )
        print(f"[health_webhook] WhatsApp sent to {DANA_PHONE}")
    except Exception as e:
        print(f"[health_webhook] WhatsApp send failed: {e}")


# ── HTTP handler ─────────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):

    def _send_json(self, code: int, obj: dict):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check_auth(self) -> bool:
        if not TOKEN:
            return True  # no token configured — open
        auth = self.headers.get("Authorization", "")
        if auth == f"Bearer {TOKEN}":
            return True
        self._send_json(401, {"ok": False, "error": "unauthorized"})
        return False

    def do_POST(self):
        if self.path != "/health":
            self._send_json(404, {"ok": False, "error": "not found"})
            return

        if not self._check_auth():
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return

        err = validate_payload(data)
        if err:
            self._send_json(400, {"ok": False, "error": err})
            return

        store_health_data(data)

        # Fire-and-forget WhatsApp notification
        threading.Thread(target=send_whatsapp_notification, args=(data,), daemon=True).start()

        received = {k: v for k, v in data.items() if k != "type"}
        self._send_json(200, {"ok": True, "received": received})

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "health_webhook"})
        else:
            self._send_json(404, {"ok": False, "error": "not found"})

    def log_message(self, fmt, *args):
        print(f"[health_webhook] {args[0]}" if args else "")


# ── server ───────────────────────────────────────────────────────────
def run_server(port: int = PORT, block: bool = True) -> HTTPServer:
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"[health_webhook] listening on 0.0.0.0:{port}")
    if block:
        server.serve_forever()
    else:
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
    return server


# ── self-test ────────────────────────────────────────────────────────
def self_test():
    import urllib.request

    port = 18766  # use a non-conflicting port for test
    server = run_server(port=port, block=False)

    test_payload = {
        "type": "health_sync",
        "steps": 8432,
        "sleep_hours": 7.2,
        "heart_rate": 68,
        "weight_kg": 79.5,
        "date": date.today().isoformat(),
    }

    passed = 0
    failed = 0

    def check(name: str, ok: bool):
        nonlocal passed, failed
        if ok:
            passed += 1
            print(f"  PASS: {name}")
        else:
            failed += 1
            print(f"  FAIL: {name}")

    try:
        # Test 1: valid POST
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/health",
            data=json.dumps(test_payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
            check("valid POST returns ok=true", body.get("ok") is True)
            check("received contains steps", body.get("received", {}).get("steps") == 8432)

        # Test 2: missing type
        bad = {"steps": 100}
        req2 = urllib.request.Request(
            f"http://127.0.0.1:{port}/health",
            data=json.dumps(bad).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req2)
            check("missing type rejected", False)
        except urllib.error.HTTPError as e:
            check("missing type rejected", e.code == 400)

        # Test 3: unknown fields
        bad2 = {"type": "health_sync", "bogus": 1}
        req3 = urllib.request.Request(
            f"http://127.0.0.1:{port}/health",
            data=json.dumps(bad2).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req3)
            check("unknown fields rejected", False)
        except urllib.error.HTTPError as e:
            check("unknown fields rejected", e.code == 400)

        # Test 4: GET health check
        req4 = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        with urllib.request.urlopen(req4) as resp:
            body = json.loads(resp.read())
            check("GET /health returns status ok", body.get("status") == "ok")

        # Test 5: 404
        req5 = urllib.request.Request(f"http://127.0.0.1:{port}/nope")
        try:
            urllib.request.urlopen(req5)
            check("unknown path returns 404", False)
        except urllib.error.HTTPError as e:
            check("unknown path returns 404", e.code == 404)

    finally:
        server.shutdown()

    total = passed + failed
    print(f"\n{'PASS' if failed == 0 else 'FAIL'}: {passed}/{total} tests passed")
    return failed == 0


# ── main ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--serve" in sys.argv:
        run_server()
    else:
        print("[health_webhook] running self-test...")
        ok = self_test()
        sys.exit(0 if ok else 1)
