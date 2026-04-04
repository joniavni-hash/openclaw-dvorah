"""
PR4 — Real Per-Request Cost Telemetry

Writes a structured trace record for every request.
Daily file: workspace/state/traces/cost_YYYY-MM-DD.jsonl
Also produces daily rollup on demand.

Fields per record:
  agent, domain, model, recommended_tier, final_tier,
  input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
  usd_cost, deterministic_path, model_call_skipped,
  history_selected_turns, context_chars, escalation_reason
"""

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Anthropic pricing (per 1M tokens, USD) — sonnet-4-6 / haiku-4 / opus-4-6
PRICING = {
    "anthropic/claude-sonnet-4-6":     {"input": 3.0,  "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "anthropic/claude-haiku-4":        {"input": 0.8,  "output": 4.0,  "cache_read": 0.08, "cache_write": 1.0},
    "anthropic/claude-opus-4-6":       {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75},
    "anthropic/claude-haiku-4-20250514": {"input": 0.8,  "output": 4.0,  "cache_read": 0.08, "cache_write": 1.0},
    "anthropic/claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "anthropic/claude-opus-4-20250514":  {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75},
    "none": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0},
}

_WORKSPACE = Path(os.environ.get("DVORAH_WORKSPACE", Path.home() / ".openclaw" / "workspace"))
_TRACES_DIR = _WORKSPACE / "state" / "traces"


def _cost_file() -> Path:
    return _TRACES_DIR / f"cost_{date.today().isoformat()}.jsonl"


def _calc_usd(model: str, input_t: int, output_t: int,
              cache_read_t: int = 0, cache_write_t: int = 0) -> float:
    p = PRICING.get(model, PRICING["none"])
    M = 1_000_000
    return (
        input_t      * p["input"]       / M +
        output_t     * p["output"]      / M +
        cache_read_t * p["cache_read"]  / M +
        cache_write_t * p["cache_write"] / M
    )


def record(
    *,
    execution_id: str,
    agent: str,
    domain: str,
    model: str,
    recommended_tier: str,
    final_tier: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    deterministic_path: bool = False,
    model_call_skipped: bool = False,
    history_selected_turns: int = 0,
    context_chars: int = 0,
    escalation_reason: str = "",
    handler_name: str = "",
    source_of_truth: str = "",
) -> dict[str, Any]:
    """
    Write one cost trace record to daily JSONL.
    Returns the record dict (for embedding in execution trace).
    """
    usd = 0.0 if model_call_skipped else _calc_usd(
        model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens
    )

    entry = {
        "ts": datetime.now().isoformat(),
        "execution_id": execution_id,
        "agent": agent,
        "domain": domain,
        "model": model,
        "recommended_tier": recommended_tier,
        "final_tier": final_tier,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "usd_cost": round(usd, 6),
        "deterministic_path": deterministic_path,
        "model_call_skipped": model_call_skipped,
        "history_selected_turns": history_selected_turns,
        "context_chars": context_chars,
        "escalation_reason": escalation_reason,
        "handler_name": handler_name,
        "source_of_truth": source_of_truth,
    }

    _TRACES_DIR.mkdir(parents=True, exist_ok=True)
    with _cost_file().open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entry


def daily_rollup(target_date: str | None = None) -> dict[str, Any]:
    """
    Compute rollup for a given date (default: today).
    Returns totals by domain, agent, model, and deterministic vs model path.
    """
    d = target_date or date.today().isoformat()
    path = _TRACES_DIR / f"cost_{d}.jsonl"
    if not path.exists():
        return {"date": d, "records": 0, "total_usd": 0.0, "by_domain": {}, "by_agent": {}, "by_model": {}, "by_path": {}}

    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass

    def _agg(key_fn):
        result: dict[str, dict] = {}
        for r in records:
            k = key_fn(r)
            if k not in result:
                result[k] = {"calls": 0, "usd": 0.0, "model_calls": 0, "det_calls": 0}
            result[k]["calls"] += 1
            result[k]["usd"] = round(result[k]["usd"] + r.get("usd_cost", 0), 6)
            if r.get("model_call_skipped"):
                result[k]["det_calls"] += 1
            else:
                result[k]["model_calls"] += 1
        return result

    return {
        "date": d,
        "records": len(records),
        "total_usd": round(sum(r.get("usd_cost", 0) for r in records), 6),
        "by_domain": _agg(lambda r: r.get("domain", "?")),
        "by_agent":  _agg(lambda r: r.get("agent", "?")),
        "by_model":  _agg(lambda r: r.get("model", "?")),
        "by_path":   _agg(lambda r: "deterministic" if r.get("model_call_skipped") else "model"),
    }
