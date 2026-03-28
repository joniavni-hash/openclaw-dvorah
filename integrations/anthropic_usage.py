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
SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"

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


def _parse_sessions_usage(date_str: str) -> Dict:
    """
    Parse today's token usage from OpenClaw session JSONL files.
    Returns aggregated usage dict.
    """
    total_input = total_output = 0
    total_cache_read = total_cache_write = 0
    total_cost = 0.0
    records = 0
    models_seen = set()

    for sf in SESSIONS_DIR.glob("*.jsonl"):
        if "deleted" in sf.name or "reset" in sf.name:
            continue
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

                    # If no cost in record, compute from pricing
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


def get_today_anthropic_usage() -> Dict:
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

    data = _parse_sessions_usage(date_str)

    if data["records"] > 0:
        source = "openclaw_session_logs"
    else:
        source = "no_data_found"

    return {
        "date": date_str,
        "input_tokens": data["input_tokens"],
        "output_tokens": data["output_tokens"],
        "cache_creation_tokens": data["cache_write_tokens"],
        "cache_read_tokens": data["cache_read_tokens"],
        "usd_cost": data["usd_cost"],
        "models": data["models"],
        "source": source,
        "calculated_at": calculated_at,
        "_records_parsed": data["records"],
    }


def format_usage_response(usage: Dict) -> str:
    """Format usage dict into user-facing compact response."""
    exact = usage["source"] == "openclaw_session_logs"
    label = "היום עד עכשיו:" if exact else "היום עד עכשיו (הערכה):"
    source_label = "OpenClaw session logs" if exact else usage["source"]

    cr = usage.get("cache_read_tokens", 0) or 0
    cw = usage.get("cache_creation_tokens", 0) or 0

    lines = [
        label,
        f"- input tokens: {usage['input_tokens']:,}",
        f"- output tokens: {usage['output_tokens']:,}",
    ]
    if cr or cw:
        lines.append(f"- cache write: {cw:,}")
        lines.append(f"- cache read: {cr:,}")
    lines += [
        f"- עלות: ${usage['usd_cost']:.4f}",
        f"- מקור: {source_label}",
        f"- חושב ב: {usage['calculated_at']}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    usage = get_today_anthropic_usage()
    print(format_usage_response(usage))
