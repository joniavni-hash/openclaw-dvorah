"""
PR3 — Deterministic No-Model Handlers

Intercepts requests where state already exists and the answer shape is known.
Returns answer from code. No model call. No LLM.

Handlers registered here run BEFORE any agent/model dispatch.
If a handler fires → model_call_skipped=True.
If no handler matches → fall through to normal pipeline.
"""

import json
import re
from datetime import datetime, date
from pathlib import Path
from typing import Any

# ── Pattern matchers ──────────────────────────────────────────────────────────

_QUEUE_PATTERNS = [
    r"(לוז|תוכנית|schedule|queue)\s*(של\s*)?(טלי|tali|הפרסומים|פרסום)",
    r"(מה\s*)?(scheduled|draft|פוסט|posts)\s*(יש|scheduled|draft)",
    r"כמה\s*(scheduled|draftים|drafts|פוסטים)",
    r"(postiz|publish)\s*(queue|status|סטטוס)",
    r"queue\s*status",
    r"draft.{0,10}count",
    r"scheduled.{0,10}count",
]

_HEALTH_PATTERNS = [
    r"(מצב\s*)?(מערכת|system|health)\s*(check|summary|status|בריאות)?",
    r"שירות.{0,20}(פועל|מחובר|תקין|ok)",
    r"(integration|אינטגרציה).{0,15}(מחובר|connected|סטטוס|status)",
    r"האם.{0,20}(google.{0,10}drive|outlook|telegram|whatsapp)\s*(מחובר|connected|פועל|works)",
    r"(connected|מחובר|integration)\s*(status|check)",
]

_COST_PATTERNS = [
    r"כמה\s*(בזבזת|עלה|עולה|הוצאת)",
    r"(cost|עלות|עלויות)\s*(היום|today|usage|שימוש)",
    r"(token|טוקן).{0,20}(cost|עלות|usage)",
    r"(daily|יומי).{0,10}(cost|עלות|spend)",
    r"כמה\s*(טוקנים|tokens)\s*(נצרכו|שמשת|used)",
]

_DAILY_STATUS_PATTERNS = [
    r"(סטטוס|status)\s*(יומי|daily|today|היום)",
    r"מה\s*(קרה|היה|הולך|קורה)\s*(היום|today)",
    r"(daily|יומי)\s*(report|summary|סיכום|דוח)",
    r"(daily|היום)\s*(log|רשומות|פעילות)",
]


def _match(text: str, patterns: list[str]) -> bool:
    t = text.lower().strip()
    return any(re.search(p, t, re.IGNORECASE) for p in patterns)


# ── Data loaders ──────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:
        return None


def _load_queue(workspace: Path) -> dict | None:
    return _load_json(workspace / "state" / "publishing_queue.json")


def _load_health(workspace: Path) -> dict | None:
    return _load_json(workspace / "state" / "health_check.json")


def _load_metrics(workspace: Path) -> dict | None:
    return _load_json(workspace / "state" / "metrics_latest.json")


# ── Handlers ──────────────────────────────────────────────────────────────────

def handle_queue_status(message: str, workspace: Path) -> dict | None:
    """queue status, scheduled_count, draft_count, Tali schedule."""
    if not _match(message, _QUEUE_PATTERNS):
        return None

    q = _load_queue(workspace)
    if not q:
        return None

    stats = q.get("stats", {})
    queue_items = q.get("queue", [])
    scheduled = stats.get("scheduled", 0) or sum(
        1 for i in queue_items if i.get("status") == "scheduled"
    )
    drafts = stats.get("draft", 0) or sum(
        1 for i in queue_items if i.get("status") == "draft"
    )
    total = len(queue_items)
    updated = q.get("updated", q.get("created", "?"))

    text = (
        f"📅 **תור פרסומים — Postiz**\n"
        f"• Scheduled: {scheduled}\n"
        f"• Drafts: {drafts}\n"
        f"• סה\"כ: {total}\n"
        f"• עדכון אחרון: {updated}"
    )
    return _result("queue_status", text, "state/publishing_queue.json")


def handle_health_summary(message: str, workspace: Path) -> dict | None:
    """Health check / integration connected."""
    if not _match(message, _HEALTH_PATTERNS):
        return None

    h = _load_health(workspace)
    if not h:
        return None

    checks = h.get("checks", {})
    summary = h.get("summary", {})
    ok = summary.get("ok", 0)
    total = summary.get("total", 0)
    ts = h.get("timestamp", "?")

    lines = [f"🏥 **Health — {ts}**", f"• {ok}/{total} שירותים תקינים"]
    for name, check in checks.items():
        icon = "✅" if check.get("ok") else "❌"
        status = check.get("status", "?")
        lines.append(f"  {icon} {name}: {status}")

    return _result("health_summary", "\n".join(lines), "state/health_check.json")


def handle_cost_usage(message: str, workspace: Path) -> dict | None:
    """Daily cost / token usage."""
    if not _match(message, _COST_PATTERNS):
        return None

    m = _load_metrics(workspace)
    if not m:
        return None

    cost = m.get("cost", {})
    daily_usd = cost.get("daily_avg_usd") or cost.get("total_usd", 0)
    total_usd = cost.get("total_usd", 0)
    period = m.get("period_days", "?")
    model_stats = m.get("model_stats", {})

    lines = [f"💰 **עלות — {period} ימים אחרונים**",
             f"• סה\"כ: ${total_usd:.4f}",
             f"• ממוצע יומי: ${daily_usd:.4f}" if daily_usd else ""]
    if model_stats:
        for model, stats in list(model_stats.items())[:3]:
            calls = stats.get("calls", 0)
            lines.append(f"  • {model}: {calls} קריאות")

    return _result("cost_usage", "\n".join(l for l in lines if l), "state/metrics_latest.json")


def handle_daily_status(message: str, workspace: Path) -> dict | None:
    """Daily status from structured state."""
    if not _match(message, _DAILY_STATUS_PATTERNS):
        return None

    h = _load_health(workspace)
    m = _load_metrics(workspace)
    q = _load_queue(workspace)

    if not any([h, m, q]):
        return None

    parts = [f"📊 **סטטוס יומי — {date.today().strftime('%d.%m.%Y')}**"]

    if h:
        s = h.get("summary", {})
        parts.append(f"• מערכת: {s.get('ok', 0)}/{s.get('total', 0)} שירותים תקינים")

    if q:
        stats = q.get("stats", {})
        parts.append(f"• פרסומים: {stats.get('scheduled', 0)} scheduled, {stats.get('draft', 0)} drafts")

    if m:
        cost = m.get("cost", {})
        parts.append(f"• עלות: ${cost.get('total_usd', 0):.4f}")

    return _result("daily_status", "\n".join(parts),
                   "state/health_check.json + state/metrics_latest.json + state/publishing_queue.json")


# ── Dispatcher ────────────────────────────────────────────────────────────────

_HANDLER_CHAIN = [
    handle_queue_status,
    handle_health_summary,
    handle_cost_usage,
    handle_daily_status,
]


def try_deterministic(message: str, workspace: Path) -> dict | None:
    """
    Try all deterministic handlers in order.
    Returns a result dict if matched, None if no handler fires.

    Caller must check None → fall through to normal pipeline.
    """
    for handler in _HANDLER_CHAIN:
        result = handler(message, workspace)
        if result is not None:
            return result
    return None


# ── Result builder ────────────────────────────────────────────────────────────

def _result(handler_name: str, text: str, source: str) -> dict:
    return {
        "status": "ok",
        "agent": "דבורה",
        "domain": "deterministic",
        "response_type": "deterministic",
        "requires_approval": False,
        "final_text": text,
        "should_send": True,
        "summary": text[:120],
        "deterministic_path": True,
        "model_call_skipped": True,
        "handler_name": handler_name,
        "source_of_truth": source,
        "metadata": {
            "model_used": "none",
            "model_reason": "deterministic handler — no model call",
            "output_mode": "direct_send",
            "deterministic_path": True,
            "model_call_skipped": True,
            "handler_name": handler_name,
            "source_of_truth": source,
            "duration_ms": 0,
        },
    }
