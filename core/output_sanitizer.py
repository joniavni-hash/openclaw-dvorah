#!/usr/bin/env python3
"""
output_sanitizer.py — Strip internal technical content before sending to user.

Called by action_executor.send_response_if_ready() on any text going to WhatsApp/DM.
Never touches the transparency footer (lines containing ' · ').
"""

import re
from typing import Optional

# Patterns that indicate internal/debug content
_BLOCKLIST = [
    # Python identifiers / function calls
    r"[a-z]+_[a-z]+_[a-z]+\(",     # snake_case function calls (3+ segments)
    r"\b_[a-z]+_[a-z]+\b",         # _private_methods
    # Status enum values
    r"\bno_response_needed\b",
    r"\banalysis_ready\b",
    r"\bgroup_retrieval_response\b",
    r"\bpending_approval\b",
    r"\bdraft_completed\b",
    r"\bblocked_by_qa\b",
    r"\bdirect_response\b",
    # Git artifacts
    r"\bHEAD:\s*[0-9a-f]{7,}\b",
    r"\bcommit\s+[0-9a-f]{7,}\b",
    r"\bexec_\d{8}_\d{6}_\d+\b",
    # Model IDs
    r"anthropic/claude-[\w\-\.]+",
    # File paths
    r"[a-z]+/[a-z_]+\.py",
    # Routing/impl notes (lines only)
    r"^.*\bimplementation note.*$",
    r"^.*\brouting.*internal.*$",
]

# Placeholder texts that should not reach users — replace with empty
_PLACEHOLDER_REPLACEMENTS = {
    "Standard conversation handled": "",
    "Fitness message received (processing pending):": "✅",
    "Legal analysis queued for review": "⚖️ הניתוח המשפטי הושלם — ממתין לבדיקתך",
    "Research query processed": "🔍 בדיקה בתהליך",
}


def sanitize(text: str) -> str:
    """
    Clean user-facing text:
    - Replace known placeholders
    - Strip lines with internal identifiers
    - Preserve footer (lines with ' · ')
    - Return stripped result
    """
    if not text:
        return text

    # Separate footer from body
    lines = text.split("\n")
    footer_lines = []
    body_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("_") and stripped.endswith("_") and " · " in stripped:
            footer_lines.append(line)
        else:
            body_lines.append(line)

    body = "\n".join(body_lines)

    # Apply placeholder replacements
    for placeholder, replacement in _PLACEHOLDER_REPLACEMENTS.items():
        body = body.replace(placeholder, replacement)

    # Apply blocklist patterns (line-by-line for line patterns, global for inline)
    cleaned_lines = []
    for line in body.split("\n"):
        skip = False
        for pattern in _BLOCKLIST:
            if re.search(pattern, line, re.IGNORECASE | re.MULTILINE):
                # If the whole line is internal, drop it
                # If it's partial, strip the match
                cleaned = re.sub(pattern, "", line, flags=re.IGNORECASE).strip()
                if not cleaned:
                    skip = True
                    break
                line = cleaned
        if not skip:
            cleaned_lines.append(line)

    body = "\n".join(cleaned_lines).strip()

    # Collapse multiple blank lines
    body = re.sub(r"\n{3,}", "\n\n", body)

    # Rejoin with footer
    if footer_lines and body:
        return body + "\n\n" + "\n".join(footer_lines)
    elif footer_lines:
        return "\n".join(footer_lines)
    return body


def is_clean(text: str) -> bool:
    """Returns True if text passes sanitization unchanged."""
    return sanitize(text) == text


# Cyrillic / other unexpected scripts — flag if primary content is not Hebrew/Latin/Arabic numerals
_UNEXPECTED_SCRIPTS = [
    re.compile(r'[\u0400-\u04FF]{4,}'),   # Cyrillic
    re.compile(r'[\u4E00-\u9FFF]{4,}'),   # CJK
    re.compile(r'[\u0900-\u097F]{4,}'),   # Devanagari
]

def has_unexpected_language(text: str) -> bool:
    """Returns True if text contains unexpected non-Hebrew/non-Latin script blocks."""
    for pattern in _UNEXPECTED_SCRIPTS:
        if pattern.search(text):
            return True
    return False


# ── Single-message enforcement ────────────────────────────────────────────────

MAX_CHARS_DEFAULT = 3500   # Stay under 4000-char WhatsApp chunk limit
MAX_CHARS_ANALYSIS = 5000  # For analysis/research/legal — still single chunk if possible

def enforce_single_message(text: str, mode: str = "default") -> str:
    """
    Enforce single-message output discipline.

    - If text is within limit: return as-is.
    - If over limit: truncate to last sentence boundary + add truncation note.
    - Never splits into multiple messages — caller gets ONE string.
    - mode: "default" (3500 chars) | "analysis" (5000 chars)
    """
    if not text:
        return text

    limit = MAX_CHARS_ANALYSIS if mode == "analysis" else MAX_CHARS_DEFAULT

    if len(text) <= limit:
        return text

    # Separate footer before truncating
    lines = text.split("\n")
    footer = ""
    body_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("_") and stripped.endswith("_") and " · " in stripped:
            footer = line
        else:
            body_lines.append(line)

    body = "\n".join(body_lines)

    # Truncate to limit minus room for note + footer
    reserve = len(footer) + 60
    truncate_at = limit - reserve

    if len(body) <= truncate_at:
        truncated = body
    else:
        # Find last sentence boundary before truncate_at
        chunk = body[:truncate_at]
        last_period = max(chunk.rfind(". "), chunk.rfind(".\n"), chunk.rfind("? "), chunk.rfind("! "))
        if last_period > truncate_at * 0.6:
            truncated = body[:last_period + 1]
        else:
            truncated = chunk.rstrip() + "..."

    result = truncated.rstrip()
    if footer:
        result = result + "\n\n" + footer
    return result


# ── Process spam filter ───────────────────────────────────────────────────────

import re as _re

_PROCESS_SPAM_PATTERNS = [
    # Hebrew process narration
    r'^עכשיו אני[^\n]*\n?',
    r'^הנה מה שמצאתי[^\n]*\n?',
    r'^בוא נבדוק[^\n]*\n?',
    r'^אני אעשה[^\n]*\n?',
    r'^ממשיך ל[^\n]*\n?',
    r'^מריץ[^\n]*\n?',
    r'^בודק[^\n]*\n?',
    r'^טוען[^\n]*\n?',
    r'^שולף[^\n]*\n?',
    r'^כרגע אני[^\n]*\n?',
    # English process narration
    r'(?m)^Now I\'m[^\n]*\n?',
    r'(?m)^Let me check[^\n]*\n?',
    r'(?m)^I\'m checking[^\n]*\n?',
    r'(?m)^Running[^\n]*\n?',
    r'(?m)^Loading[^\n]*\n?',
    # Stage headers that are process not answer
    r'(?m)^\*?Diagnosis\*?:[^\n]*\n?',
    r'(?m)^\*?Implementation\*?:[^\n]*\n?',
    r'(?m)^\*?Proof\*?:[^\n]*\n?',
    r'(?m)^---+\s*\n',
]

_PROCESS_SPAM_COMPILED = [_re.compile(p, _re.IGNORECASE | _re.MULTILINE)
                           for p in _PROCESS_SPAM_PATTERNS]


def strip_process_spam(text: str) -> str:
    """Remove process narration patterns from user-facing text."""
    if not text:
        return text
    for pattern in _PROCESS_SPAM_COMPILED:
        text = pattern.sub('', text)
    # Collapse 3+ blank lines
    text = _re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def shape_final_response(text: str, mode: str = "default") -> str:
    """
    Full output contract enforcement pipeline:
    1. Sanitize internal content
    2. Strip process spam
    3. Enforce single-message length
    Returns one clean, direct message.

    mode: "default" | "group" | "analysis"
    """
    if not text:
        return text
    text = sanitize(text)
    text = strip_process_spam(text)
    text = enforce_single_message(text, mode="analysis" if mode == "analysis" else "default")
    return text
