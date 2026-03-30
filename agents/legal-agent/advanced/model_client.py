#!/usr/bin/env python3
"""
Model Client — Direct Anthropic API client for Masha Advanced.
Reads auth from OpenClaw's auth-profiles.json. No SDK dependency — uses requests.

Handles:
- Tier 1/2 (Sonnet) and Tier 3 (Opus) calls
- Prompt caching for system prompts (reduces input cost by up to 90%)
- Retry with exponential backoff
- Token counting from actual API responses
- Cost tracking integration
"""

import json
import os
import time
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path

import requests

logger = logging.getLogger("masha.model_client")

# ============================================================
# CONFIG
# ============================================================

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

# Model identifiers — updated to latest versions
# Tier 3 changed from Opus to Sonnet 4-6 (5x cheaper, sufficient for legal tasks)
# Set OPENCLAW_USE_OPUS=1 env var to re-enable Opus for Tier 3 when truly needed
TIER_MODELS = {
    "tier1": "claude-sonnet-4-6",
    "tier2": "claude-sonnet-4-6",  # Same model, different prompting
    "tier3": os.environ.get("OPENCLAW_TIER3_MODEL", "claude-sonnet-4-6"),
}

# Cost per 1M tokens (input, output, cache_write, cache_read) in USD
TIER_COSTS_PER_1M = {
    "tier1": (3.0, 15.0),
    "tier2": (3.0, 15.0),
    "tier3": (3.0, 15.0),  # Default is now Sonnet pricing
}

# Opus pricing reference (for when OPENCLAW_TIER3_MODEL is set to Opus)
OPUS_COSTS_PER_1M = (15.0, 75.0)

# Max tokens per tier
TIER_MAX_TOKENS = {
    "tier1": 4096,
    "tier2": 8192,
    "tier3": 8192,
}

# Retry config
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_BACKOFF = 2.0


# ============================================================
# AUTH LOADING
# ============================================================

def _load_api_key() -> str:
    """Load Anthropic API key from OpenClaw auth-profiles.json."""
    auth_paths = [
        Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json",
        Path.home() / ".openclaw" / "auth-profiles.json",
    ]

    for path in auth_paths:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            # Handle list format
            if isinstance(data, list):
                data = data[0]
            profiles = data.get("profiles", {})
            anthro = profiles.get("anthropic:default", {})
            key = anthro.get("key", "")
            if key.startswith("sk-ant"):
                return key
        except (json.JSONDecodeError, KeyError, IndexError):
            continue

    # Fallback: env var
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key

    raise RuntimeError(
        "No Anthropic API key found. Check ~/.openclaw/agents/main/agent/auth-profiles.json"
    )


# Lazy-load key
_api_key: Optional[str] = None


def _get_api_key() -> str:
    global _api_key
    if _api_key is None:
        _api_key = _load_api_key()
    return _api_key


# ============================================================
# API CALL
# ============================================================

class ModelResponse:
    """Parsed response from Anthropic API."""

    def __init__(self, raw: Dict):
        self.raw = raw
        self.content = self._extract_content()
        usage = raw.get("usage", {})
        self.input_tokens = usage.get("input_tokens", 0)
        self.output_tokens = usage.get("output_tokens", 0)
        self.cache_creation_input_tokens = usage.get("cache_creation_input_tokens", 0)
        self.cache_read_input_tokens = usage.get("cache_read_input_tokens", 0)
        self.stop_reason = raw.get("stop_reason", "unknown")
        self.model = raw.get("model", "unknown")

    def _extract_content(self) -> str:
        content_blocks = self.raw.get("content", [])
        parts = []
        for block in content_blocks:
            if block.get("type") == "text":
                parts.append(block["text"])
        return "\n".join(parts)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def cost_usd(self, tier: str) -> float:
        costs = TIER_COSTS_PER_1M.get(tier, TIER_COSTS_PER_1M["tier2"])
        return (
            (self.input_tokens / 1_000_000) * costs[0]
            + (self.output_tokens / 1_000_000) * costs[1]
        )

    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "total_tokens": self.total_tokens,
            "stop_reason": self.stop_reason,
            "model": self.model,
        }


def call_model(
    tier: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: Optional[int] = None,
    temperature: float = 0.2,
    thinking: bool = False,
) -> ModelResponse:
    """
    Call the Anthropic API for a specific tier.

    Args:
        tier: "tier1", "tier2", or "tier3"
        system_prompt: System message
        user_prompt: User message
        max_tokens: Override max tokens (default per tier)
        temperature: Model temperature (lower = more deterministic)
        thinking: Enable extended thinking (Tier 2/3 only, adds CoT)

    Returns:
        ModelResponse with content and token counts

    Raises:
        ModelCallError on persistent failure after retries
    """
    model = TIER_MODELS.get(tier, TIER_MODELS["tier2"])
    if max_tokens is None:
        max_tokens = TIER_MAX_TOKENS.get(tier, 4096)

    headers = {
        "x-api-key": _get_api_key(),
        "anthropic-version": ANTHROPIC_API_VERSION,
        "content-type": "application/json",
    }

    # Use structured system prompt with cache_control to enable prompt caching.
    # The system prompt (policies, checklists, tier prompts) is the same across
    # many calls. Caching it means subsequent calls pay only ~10% of input cost
    # for the cached portion (cache_read vs full input pricing).
    system_with_cache = [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_with_cache,
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
    }

    # Tier 2 uses chain-of-thought via extended thinking or explicit CoT prompt
    if tier == "tier2" and thinking:
        # Extended thinking not available in all API versions
        # Fallback: we prepend CoT instruction in the system prompt
        pass  # CoT is built into tier2 prompts already

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                ANTHROPIC_API_URL,
                headers=headers,
                json=payload,
                timeout=120,
            )

            if resp.status_code == 200:
                return ModelResponse(resp.json())

            if resp.status_code == 429:
                # Rate limited — respect Retry-After
                retry_after = int(resp.headers.get("retry-after", RETRY_BASE_DELAY * (RETRY_BACKOFF ** attempt)))
                logger.warning(f"Rate limited (429). Waiting {retry_after}s (attempt {attempt+1}/{MAX_RETRIES})")
                time.sleep(retry_after)
                last_error = f"Rate limited: {resp.text[:200]}"
                continue

            if resp.status_code >= 500:
                # Server error — retry
                delay = RETRY_BASE_DELAY * (RETRY_BACKOFF ** attempt)
                logger.warning(f"Server error {resp.status_code}. Waiting {delay}s (attempt {attempt+1}/{MAX_RETRIES})")
                time.sleep(delay)
                last_error = f"Server error {resp.status_code}: {resp.text[:200]}"
                continue

            # Client error — don't retry
            raise ModelCallError(
                f"API error {resp.status_code}: {resp.text[:500]}",
                status_code=resp.status_code,
                tier=tier,
            )

        except requests.exceptions.Timeout:
            delay = RETRY_BASE_DELAY * (RETRY_BACKOFF ** attempt)
            logger.warning(f"Timeout. Waiting {delay}s (attempt {attempt+1}/{MAX_RETRIES})")
            time.sleep(delay)
            last_error = "Request timeout"

        except requests.exceptions.ConnectionError as e:
            delay = RETRY_BASE_DELAY * (RETRY_BACKOFF ** attempt)
            logger.warning(f"Connection error. Waiting {delay}s (attempt {attempt+1}/{MAX_RETRIES})")
            time.sleep(delay)
            last_error = f"Connection error: {e}"

    raise ModelCallError(
        f"Failed after {MAX_RETRIES} retries: {last_error}",
        tier=tier,
    )


class ModelCallError(Exception):
    """Error from model API call."""

    def __init__(self, message: str, status_code: int = 0, tier: str = "unknown"):
        super().__init__(message)
        self.status_code = status_code
        self.tier = tier


# ============================================================
# HIGH-LEVEL HELPERS
# ============================================================

def call_tier1(system: str, user: str, max_tokens: int = 4096) -> ModelResponse:
    """Quick helper for Tier 1 (Sonnet) calls."""
    return call_model("tier1", system, user, max_tokens=max_tokens, temperature=0.1)


def call_tier2(system: str, user: str, max_tokens: int = 8192) -> ModelResponse:
    """Quick helper for Tier 2 (Sonnet + CoT) calls."""
    return call_model("tier2", system, user, max_tokens=max_tokens, temperature=0.3)


def call_tier3(system: str, user: str, max_tokens: int = 8192) -> ModelResponse:
    """Quick helper for Tier 3 (Opus) calls."""
    return call_model("tier3", system, user, max_tokens=max_tokens, temperature=0.3)


def call_for_tier(tier: str, system: str, user: str, max_tokens: Optional[int] = None) -> ModelResponse:
    """Route to the right helper based on tier string."""
    if tier == "tier1":
        return call_tier1(system, user, max_tokens=max_tokens or 4096)
    elif tier == "tier2":
        return call_tier2(system, user, max_tokens=max_tokens or 8192)
    elif tier == "tier3":
        return call_tier3(system, user, max_tokens=max_tokens or 8192)
    else:
        return call_tier1(system, user, max_tokens=max_tokens or 4096)


# ============================================================
# JSON EXTRACTION HELPER
# ============================================================

def extract_json(text: str) -> Optional[Dict]:
    """Extract JSON from model response text, handling markdown code blocks."""
    import re

    # Try direct parse
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code block
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } or [ ... ]
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break

    return None


# ============================================================
# TEST
# ============================================================

def test_model_client():
    """Quick connectivity test."""
    print("Testing Masha Model Client...")
    print(f"API key loaded: {'yes' if _get_api_key()[:8] else 'no'}")

    # Tier 1 test
    print("\n--- Tier 1 (Sonnet) Test ---")
    try:
        resp = call_tier1(
            system="You are a legal assistant. Respond briefly in JSON.",
            user='Classify this request: "\u05ea\u05e1\u05db\u05de\u05d9 \u05d0\u05ea \u05d4\u05d7\u05d5\u05d6\u05d4". Return {"task_type": "...", "confidence": 0.0-1.0}',
            max_tokens=200,
        )
        print(f"  Content: {resp.content[:200]}")
        print(f"  Tokens: {resp.input_tokens} in / {resp.output_tokens} out")
        print(f"  Cost: ${resp.cost_usd('tier1'):.4f}")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\nModel client ready.")


if __name__ == "__main__":
    test_model_client()
