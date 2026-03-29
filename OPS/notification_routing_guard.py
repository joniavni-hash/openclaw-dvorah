#!/usr/bin/env python3
"""
Notification Routing Guard — enforces OPS/NOTIFICATION_ROUTING_FIX.md at runtime.
Import and call check_channel() before any scheduled send.
"""

DANA_ALLOWED = {"whatsapp"}
DANA_FORBIDDEN = {"telegram", "email", "openai_task_email"}
HEALTH_DIGEST_ENABLED = False  # disabled per NOTIFICATION_ROUTING_FIX.md


def check_dana_channel(channel: str) -> str:
    """
    Returns the enforced channel for Dana reminders.
    Always returns 'whatsapp'; logs if override attempted.
    """
    c = channel.lower().strip()
    if c in DANA_FORBIDDEN:
        print(f"[NotificationGuard] ⛔ Blocked Dana channel '{c}' → forced to 'whatsapp'")
        return "whatsapp"
    if c not in DANA_ALLOWED:
        print(f"[NotificationGuard] ⚠️  Unknown channel '{c}' for Dana → forced to 'whatsapp'")
        return "whatsapp"
    return "whatsapp"


def is_health_digest_allowed(explicit_request: bool = False) -> bool:
    """
    Returns True only if user explicitly requested an infra health digest.
    07:00 automatic Telegram digest is blocked.
    """
    if not explicit_request:
        print("[NotificationGuard] ⛔ Health digest blocked: not an explicit user request")
        return False
    return True


if __name__ == "__main__":
    # Self-test / proof traces
    print("=== Notification Routing Guard — Proof Traces ===")

    # Trace 1: Dana reminder → WhatsApp only
    result = check_dana_channel("whatsapp")
    assert result == "whatsapp", f"FAIL: {result}"
    print(f"✅ Trace 1 — Dana reminder channel=whatsapp → '{result}' ✓")

    # Trace 2: Dana reminder attempted via telegram → blocked
    result = check_dana_channel("telegram")
    assert result == "whatsapp", f"FAIL: {result}"
    print(f"✅ Trace 2 — Dana reminder channel=telegram → forced to '{result}' ✓")

    # Trace 3: Morning scheduler tick (no explicit request) → blocked
    allowed = is_health_digest_allowed(explicit_request=False)
    assert not allowed, "FAIL: digest should be blocked"
    print(f"✅ Trace 3 — health digest without explicit request → blocked={not allowed} ✓")

    print("=== All traces passed ===")
