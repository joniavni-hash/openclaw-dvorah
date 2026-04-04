"""
PR1 — Deterministic History Selector v1

Reduces conversation history payload before model calls.
No LLM calls. No embeddings. Pure deterministic selection.
"""

import re
from typing import Any


# ── Boost markers ────────────────────────────────────────────────────────────

DECISION_MARKERS = [
    "סיכמנו", "הוחלט", "שלחתי", "קבעתי", "תמשכי", "commit",
    "scheduled", "approved", "בוצע", "נשלח", "נקבע",
]

DATE_MARKERS = [
    r"\d{1,2}[./]\d{1,2}([./]\d{2,4})?",   # 3.4 / 03/04/2026
    r"\b(ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)\b",
    r"\b(ינואר|פברואר|מרץ|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר)\b",
    r"\b\d{2}:\d{2}\b",                      # 14:30
    r"\b(today|tomorrow|tonight|morning|evening)\b",
]

TOOL_MARKERS = [
    r"postiz[_\-]?id",
    r"\b[0-9a-f]{7,40}\b",   # commit hash
    r"scheduled_count",
    r"draft_count",
    r"queue_health",
    r"execution_id",
    r'"status"',
    r"health_check",
]

KNOWN_ENTITIES = [
    "villa lithos", "ליתוס", "וילה", "dana", "דנה", "tali", "טלי",
    "postiz", "google drive", "whatsapp", "גבי", "gabi", "צופית", "tzofit",
    "אודיה", "odya", "אתי", "eti", "מאשה", "masha", "newton", "citykids",
    "friends", "kappasense", "שני", "אלון", "ניב", "רני", "מתן",
]


def _text(turn: dict) -> str:
    """Extract text content from a turn dict."""
    content = turn.get("content", "")
    if isinstance(content, list):
        return " ".join(
            p.get("text", "") for p in content if isinstance(p, dict)
        )
    return str(content)


def _has_decision(text: str) -> bool:
    tl = text.lower()
    return any(m.lower() in tl for m in DECISION_MARKERS)


def _has_date(text: str) -> bool:
    for p in DATE_MARKERS:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def _has_tool_result(text: str) -> bool:
    for p in TOOL_MARKERS:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def _entity_overlap(text: str, entities: list[str]) -> bool:
    tl = text.lower()
    for e in entities:
        if e.lower() in tl:
            return True
    return False


def _extract_entities(message: str) -> list[str]:
    """Return which known entities appear in the current message."""
    ml = message.lower()
    return [e for e in KNOWN_ENTITIES if e.lower() in ml]


def select_relevant_history(
    history: list[dict[str, Any]],
    current_message: str,
    mentioned_entities: list[str] | None = None,
    recency_window: int = 12,
    max_selected: int = 40,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Deterministically select the most relevant prior turns.

    Returns:
        (selected_turns, selector_meta)
    """
    total = len(history)

    # Fast-path: small history — return as-is
    if total <= recency_window:
        meta = {
            "history_total_turns": total,
            "history_selected_turns": total,
            "history_dropped_turns": 0,
            "history_selector_used": True,
            "history_selector_reason_summary": "small_history_passthrough",
        }
        return history, meta

    entities = mentioned_entities or _extract_entities(current_message)

    # Always keep the recency window
    recency_set = set(range(total - recency_window, total))
    boost_set: set[int] = set()
    reason_parts: list[str] = []

    for i, turn in enumerate(history):
        if i in recency_set:
            continue
        text = _text(turn)

        if _has_decision(text):
            boost_set.add(i)
            reason_parts.append("decision")
        if _has_date(text):
            boost_set.add(i)
            reason_parts.append("date")
        if _has_tool_result(text):
            boost_set.add(i)
            reason_parts.append("tool_result")
        if entities and _entity_overlap(text, entities):
            boost_set.add(i)
            reason_parts.append("entity")

    selected_indices = sorted(boost_set | recency_set)

    # Cap aggressively if still too large
    if len(selected_indices) > max_selected:
        # Keep recency + most recent boosted
        boosted_sorted = sorted(boost_set, reverse=True)[: max_selected - recency_window]
        selected_indices = sorted(set(boosted_sorted) | recency_set)

    selected = [history[i] for i in selected_indices]
    dropped = total - len(selected)

    meta = {
        "history_total_turns": total,
        "history_selected_turns": len(selected),
        "history_dropped_turns": dropped,
        "history_selector_used": True,
        "history_selector_reason_summary": ", ".join(sorted(set(reason_parts))) or "recency_only",
    }
    return selected, meta
