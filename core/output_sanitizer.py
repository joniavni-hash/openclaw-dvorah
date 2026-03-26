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
