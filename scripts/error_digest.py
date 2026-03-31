#!/usr/bin/env python3
"""
Error Digest — Aggregates execution traces and reports failures.

Usage:
    python3 scripts/error_digest.py                   # Today's digest
    python3 scripts/error_digest.py --date 2026-03-30 # Specific date
    python3 scripts/error_digest.py --week             # Last 7 days
    python3 scripts/error_digest.py --json             # Machine-readable output

Reads from: state/traces/execution_YYYY-MM-DD.jsonl
Output: summary of errors, invariant violations, agent failures, slow requests.
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

WORKSPACE = Path(os.environ.get("DVORAH_WORKSPACE", Path.home() / ".openclaw" / "workspace"))
TRACES_DIR = WORKSPACE / "state" / "traces"
DIGEST_OUTPUT = WORKSPACE / "state" / "error_digest_latest.json"

# Thresholds
SLOW_REQUEST_MS = 5000  # >5s is slow
ERROR_STATUSES = {"error", "invariant_violation", "blocked_by_qa"}
WARNING_STATUSES = {"pending_approval", "fallback_to_direct"}


def load_traces(target_date: date) -> List[Dict]:
    """Load trace entries for a specific date."""
    entries = []
    # Try both naming patterns
    patterns = [
        TRACES_DIR / f"execution_{target_date.isoformat()}.jsonl",
        TRACES_DIR / f"{target_date.isoformat()}.jsonl",
    ]
    for path in patterns:
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass
    return entries


def analyze_traces(entries: List[Dict]) -> Dict:
    """Analyze trace entries and return digest."""
    if not entries:
        return {"status": "no_data", "message": "No trace entries found"}

    total = len(entries)
    errors = []
    warnings = []
    slow_requests = []
    agent_counts = Counter()
    domain_counts = Counter()
    agent_errors = defaultdict(list)
    invariant_violations = []
    qa_failures = []

    for entry in entries:
        status = entry.get("status", entry.get("agent_response", "unknown"))
        domain = entry.get("classified_domain", "unknown")
        agent = entry.get("expected_agent") or entry.get("routing", {}).get("agent", "direct")
        duration = entry.get("duration_ms", 0)
        exec_id = entry.get("execution_id", "?")
        msg = entry.get("message", "")[:80]

        agent_counts[agent or "direct"] += 1
        domain_counts[domain] += 1

        # Errors
        if status in ERROR_STATUSES:
            error_info = {
                "execution_id": exec_id,
                "status": status,
                "domain": domain,
                "agent": agent,
                "message": msg,
                "error": entry.get("error", ""),
            }
            errors.append(error_info)

            if status == "invariant_violation":
                invariant_violations.append(error_info)

        # Warnings
        if status in WARNING_STATUSES:
            warnings.append({
                "execution_id": exec_id,
                "status": status,
                "domain": domain,
                "agent": agent,
                "message": msg,
            })

        # QA failures
        if not entry.get("qa_passed", True):
            qa_failures.append({
                "execution_id": exec_id,
                "domain": domain,
                "agent": agent,
                "message": msg,
            })

        # Agent-level errors (from metadata)
        agent_meta = entry.get("metadata", {}) if isinstance(entry.get("metadata"), dict) else {}
        if "error" in str(agent_meta):
            agent_errors[agent or "direct"].append({
                "execution_id": exec_id,
                "error": str(agent_meta.get("error", "")),
            })

        # Slow requests
        if duration > SLOW_REQUEST_MS:
            slow_requests.append({
                "execution_id": exec_id,
                "duration_ms": duration,
                "domain": domain,
                "agent": agent,
                "message": msg,
            })

    # Compute stats
    error_rate = len(errors) / total if total > 0 else 0
    qa_fail_rate = len(qa_failures) / total if total > 0 else 0
    avg_duration = sum(e.get("duration_ms", 0) for e in entries) / total if total else 0

    # Agent health summary
    agent_health = {}
    for agent_name in agent_counts:
        agent_entries = [e for e in entries
                        if (e.get("expected_agent") or e.get("routing", {}).get("agent", "direct")) == agent_name]
        agent_total = len(agent_entries)
        agent_err = len([e for e in agent_entries if e.get("status") in ERROR_STATUSES])
        agent_health[agent_name] = {
            "total": agent_total,
            "errors": agent_err,
            "health": "healthy" if agent_err == 0 else ("degraded" if agent_err / max(agent_total, 1) < 0.3 else "failing"),
        }

    return {
        "status": "ok",
        "summary": {
            "total_requests": total,
            "errors": len(errors),
            "warnings": len(warnings),
            "qa_failures": len(qa_failures),
            "invariant_violations": len(invariant_violations),
            "slow_requests": len(slow_requests),
            "error_rate": round(error_rate, 4),
            "qa_fail_rate": round(qa_fail_rate, 4),
            "avg_duration_ms": round(avg_duration, 1),
        },
        "domain_distribution": dict(domain_counts.most_common()),
        "agent_distribution": dict(agent_counts.most_common()),
        "agent_health": agent_health,
        "errors": errors[:20],       # Cap at 20 most recent
        "warnings": warnings[:10],
        "qa_failures": qa_failures[:10],
        "invariant_violations": invariant_violations,
        "slow_requests": slow_requests[:10],
    }


def format_digest(digest: Dict, target_dates: List[date]) -> str:
    """Format digest as human-readable text."""
    if digest.get("status") == "no_data":
        return f"No trace data found for {', '.join(str(d) for d in target_dates)}"

    s = digest["summary"]
    lines = [
        f"📊 Error Digest — {', '.join(str(d) for d in target_dates)}",
        f"",
        f"Total requests: {s['total_requests']}",
        f"Errors: {s['errors']} ({s['error_rate']:.1%})",
        f"QA failures: {s['qa_failures']} ({s['qa_fail_rate']:.1%})",
        f"Invariant violations: {s['invariant_violations']}",
        f"Slow requests (>{SLOW_REQUEST_MS}ms): {s['slow_requests']}",
        f"Avg duration: {s['avg_duration_ms']:.0f}ms",
        f"",
    ]

    # Agent health
    lines.append("Agent Health:")
    for agent, health in digest.get("agent_health", {}).items():
        icon = {"healthy": "✅", "degraded": "⚠️", "failing": "❌"}.get(health["health"], "?")
        lines.append(f"  {icon} {agent}: {health['total']} requests, {health['errors']} errors")

    # Domain distribution
    lines.append("")
    lines.append("Domain Distribution:")
    for domain, count in digest.get("domain_distribution", {}).items():
        lines.append(f"  {domain}: {count}")

    # Errors detail
    if digest.get("errors"):
        lines.append("")
        lines.append("Errors:")
        for err in digest["errors"][:5]:
            lines.append(f"  [{err['execution_id']}] {err['status']} | {err['domain']} → {err['agent']} | {err['message']}")
            if err.get("error"):
                lines.append(f"    → {err['error'][:120]}")

    # Invariant violations
    if digest.get("invariant_violations"):
        lines.append("")
        lines.append("⚠️ Invariant Violations (direct LLM blocked):")
        for v in digest["invariant_violations"]:
            lines.append(f"  [{v['execution_id']}] domain={v['domain']} expected_agent={v['agent']} | {v['message']}")

    # Slow requests
    if digest.get("slow_requests"):
        lines.append("")
        lines.append("🐌 Slow Requests:")
        for sr in digest["slow_requests"][:5]:
            lines.append(f"  [{sr['execution_id']}] {sr['duration_ms']}ms | {sr['domain']} → {sr['agent']} | {sr['message']}")

    # Overall health
    lines.append("")
    if s["errors"] == 0 and s["invariant_violations"] == 0:
        lines.append("✅ System healthy — no errors or violations")
    elif s["error_rate"] < 0.05:
        lines.append("⚠️ System mostly healthy — minor issues")
    else:
        lines.append(f"❌ System degraded — {s['error_rate']:.1%} error rate")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Error Digest — aggregate execution traces")
    parser.add_argument("--date", type=str, default=None, help="Specific date (YYYY-MM-DD)")
    parser.add_argument("--week", action="store_true", help="Last 7 days")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    # Determine target dates
    if args.week:
        target_dates = [date.today() - timedelta(days=i) for i in range(7)]
    elif args.date:
        target_dates = [date.fromisoformat(args.date)]
    else:
        target_dates = [date.today()]

    # Load and analyze
    all_entries = []
    for d in target_dates:
        all_entries.extend(load_traces(d))

    digest = analyze_traces(all_entries)

    # Save latest digest
    try:
        DIGEST_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with open(DIGEST_OUTPUT, "w", encoding="utf-8") as f:
            json.dump(digest, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # Output
    if args.json:
        print(json.dumps(digest, ensure_ascii=False, indent=2))
    else:
        print(format_digest(digest, target_dates))


if __name__ == "__main__":
    main()
