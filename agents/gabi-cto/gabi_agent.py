#!/usr/bin/env python3
"""
🔧 גבי (Gabi) — CTO Domain Agent

System guardian: health monitoring, OpenClaw updates, self-improvement
from corrections, regression detection.

Multi-tier routing:
- Tier 1 (80%): system status, version check, health report
- Tier 2 (20%): error pattern analysis, self-improvement proposals
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent / "_shared"))
from domain_agent_base import (
    DomainAgent, FinalPayload, RoutingResult, ModelTier, WORKSPACE
)

HEALTH_CHECK_SCRIPT = WORKSPACE / "scripts" / "health_check.py"
ERROR_DIGEST_SCRIPT = WORKSPACE / "scripts" / "error_digest.py"
METRICS_SCRIPT = WORKSPACE / "scripts" / "metrics.py"
HEALTH_STATE = WORKSPACE / "state" / "health_check.json"
ERROR_DIGEST_STATE = WORKSPACE / "state" / "error_digest_latest.json"
CORRECTIONS_FILE = WORKSPACE / "memory" / "corrections.md"
METRICS_STATE = WORKSPACE / "state" / "metrics_latest.json"


class GabiAgent(DomainAgent):
    """CTO / System Guardian domain agent."""

    AGENT_NAME = "גבי"
    AGENT_EMOJI = "🔧"
    DOMAIN = "cto"
    KEYWORDS = [
        "מצב מערכת", "מצב המערכת", "system status", "system health",
        "עדכון", "update", "openclaw", "גרסה", "version",
        "בריאות", "health", "health check",
        "שגיאות", "errors", "תקלות", "failures",
        "שיפור", "improve", "self improve", "regression",
        "תיקונים", "corrections", "דפוסי שגיאות",
        "אבחון", "diagnose", "debug",
    ]

    TASK_TYPES = {
        "system_status":    {"tier": "tier1", "keywords": ["מצב מערכת", "מצב המערכת", "system status", "system health", "סטטוס מערכת"]},
        "health_check":     {"tier": "tier1", "keywords": ["health check", "בריאות", "בריאות המערכת", "בדיקת תקינות"]},
        "version_check":    {"tier": "tier1", "keywords": ["גרסה", "version", "openclaw version", "מה הגרסה"]},
        "update_openclaw":  {"tier": "tier1", "keywords": ["עדכון", "עדכון openclaw", "update openclaw", "עדכני openclaw"]},
        "error_analysis":   {"tier": "tier2", "keywords": ["שגיאות", "errors", "תקלות", "failures", "אבחון", "diagnose"]},
        "self_improve":     {"tier": "tier2", "keywords": ["שיפור", "improve", "self improve", "תיקונים", "corrections", "דפוסי שגיאות"]},
        "regression_check": {"tier": "tier1", "keywords": ["regression", "נסיגה", "ביצועים ירדו"]},
    }

    def can_handle(self, message: str, context: Dict, attachments: List[str] = None) -> RoutingResult:
        score = self.keyword_match(message)

        if re.search(r'(מצב.*מערכת|system.*status|health.*check)', message, re.IGNORECASE):
            score = max(score, 0.92)
        if re.search(r'(עדכון.*openclaw|update.*openclaw|גרסה)', message, re.IGNORECASE):
            score = max(score, 0.9)
        if re.search(r'(שגיאות|errors|תקלות|אבחון)', message, re.IGNORECASE):
            score = max(score, 0.85)
        if re.search(r'(שיפור.*מערכת|self.*improve|corrections)', message, re.IGNORECASE):
            score = max(score, 0.85)

        task_type = self._classify_task(message)
        tier = self._get_tier(task_type)

        return RoutingResult(
            can_handle=score >= 0.3,
            confidence=score,
            domain=self.DOMAIN,
            tier=tier,
            estimated_cost_usd=self.estimate_cost(tier),
            reason=f"CTO task: {task_type} → {tier.value}",
        )

    def execute(self, message: str, context: Dict,
                attachments: List[str] = None) -> FinalPayload:
        self._start_timer()
        task_type = self._classify_task(message)
        tier = self._get_tier(task_type)

        if task_type == "system_status":
            text = self._build_system_report()
            approval = False
        elif task_type == "health_check":
            text = self._build_health_report()
            approval = False
        elif task_type == "version_check":
            text = self._build_version_report()
            approval = False
        elif task_type == "update_openclaw":
            text = self._build_update_proposal()
            approval = True  # Updates always need Yoni's approval
        elif task_type == "error_analysis":
            text = self._build_error_analysis()
            approval = False
        elif task_type == "self_improve":
            text = self._build_self_improvement_report()
            approval = True  # Proposing changes needs approval
        elif task_type == "regression_check":
            text = self._build_regression_report()
            approval = False
        else:
            text = self._build_system_report()
            approval = False

        return FinalPayload(
            status="needs_approval" if approval else "ok",
            agent=self.AGENT_NAME,
            final_text=text,
            should_send=not approval,
            requires_approval=approval,
            metadata={
                "model_used": "anthropic/claude-sonnet-4-20250514",
                "model_reason": f"cto/{task_type} — {tier.value}",
                "output_mode": "draft_for_approval" if approval else "direct_send",
                "task_type": task_type,
                "duration_ms": self._elapsed_ms(),
            },
        )

    # ── Builders ─────────────────────────────────────────────────────────────

    def _build_system_report(self) -> str:
        """Full system status report: health + errors + version + corrections."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        sections = [f"🔧 System Status Report — {ts}\n"]

        # Health
        health = self._load_health_state()
        if health:
            summary = health.get("summary", {})
            ok = summary.get("ok", 0)
            total = summary.get("total", 0)
            failed = summary.get("failed", 0)
            icon = "✅" if failed == 0 else "❌"
            sections.append(f"{icon} Services: {ok}/{total} healthy")
            if failed > 0:
                for name, check in health.get("checks", {}).items():
                    if check.get("ok") is False:
                        sections.append(f"  ❌ {name}: {check.get('status', '?')}")
        else:
            sections.append("⚠️ Health check: no data (run health_check.py)")

        # Errors
        errors = self._load_error_digest()
        if errors and errors.get("status") == "ok":
            s = errors["summary"]
            err_icon = "✅" if s["errors"] == 0 else "⚠️" if s["error_rate"] < 0.05 else "❌"
            sections.append(f"\n{err_icon} Errors: {s['errors']}/{s['total_requests']} ({s['error_rate']:.1%})")
            if s.get("invariant_violations", 0) > 0:
                sections.append(f"  ⚠️ Invariant violations: {s['invariant_violations']}")
            # Agent health summary
            agent_health = errors.get("agent_health", {})
            failing = [n for n, h in agent_health.items() if h.get("health") == "failing"]
            if failing:
                sections.append(f"  ❌ Failing agents: {', '.join(failing)}")
        else:
            sections.append("\n⚠️ Error digest: no data")

        # Version
        version_info = self._get_version_info()
        installed = version_info.get("installed", "?")
        latest = version_info.get("latest", "?")
        if installed == latest:
            sections.append(f"\n✅ OpenClaw: v{installed} (up to date)")
        elif latest != "?":
            sections.append(f"\n🔄 OpenClaw: v{installed} → v{latest} available")
        else:
            sections.append(f"\nℹ️ OpenClaw: v{installed} (latest check failed)")

        # Corrections summary
        corrections = self._parse_corrections()
        if corrections["total"] > 0:
            sections.append(f"\n📝 Corrections: {corrections['total']} logged")
            if corrections["patterns"]:
                sections.append(f"  ⚠️ Repeating patterns: {', '.join(corrections['patterns'])}")
        else:
            sections.append("\n📝 Corrections: none logged")

        return "\n".join(sections)

    def _build_health_report(self) -> str:
        """Focused health check report."""
        # Try to run health check fresh
        self._run_script(HEALTH_CHECK_SCRIPT)
        health = self._load_health_state()
        if not health:
            return "⚠️ Health check failed — no data available"

        ts = health.get("timestamp", "?")[:16]
        lines = [f"🏥 Health Check — {ts}\n"]
        for name, check in health.get("checks", {}).items():
            icon = "✅" if check.get("ok") is True else "❌" if check.get("ok") is False else "❓"
            lines.append(f"{icon} {name}: {check.get('status', '?')}")

        summary = health.get("summary", {})
        lines.append(f"\n{summary.get('ok', 0)}/{summary.get('total', 0)} services healthy")
        return "\n".join(lines)

    def _build_version_report(self) -> str:
        """OpenClaw version check."""
        info = self._get_version_info()
        installed = info.get("installed", "?")
        latest = info.get("latest", "?")

        if installed == "?" and latest == "?":
            return "⚠️ Could not determine OpenClaw version"

        if installed == latest:
            return f"✅ OpenClaw v{installed} — up to date"

        if latest != "?":
            return (
                f"🔄 OpenClaw Update Available\n\n"
                f"Installed: v{installed}\n"
                f"Latest: v{latest}\n\n"
                f"To update: npm update -g openclaw && systemctl --user restart openclaw-gateway\n"
                f"Say 'עדכני openclaw' to proceed (requires approval)"
            )

        return f"ℹ️ OpenClaw v{installed} installed (couldn't check latest)"

    def _build_update_proposal(self) -> str:
        """Proposal to update OpenClaw — requires approval."""
        info = self._get_version_info()
        installed = info.get("installed", "?")
        latest = info.get("latest", "?")

        if installed == latest:
            return f"✅ OpenClaw v{installed} already up to date — no update needed"

        return (
            f"🔄 OpenClaw Update Proposal\n\n"
            f"Current: v{installed}\n"
            f"Target: v{latest}\n\n"
            f"Steps:\n"
            f"1. npm update -g openclaw\n"
            f"2. systemctl --user restart openclaw-gateway\n"
            f"3. Verify gateway health\n\n"
            f"⚠️ This requires Yoni's approval before execution."
        )

    def _build_error_analysis(self) -> str:
        """Deep error pattern analysis."""
        # Run fresh digest
        self._run_script(ERROR_DIGEST_SCRIPT, ["--json"])
        errors = self._load_error_digest()
        if not errors or errors.get("status") != "ok":
            return "⚠️ No error data available for analysis"

        s = errors["summary"]
        lines = [f"🔍 Error Analysis\n"]
        lines.append(f"Total requests analyzed: {s['total_requests']}")
        lines.append(f"Error rate: {s['error_rate']:.1%}")
        lines.append(f"QA failure rate: {s['qa_fail_rate']:.1%}")

        # Agent breakdown
        agent_health = errors.get("agent_health", {})
        if agent_health:
            lines.append("\nAgent Health:")
            for name, h in sorted(agent_health.items()):
                icon = {"healthy": "✅", "degraded": "⚠️", "failing": "❌"}.get(h["health"], "?")
                lines.append(f"  {icon} {name}: {h['total']} reqs, {h['errors']} errors")

        # Error details
        if errors.get("errors"):
            lines.append("\nRecent Errors:")
            for err in errors["errors"][:5]:
                lines.append(f"  • [{err.get('status')}] {err.get('domain')} → {err.get('agent')}: {err.get('message', '')[:60]}")

        # Invariant violations
        if errors.get("invariant_violations"):
            lines.append(f"\n⚠️ Invariant Violations: {len(errors['invariant_violations'])}")
            for v in errors["invariant_violations"][:3]:
                lines.append(f"  • domain={v.get('domain')} should use {v.get('agent')}")

        return "\n".join(lines)

    def _build_self_improvement_report(self) -> str:
        """Analyze corrections and propose improvements."""
        corrections = self._parse_corrections()
        lines = ["🧠 Self-Improvement Report\n"]

        lines.append(f"Total corrections logged: {corrections['total']}")
        lines.append(f"Categories: {len(corrections['categories'])}")

        if corrections["patterns"]:
            lines.append(f"\n⚠️ Repeating Patterns (3+ occurrences):")
            for pattern in corrections["patterns"]:
                count = corrections["categories"].get(pattern, 0)
                lines.append(f"  • {pattern}: {count} occurrences — rule needed")

        if corrections["entries"]:
            lines.append(f"\nRecent Corrections:")
            for entry in corrections["entries"][-5:]:
                lines.append(f"  • {entry.get('header', '?')}")

        # Propose actions
        if corrections["patterns"]:
            lines.append(f"\nProposed Actions:")
            for pattern in corrections["patterns"]:
                lines.append(f"  📌 Create explicit rule in SOUL.md or policies/ for: {pattern}")
            lines.append(f"\n⚠️ Requires approval before making changes.")
        else:
            lines.append(f"\n✅ No repeating patterns — system is learning from mistakes")

        return "\n".join(lines)

    def _build_regression_report(self) -> str:
        """Check for performance regressions."""
        metrics = self._load_metrics()
        errors = self._load_error_digest()

        lines = ["📉 Regression Check\n"]

        if metrics:
            cost = metrics.get("cost", {})
            lines.append(f"Cost (30d): ${cost.get('last_30d', 0):.4f}")
            corrections = metrics.get("corrections", {})
            if corrections.get("repeating_patterns"):
                lines.append(f"⚠️ Repeating error patterns: {', '.join(corrections['repeating_patterns'])}")
            tasks = metrics.get("tasks", {})
            if tasks.get("stuck_7d", 0) > 0:
                lines.append(f"⚠️ {tasks['stuck_7d']} task(s) stuck >7 days")
        else:
            lines.append("⚠️ No metrics data (run scripts/metrics.py)")

        if errors and errors.get("status") == "ok":
            s = errors["summary"]
            if s["error_rate"] > 0.1:
                lines.append(f"❌ Error rate {s['error_rate']:.1%} — above 10% threshold")
            elif s["error_rate"] > 0.05:
                lines.append(f"⚠️ Error rate {s['error_rate']:.1%} — elevated")
            else:
                lines.append(f"✅ Error rate {s['error_rate']:.1%} — healthy")
        else:
            lines.append("⚠️ No error digest data")

        return "\n".join(lines)

    # ── Data loaders ─────────────────────────────────────────────────────────

    def _load_health_state(self) -> Optional[Dict]:
        try:
            if HEALTH_STATE.exists():
                return json.loads(HEALTH_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None

    def _load_error_digest(self) -> Optional[Dict]:
        try:
            if ERROR_DIGEST_STATE.exists():
                return json.loads(ERROR_DIGEST_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None

    def _load_metrics(self) -> Optional[Dict]:
        try:
            if METRICS_STATE.exists():
                return json.loads(METRICS_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None

    def _get_version_info(self) -> Dict:
        """Get installed and latest OpenClaw versions."""
        installed = "?"
        latest = "?"

        try:
            result = subprocess.run(
                ["npm", "list", "-g", "openclaw", "--depth=0"],
                capture_output=True, text=True, timeout=10,
                cwd=str(Path.home())
            )
            match = re.search(r'openclaw@([\d.]+)', result.stdout)
            if match:
                installed = match.group(1)
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["npm", "view", "openclaw", "version"],
                capture_output=True, text=True, timeout=10,
                cwd=str(Path.home())
            )
            v = result.stdout.strip()
            if re.match(r'^\d+\.\d+\.\d+', v):
                latest = v
        except Exception:
            pass

        return {"installed": installed, "latest": latest}

    def _parse_corrections(self) -> Dict:
        """Parse corrections.md for patterns."""
        result = {"total": 0, "entries": [], "categories": {}, "patterns": []}
        try:
            if not CORRECTIONS_FILE.exists():
                return result
            content = CORRECTIONS_FILE.read_text(encoding="utf-8")
        except Exception:
            return result

        blocks = re.split(r'^## ', content, flags=re.MULTILINE)
        for block in blocks[1:]:  # skip header
            lines = block.strip().split('\n')
            if not lines:
                continue
            header = lines[0].strip()
            entry = {"header": header, "category": None}

            for line in lines[1:]:
                # Extract category from **Issue:** or **Problem:** lines
                cat_match = re.search(r'\*\*Issue:\*\*\s*(.*)', line)
                if cat_match:
                    entry["category"] = cat_match.group(1).strip()[:40]

            result["entries"].append(entry)

        result["total"] = len(result["entries"])

        # Count categories
        for entry in result["entries"]:
            cat = entry.get("category")
            if cat:
                result["categories"][cat] = result["categories"].get(cat, 0) + 1

        # Find patterns (3+ occurrences)
        result["patterns"] = [k for k, v in result["categories"].items() if v >= 3]

        return result

    def _run_script(self, script_path: Path, extra_args: List[str] = None) -> Optional[str]:
        """Run a Python script and return stdout."""
        if not script_path.exists():
            return None
        try:
            cmd = [sys.executable, str(script_path)] + (extra_args or [])
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                cwd=str(WORKSPACE)
            )
            return result.stdout if result.returncode == 0 else None
        except Exception:
            return None

    def _classify_task(self, message: str) -> str:
        msg = message.lower()
        for task_type, config in self.TASK_TYPES.items():
            if any(kw in msg for kw in config["keywords"]):
                return task_type
        return "system_status"

    def _get_tier(self, task_type: str) -> ModelTier:
        config = self.TASK_TYPES.get(task_type, {})
        tier_str = config.get("tier", "tier1")
        return {
            "tier1": ModelTier.TIER1_CHEAP,
            "tier2": ModelTier.TIER2_MID,
            "tier3": ModelTier.TIER3_PREMIUM,
        }.get(tier_str, ModelTier.TIER1_CHEAP)


def test_gabi():
    gabi = GabiAgent()
    print(f"Agent: {gabi}")

    tests = [
        "מצב המערכת",
        "עדכני openclaw",
        "מה הגרסה של openclaw?",
        "שגיאות במערכת",
        "שיפור מתיקונים",
        "מה מזג האוויר?",  # should NOT match
    ]

    for msg in tests:
        result = gabi.can_handle(msg, {"sender": "yoni"})
        print(f"\n'{msg}'")
        print(f"  Can handle: {result.can_handle} (conf: {result.confidence:.2f})")
        print(f"  Tier: {result.tier.value}")


if __name__ == "__main__":
    test_gabi()
