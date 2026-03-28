#!/usr/bin/env python3
"""
Anthropic Usage Reporter — per INTEGRATIONS/anthropic_cost_reporter_spec.md

Sources (in priority order):
  1. OpenClaw session JSONL files (usage field per assistant message)
  2. Anthropic Admin/Usage API (if available — currently 404)

Usage:
  python3 integrations/anthropic_usage.py
  from integrations.anthropic_usage import get_today_anthropic_usage
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

WORKSPACE = Path(os.environ.get("DVORAH_WORKSPACE", Path.home() / ".openclaw" / "workspace"))
SESSIONS_DIR = Path.home() / ".openclaw" / "agents"   # scan ALL agents, not just main
AUTH_PROFILES = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"

ANTHROPIC_USAGE_API_ENDPOINTS = [
    # Admin API (requires sk-ant-admin03- key)
    "https://api.anthropic.com/v1/usage/daily",
    "https://api.anthropic.com/v1/usage",
    "https://api.anthropic.com/v1/organizations/usage",
]

# Official Anthropic pricing for models in use (per 1M tokens, as of 2026-03)
PRICING = {
    "claude-sonnet-4-6": {
        "input":        3.00 / 1_000_000,
        "output":      15.00 / 1_000_000,
        "cache_read":   0.30 / 1_000_000,
        "cache_write":  3.75 / 1_000_000,
    },
    "claude-opus-4-6": {
        "input":       15.00 / 1_000_000,
        "output":      75.00 / 1_000_000,
        "cache_read":   1.50 / 1_000_000,
        "cache_write": 18.75 / 1_000_000,
    },
    "claude-haiku-4-5": {
        "input":        0.80 / 1_000_000,
        "output":       4.00 / 1_000_000,
        "cache_read":   0.08 / 1_000_000,
        "cache_write":  1.00 / 1_000_000,
    },
}


def _try_anthropic_official_api(date_str: str) -> Optional[Dict]:
    """
    Attempt Anthropic official Usage/Admin API.
    Returns usage dict if successful, None otherwise.
    Requires sk-ant-admin03-... key with admin permissions.
    Regular sk-ant-api03-... keys return 404.
    """
    try:
        import requests
        profiles = json.loads(AUTH_PROFILES.read_text(encoding="utf-8"))
        api_key = (profiles.get("profiles", {})
                   .get("anthropic:default", {})
                   .get("key", ""))
        if not api_key:
            return None

        is_admin_key = "admin" in api_key[:20]
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

        for endpoint in ANTHROPIC_USAGE_API_ENDPOINTS:
            try:
                params = {"start_date": date_str, "end_date": date_str}
                r = requests.get(endpoint, headers=headers, params=params, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    # Parse usage from response
                    return {
                        "source": "anthropic_official_api",
                        "endpoint": endpoint,
                        "raw": data,
                        "is_admin_key": is_admin_key,
                    }
            except Exception:
                continue

        # All endpoints returned non-200 — document why
        return {
            "unavailable": True,
            "reason": (
                "admin_key_required" if not is_admin_key
                else "api_endpoint_not_found"
            ),
            "key_type": "admin" if is_admin_key else "regular_api_key",
            "detail": (
                "Anthropic Usage API requires sk-ant-admin03-... key with admin permissions. "
                "Current key is a regular API key (sk-ant-api03-...) which only has access to "
                "Messages/Models/Files APIs."
            ),
        }

    except Exception as e:
        return {"unavailable": True, "reason": str(e)}


def _parse_sessions_usage(date_str: str) -> Dict:
    """
    Fallback: parse token usage from ALL OpenClaw session JSONL files (all agents).
    NOTE: This captures only sessions tracked by this OpenClaw instance.
    May undercount vs Anthropic Console if some requests bypass session logging.
    """
    total_input = total_output = 0
    total_cache_read = total_cache_write = 0
    total_cost = 0.0
    records = 0
    models_seen = set()

    # Scan all agent session dirs, not just main
    for agent_dir in SESSIONS_DIR.iterdir():
        if not agent_dir.is_dir():
            continue
        sessions_path = agent_dir / "sessions"
        if not sessions_path.exists():
            sessions_path = agent_dir  # some agents store directly
        for sf in sessions_path.glob("*.jsonl"):
            try:
                for line in sf.read_text(encoding="utf-8").splitlines():
                    if not line.strip() or date_str not in line:
                        continue
                    try:
                        r = json.loads(line)
                        if r.get("type") != "message":
                            continue
                        msg = r.get("message", {})
                        if not isinstance(msg, dict) or msg.get("role") != "assistant":
                            continue
                        usage = msg.get("usage")
                        if not usage or not isinstance(usage, dict):
                            continue

                        inp = usage.get("input", 0)
                        out = usage.get("output", 0)
                        cr  = usage.get("cacheRead", 0)
                        cw  = usage.get("cacheWrite", 0)
                        cost_data = usage.get("cost", {})
                        cost = cost_data.get("total", 0.0) if isinstance(cost_data, dict) else 0.0

                        if not cost:
                            model = msg.get("model", "claude-sonnet-4-6")
                            prices = PRICING.get(model, PRICING["claude-sonnet-4-6"])
                            cost = (inp * prices["input"] + out * prices["output"] +
                                    cr * prices["cache_read"] + cw * prices["cache_write"])

                        model = msg.get("model", "claude-sonnet-4-6")
                        models_seen.add(model)
                        total_input       += inp
                        total_output      += out
                        total_cache_read  += cr
                        total_cache_write += cw
                        total_cost        += cost
                        records           += 1

                    except Exception:
                        pass
            except Exception:
                pass

    return {
        "records": records,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cache_read_tokens": total_cache_read,
        "cache_write_tokens": total_cache_write,
        "usd_cost": round(total_cost, 4),
        "models": sorted(models_seen),
    }


def get_today_anthropic_usage() -> Dict:  # noqa: C901
    """
    Returns today's token usage + cost.

    {
      "date": "YYYY-MM-DD",
      "input_tokens": int,
      "output_tokens": int,
      "cache_creation_tokens": int | None,
      "cache_read_tokens": int | None,
      "usd_cost": float,
      "source": str,
      "calculated_at": str,
    }
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    calculated_at = now.strftime("%Y-%m-%d %H:%M UTC")

    # 1. Try Anthropic official API first
    official = _try_anthropic_official_api(date_str)

    if official and not official.get("unavailable") and not official.get("raw") is None:
        # Parse official API response
        raw = official.get("raw", {})
        # Anthropic usage API response format varies — extract best-effort
        inp = raw.get("input_tokens", raw.get("usage", {}).get("input_tokens", 0))
        out = raw.get("output_tokens", raw.get("usage", {}).get("output_tokens", 0))
        cr  = raw.get("cache_read_input_tokens", 0)
        cw  = raw.get("cache_creation_input_tokens", 0)
        cost = raw.get("cost_usd", raw.get("total_cost", 0.0))
        return {
            "date": date_str,
            "input_tokens": inp,
            "output_tokens": out,
            "cache_creation_tokens": cw,
            "cache_read_tokens": cr,
            "usd_cost": round(float(cost), 4),
            "models": [],
            "source": "anthropic_official_api",
            "is_estimate": False,
            "calculated_at": calculated_at,
            "_records_parsed": 1,
        }

    # 2. Fallback to session logs — mark as estimate
    api_unavailable_reason = (official or {}).get("reason", "unknown")
    api_unavailable_detail = (official or {}).get("detail", "")

    data = _parse_sessions_usage(date_str)
    is_estimate = True
    source = "openclaw_session_logs + Anthropic pricing" if data["records"] > 0 else "no_data_found"

    return {
        "date": date_str,
        "input_tokens": data["input_tokens"],
        "output_tokens": data["output_tokens"],
        "cache_creation_tokens": data["cache_write_tokens"],
        "cache_read_tokens": data["cache_read_tokens"],
        "usd_cost": data["usd_cost"],
        "models": data["models"],
        "source": source,
        "is_estimate": is_estimate,
        "api_unavailable_reason": api_unavailable_reason,
        "api_unavailable_detail": api_unavailable_detail,
        "calculated_at": calculated_at,
        "_records_parsed": data["records"],
    }


def format_usage_response(usage: Dict) -> str:
    """Format usage dict into user-facing compact response per spec."""
    is_estimate = usage.get("is_estimate", True)
    label = "היום עד עכשיו (הערכה):" if is_estimate else "היום עד עכשיו:"

    cr = usage.get("cache_read_tokens", 0) or 0
    cw = usage.get("cache_creation_tokens", 0) or 0
    source = usage.get("source", "unknown")

    lines = [label,
             f"- input tokens: {usage['input_tokens']:,}",
             f"- output tokens: {usage['output_tokens']:,}",
             f"- cache write: {cw:,}",
             f"- cache read: {cr:,}",
             f"- עלות: ${usage['usd_cost']:.4f}",
             f"- מקור: {source}",
             f"- חושב ב: {usage['calculated_at']}"]

    if is_estimate and usage.get("api_unavailable_reason"):
        reason = usage["api_unavailable_reason"]
        if reason == "admin_key_required":
            lines.append("⚠️ Anthropic Usage API דורש Admin key — כרגע זמין רק מ-Anthropic Console")
        elif reason != "unknown":
            lines.append(f"⚠️ API לא זמין: {reason}")

    return "\n".join(lines)


if __name__ == "__main__":
    usage = get_today_anthropic_usage()
    print(format_usage_response(usage))
