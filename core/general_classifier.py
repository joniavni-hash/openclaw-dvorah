"""
PR5 — General Intent Classifier

Deterministic, no-LLM classifier for the "general" domain.
Splits general into subtypes so cheap/deterministic paths can fire
before sending to tier2/Sonnet.

Subtypes (ordered by cheapness):
  acknowledgement   — "אוקי", "כן", "סבבה", "tnx", single-word acks
  confirmation      — "בוצע", "הבנתי", "מאשר", short confirmations
  casual_reply      — chit-chat, greetings
  short_followup    — follow-up to recent turn, ≤15 words
  clarification     — "מה זה X?", "הסבירי", simple question
  factual_state     — "מה השעה?", "כמה?", "מי?" — factual with known answer shape
  lightweight_planning — "אפשר ל...?", "בואי נ...", low-stakes planning
  complex_general   — requires broad reasoning → tier2
  unknown           — catch-all → tier2
"""

import re
from typing import Any

# ── Subtype → tier mapping ────────────────────────────────────────────────────

SUBTYPE_TIER = {
    "acknowledgement":      "tier1_or_skip",  # maybe even skip
    "confirmation":         "tier1",
    "casual_reply":         "tier1",
    "short_followup":       "tier1",
    "clarification":        "tier1",
    "factual_state":        "tier1",
    "lightweight_planning": "tier1",
    "complex_general":      "tier2",
    "unknown":              "tier2",
}

# tier1_or_skip means: if message is pure ack → deterministic empty/short reply
# else → tier1

CHEAP_SUBTYPES = {k for k, v in SUBTYPE_TIER.items() if v in ("tier1", "tier1_or_skip")}

# ── History window per subtype ────────────────────────────────────────────────
# Smaller = less payload = cheaper

SUBTYPE_HISTORY_WINDOW = {
    "acknowledgement":      3,
    "confirmation":         5,
    "casual_reply":         5,
    "short_followup":       8,
    "clarification":        10,
    "factual_state":        8,
    "lightweight_planning": 10,
    "complex_general":      12,
    "unknown":              12,
}

# ── Pattern sets ──────────────────────────────────────────────────────────────

_ACK_PATTERNS = [
    r"^(אוקי|אוקיי|ok|okay|tnx|תודה|סבבה|קול|נהדר|מעולה|מצוין|perfect|great|nice|👍|✅|🙏|💪)\.?$",
    r"^(כן|לא|נכון|ברור|בטח|sure|yep|nope|yeah|no)\.?$",
    r"^(wow|וואו|יפה|אחלה)\.?$",
    r"^[\U0001F300-\U0001FFFF\s]{1,3}$",  # 1-3 emojis
    r"^.{1,4}$",  # very short
]

_CONFIRMATION_PATTERNS = [
    r"^(בוצע|הבנתי|מאשר|מאשרת|confirmed|done|got\s*it|received)[\.,!]?$",
    r"(הבנתי|קיבלתי|נרשם|נשמר|ראיתי|ביצעתי)",
    r"^(תודה|thanks?)[\s\.,!]*$",
]

_CASUAL_PATTERNS = [
    r"^(שלום|היי|הי|hello|hey|boker\s*tov|בוקר\s*טוב|ערב\s*טוב|לילה\s*טוב)[\s\.,!]*$",
    r"^(מה\s*(שלומך|נשמע|קורה|חדש)|how\s*(are|r)\s*(you|u))[\s\?]*$",
    r"^(מה\s*המצב)[\s\?]*$",
]

_FACTUAL_PATTERNS = [
    r"^מה\s+(השעה|התאריך|היום|התוצאה)\s*[\?]?$",
    r"^כמה\s+(שעות|ימים|זה|עולה)\s*[\?]?$",
    r"^מי\s+(זה|הוא|היא)\s+\w+[\?]?$",
    r"^(מה|איפה|מתי|כמה)\s+\w{1,10}\s*[\?]?$",
]

_CLARIFICATION_PATTERNS = [
    r"^מה\s+(זה|הוא|היא|אתה\s*מתכוון|כוונתך)\s*[\?]?$",
    r"(הסבירי|הסביר|explain|clarify|פרטי|פרטים)\s",
    r"^(לא\s*הבנתי|לא\s*ברור|מה\s*התכוונת|תוכל\s*להסביר)[\?\.]?$",
    r"^(מה\s*הכוונה|what\s*do\s*you\s*mean)[\?\.]?$",
]

_PLANNING_PATTERNS = [
    r"^(אפשר|יכול|אולי|בואי|בוא)\s+(ל|נ)",
    r"^(רוצה\s+(ל|ש)|want\s+to)\s+\w{3,20}",
    r"(תכנן|לתכנן|plan|נסדר|לסדר)\s+\w{3,20}",
    r"^(מה\s+אם|מה\s+לגבי|what\s+about|what\s+if)\s",
]

_COMPLEX_INDICATORS = [
    r"(נתח|נתחי|analyze|ניתוח|analysis)",
    r"(השוואה|compare|compared)",
    r"(סכמי|summarize|summary)",
    r"(כתבי|write|draft|compose)\s+\w{5,}",
    r"(מה\s+דעתך\s+על|מה\s+הדעה)",
    r"(תחקרי|investigate|research)\s",
    r"\b(strategy|אסטרטגיה|strategic)\b",
    r"\b(complex|מורכב|complicated)\b",
]


def _match_any(text: str, patterns: list[str]) -> bool:
    t = text.strip()
    return any(re.search(p, t, re.IGNORECASE | re.UNICODE) for p in patterns)


def _word_count(text: str) -> int:
    return len(text.split())


def classify_general(message: str, history_length: int = 0) -> dict[str, Any]:
    """
    Classify a general-domain message into a subtype.

    Returns:
        subtype        — string subtype
        recommended_tier — tier1 / tier2
        history_window — how many history turns to include
        reason         — brief justification
        is_cheap       — bool shortcut
    """
    msg = message.strip()
    wc = _word_count(msg)

    # 1. Acknowledgement (cheapest)
    if _match_any(msg, _ACK_PATTERNS) or wc <= 2:
        return _result("acknowledgement", "single-word/emoji ack")

    # 2. Confirmation
    if _match_any(msg, _CONFIRMATION_PATTERNS) and wc <= 8:
        return _result("confirmation", "short confirmation phrase")

    # 3. Casual
    if _match_any(msg, _CASUAL_PATTERNS):
        return _result("casual_reply", "greeting/chit-chat")

    # 4. Factual state
    if _match_any(msg, _FACTUAL_PATTERNS) and wc <= 10:
        return _result("factual_state", "short factual question")

    # 5. Clarification
    if _match_any(msg, _CLARIFICATION_PATTERNS) and wc <= 15:
        return _result("clarification", "simple clarification request")

    # 6. Short follow-up (≤15 words, no complex indicators)
    if wc <= 15 and not _match_any(msg, _COMPLEX_INDICATORS):
        if history_length > 0:
            return _result("short_followup", f"short follow-up ({wc} words)")

    # 7. Lightweight planning
    if _match_any(msg, _PLANNING_PATTERNS) and wc <= 20:
        return _result("lightweight_planning", "simple planning intent")

    # 8. Complex — needs tier2
    if _match_any(msg, _COMPLEX_INDICATORS):
        return _result("complex_general", "complex reasoning required")

    # 9. Unknown — tier2 by default
    return _result("unknown", f"no pattern matched, wc={wc}")


def _result(subtype: str, reason: str) -> dict[str, Any]:
    tier_raw = SUBTYPE_TIER[subtype]
    tier = "tier1" if tier_raw == "tier1_or_skip" else tier_raw
    return {
        "subtype": subtype,
        "recommended_tier": tier,
        "history_window": SUBTYPE_HISTORY_WINDOW[subtype],
        "reason": reason,
        "is_cheap": subtype in CHEAP_SUBTYPES,
    }
