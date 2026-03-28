#!/usr/bin/env python3
"""
output_sanitizer.py — DVORAH_OUTPUT_CONTRACT enforcement.

Contract (PROMPT_CONTRACTS/DVORAH_OUTPUT_CONTRACT.md):
  1. Single message only
  2. Short and direct (≤7 content lines for user-facing, ≤30 for analysis)
  3. No process narration
  4. Footer mandatory at send boundary
  5. Block and reshape if violated — never send raw violation

Called by action_executor.send_response_if_ready() on any text going to user.
"""

import re
from typing import Optional, Tuple

# ── Blocklist: internal content that must never reach users ───────────────────
_BLOCKLIST = [
    r"[a-z]+_[a-z]+_[a-z]+\(",
    r"\b_[a-z]+_[a-z]+\b",
    r"\bno_response_needed\b",
    r"\banalysis_ready\b",
    r"\bgroup_retrieval_response\b",
    r"\bpending_approval\b",
    r"\bdraft_completed\b",
    r"\bblocked_by_qa\b",
    r"\bdirect_response\b",
    r"\bHEAD:\s*[0-9a-f]{7,}\b",
    r"\bcommit\s+[0-9a-f]{7,}\b",
    r"\bexec_\d{8}_\d{6}_\d+\b",
    r"anthropic/claude-[\w\-\.]+",
    r"[a-z]+/[a-z_]+\.py",
    r"^.*\bimplementation note.*$",
    r"^.*\brouting.*internal.*$",
]

_PLACEHOLDER_REPLACEMENTS = {
    "Standard conversation handled": "",
    "Fitness message received (processing pending):": "✅",
    "Legal analysis queued for review": "⚖️ הניתוח המשפטי הושלם — ממתין לבדיקתך",
    "Research query processed": "🔍 בדיקה בתהליך",
}

# ── Process narration patterns — forbidden in user-facing output ──────────────
_PROCESS_SPAM_PATTERNS = [
    r'(?m)^עכשיו אני[^\n]*\n?',
    r'(?m)^הנה מה שמצאתי[^\n]*\n?',
    r'(?m)^בוא נבדוק[^\n]*\n?',
    r'(?m)^אני (בודק|בודקת|אעשה|מריץ|מריצה|טוען|טוענת|שולף|שולפת)[^\n]*\n?',
    r'(?m)^ממשיך ל[^\n]*\n?',
    r'(?m)^מריץ[^\n]*\n?',
    r'(?m)^בודק[^\n]*\n?',
    r'(?m)^טוען[^\n]*\n?',
    r'(?m)^שולף[^\n]*\n?',
    r'(?m)^כרגע אני[^\n]*\n?',
    r'(?m)^Now I\'m[^\n]*\n?',
    r'(?m)^Let me check[^\n]*\n?',
    r'(?m)^I\'m checking[^\n]*\n?',
    r'(?m)^Running[^\n]*\n?',
    r'(?m)^Loading[^\n]*\n?',
    r'(?m)^\*?\*?Diagnosis\*?\*?:?[^\n]*\n?',
    r'(?m)^\*?\*?Implementation\*?\*?:?[^\n]*\n?',
    r'(?m)^\*?\*?Proof\*?\*?:?[^\n]*\n?',
    r'(?m)^---+\s*\n',
]
_PROCESS_SPAM_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE)
                    for p in _PROCESS_SPAM_PATTERNS]

# ── Length limits ─────────────────────────────────────────────────────────────
MAX_CONTENT_LINES_DEFAULT  = 7    # user-facing short answers
MAX_CONTENT_LINES_ANALYSIS = 30   # fitness analysis, research, legal
MAX_CHARS_DEFAULT           = 3500
MAX_CHARS_ANALYSIS          = 5000

# ── Unexpected scripts ────────────────────────────────────────────────────────
_UNEXPECTED_SCRIPTS = [
    re.compile(r'[\u0400-\u04FF]{4,}'),
    re.compile(r'[\u4E00-\u9FFF]{4,}'),
    re.compile(r'[\u0900-\u097F]{4,}'),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split_footer(text: str) -> Tuple[str, str]:
    """Separate body from footer line(s)."""
    lines = text.split("\n")
    footer_lines, body_lines = [], []
    for line in lines:
        s = line.strip()
        if s.startswith("_") and s.endswith("_") and (" · " in s or "סוכנת:" in s):
            footer_lines.append(line)
        else:
            body_lines.append(line)
    return "\n".join(body_lines), "\n".join(footer_lines)


def _build_default_footer(agent: str = "דבורה", model: str = "sonnet",
                           status: str = "direct_send") -> str:
    return f"סוכנת: {agent} | מודל: {model} | מצב: {status}"


def _has_footer(text: str) -> bool:
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("_") and s.endswith("_") and " · " in s:
            return True
        if "סוכנת:" in s and "מודל:" in s:
            return True
    return False


def _has_process_spam(text: str) -> bool:
    for pattern in _PROCESS_SPAM_RE:
        if pattern.search(text):
            return True
    return False


def _count_content_lines(body: str) -> int:
    return sum(1 for l in body.split("\n") if l.strip())


# ── Core functions ────────────────────────────────────────────────────────────

def sanitize(text: str) -> str:
    """Strip internal content. Preserve footer."""
    if not text:
        return text
    body, footer = _split_footer(text)
    for placeholder, replacement in _PLACEHOLDER_REPLACEMENTS.items():
        body = body.replace(placeholder, replacement)
    cleaned_lines = []
    for line in body.split("\n"):
        skip = False
        for pattern in _BLOCKLIST:
            if re.search(pattern, line, re.IGNORECASE | re.MULTILINE):
                cleaned = re.sub(pattern, "", line, flags=re.IGNORECASE).strip()
                if not cleaned:
                    skip = True
                    break
                line = cleaned
        if not skip:
            cleaned_lines.append(line)
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned_lines)).strip()
    if footer and body:
        return body + "\n\n" + footer
    return footer if footer else body


def strip_process_spam(text: str) -> str:
    """Remove forbidden process narration patterns."""
    if not text:
        return text
    for pattern in _PROCESS_SPAM_RE:
        text = pattern.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def enforce_single_message(text: str, mode: str = "default") -> str:
    """
    Enforce single-message contract:
    - Truncate to char limit if over
    - Truncate to line limit if over (mode=default: 7 lines, analysis: 30)
    - Never split
    """
    if not text:
        return text
    body, footer = _split_footer(text)
    max_lines = MAX_CONTENT_LINES_ANALYSIS if mode == "analysis" else MAX_CONTENT_LINES_DEFAULT
    max_chars = MAX_CHARS_ANALYSIS if mode == "analysis" else MAX_CHARS_DEFAULT

    # Line limit
    content_lines = [l for l in body.split("\n") if l.strip()]
    if len(content_lines) > max_lines:
        body = "\n".join(content_lines[:max_lines])

    # Char limit
    if len(body) > max_chars:
        chunk = body[:max_chars]
        last_break = max(chunk.rfind(". "), chunk.rfind(".\n"),
                         chunk.rfind("? "), chunk.rfind("! "))
        if last_break > max_chars * 0.6:
            body = body[:last_break + 1]
        else:
            body = chunk.rstrip() + "..."

    result = body.rstrip()
    if footer:
        result = result + "\n\n" + footer
    return result


def ensure_footer(text: str, agent: str = "דבורה", model: str = "sonnet",
                  status: str = "direct_send") -> str:
    """Guarantee footer exists. If missing, append default footer."""
    if _has_footer(text):
        return text
    footer = _build_default_footer(agent, model, status)
    return text.rstrip() + "\n\n" + footer


def is_clean(text: str) -> bool:
    return sanitize(text) == text


def has_unexpected_language(text: str) -> bool:
    for pattern in _UNEXPECTED_SCRIPTS:
        if pattern.search(text):
            return True
    return False


# ── Contract enforcement: block-and-reshape ───────────────────────────────────

class ContractViolation(Exception):
    pass


def check_violations(text: str, mode: str = "default") -> list:
    """Return list of violation strings (empty = clean)."""
    violations = []
    body, footer = _split_footer(text)
    if _has_process_spam(text):
        violations.append("process_narration")
    if not _has_footer(text):
        violations.append("missing_footer")
    max_lines = MAX_CONTENT_LINES_ANALYSIS if mode == "analysis" else MAX_CONTENT_LINES_DEFAULT
    if _count_content_lines(body) > max_lines:
        violations.append(f"too_many_lines:{_count_content_lines(body)}>{max_lines}")
    if len(text) > (MAX_CHARS_ANALYSIS if mode == "analysis" else MAX_CHARS_DEFAULT):
        violations.append("too_long")
    return violations


def shape_final_response(text: str, mode: str = "default",
                          agent: str = "דבורה", model: str = "sonnet",
                          status: str = "direct_send") -> str:
    """
    Full output contract enforcement pipeline (DVORAH_OUTPUT_CONTRACT.md):
      1. Sanitize internal content
      2. Strip process spam
      3. Enforce single-message length + line count
      4. Guarantee footer (append if missing — never block on footer alone)
    Returns one clean, contract-compliant message.
    Raises ContractViolation only if text is empty after cleanup.
    """
    if not text:
        return text

    # 1. Sanitize
    text = sanitize(text)
    # 2. Strip process spam
    text = strip_process_spam(text)
    # 3. Length enforcement
    text = enforce_single_message(text, mode=mode)
    # 4. Footer guarantee
    text = ensure_footer(text, agent=agent, model=model, status=status)

    if not text.strip():
        raise ContractViolation("Empty response after enforcement")

    return text
