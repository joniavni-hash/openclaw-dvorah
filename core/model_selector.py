#!/usr/bin/env python3
"""
Model Selector — PR: Cost Governance Consolidation
Single source of truth for model selection.

Rules (hard-enforced, cannot be overridden):
- Opus (tier3) is BLOCKED unless domain=legal AND requires_high_accuracy=True
- Default fallback: tier2 (sonnet) when context is missing
- NO_REPLY path: no model, cost=$0
- Daily cost guard: if exceeded, downgrade to tier1

This file is the ONLY place that resolves domain → tier → model.
Router recommends tier; this file makes the final call.
Agents receive the decision; they do not select models.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

# ── Model registry ────────────────────────────────────────────────────────────

MODELS = {
    "tier1": "anthropic/claude-haiku-4",
    "tier2": "anthropic/claude-sonnet-4-6",
    "tier3": "anthropic/claude-opus-4-6",
    "none":  "",
}

MODEL_SHORT = {
    "tier1": "haiku",
    "tier2": "sonnet",
    "tier3": "opus",
    "none":  "—",
}

# Max output tokens per tier
MAX_OUTPUT_TOKENS = {
    "tier1": 300,
    "tier2": 800,
    "tier3": 1500,
    "none":  0,
}

# Daily cost cap (USD)
MAX_DAILY_COST_USD = float(os.environ.get("DVORAH_DAILY_BUDGET", "5.0"))

# Domain → default tier
DOMAIN_DEFAULT_TIER = {
    "fitness":          "tier1",
    "group":            "tier1",
    "whatsapp_group":   "tier1",
    "group_retrieval":  "tier1",
    "scheduling":       "tier1",
    "automation":       "tier1",
    "general":          "tier2",
    "email":            "tier2",
    "research":         "tier2",
    "marketing":        "tier2",
    "legal":            "tier2",   # tier3 only with explicit justification
}

# ── Daily cost tracking ────────────────────────────────────────────────────────

_WORKSPACE = Path(os.environ.get("DVORAH_WORKSPACE", Path.home() / ".openclaw" / "workspace"))
_COST_FILE  = _WORKSPACE / "state" / "daily_cost.json"


def _load_daily_cost() -> float:
    try:
        if _COST_FILE.exists():
            data = json.loads(_COST_FILE.read_text())
            if data.get("date") == str(date.today()):
                return float(data.get("usd", 0.0))
    except Exception:
        pass
    return 0.0


def _daily_cost_exceeded() -> bool:
    return _load_daily_cost() >= MAX_DAILY_COST_USD


# ── ModelDecision ─────────────────────────────────────────────────────────────

@dataclass
class ModelDecision:
    tier: str
    model: str
    model_short: str
    allowed: bool
    reason: str
    max_output_tokens: int
    cost_guard: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "tier":             self.tier,
            "model":            self.model,
            "model_short":      self.model_short,
            "allowed":          self.allowed,
            "reason":           self.reason,
            "max_output_tokens": self.max_output_tokens,
            "cost_guard":       self.cost_guard,
        }


# ── Core enforcer ─────────────────────────────────────────────────────────────

def select_model(context: dict) -> ModelDecision:
    """
    ENFORCER — single source of truth for model selection.

    context keys (all optional, safe to omit):
      domain              str   — e.g. "legal", "fitness"
      recommended_tier    str   — from router ("tier1" / "tier2" / "tier3")
      requires_high_accuracy bool — True allows tier3 for legal
      justification       str   — free-text reason for tier3 request
      no_reply            bool  — True → no model, cost=$0
    """
    domain   = context.get("domain", "general")
    no_reply = context.get("no_reply", False)

    # Fast path: NO_REPLY → no model
    if no_reply:
        return ModelDecision(
            tier="none", model="", model_short="—",
            allowed=True, reason="no_reply — no model needed",
            max_output_tokens=0,
            cost_guard={"no_reply": True},
        )

    # Start with domain default
    tier = DOMAIN_DEFAULT_TIER.get(domain, "tier2")

    # Router recommendation (allowed to downgrade only, never upgrade to tier3)
    recommended = context.get("recommended_tier", tier)
    if recommended in ("tier1", "tier2") and recommended < tier:
        tier = recommended

    # Tier3 (Opus) gate — hard block unless legal + justification
    wants_tier3 = (
        recommended == "tier3"
        or context.get("requires_high_accuracy", False)
        or context.get("justification", "")
    )
    if wants_tier3:
        if domain == "legal" and (
            context.get("requires_high_accuracy", False)
            or context.get("justification", "")
        ):
            tier = "tier3"
            reason = f"tier3 approved: legal + {context.get('justification','requires_high_accuracy')}"
        else:
            # Blocked — fallback to tier2
            tier = "tier2"
            reason = (
                f"tier3 BLOCKED: domain={domain} (only legal allowed). "
                "requires_high_accuracy or justification needed. Fallback: tier2."
            )
            return ModelDecision(
                tier=tier, model=MODELS[tier], model_short=MODEL_SHORT[tier],
                allowed=False, reason=reason,
                max_output_tokens=MAX_OUTPUT_TOKENS[tier],
                cost_guard={"daily_usd": _load_daily_cost(), "limit_usd": MAX_DAILY_COST_USD},
            )
    else:
        reason = f"domain={domain} → {tier} (default)"

    # Daily cost guard — if exceeded, downgrade to tier1
    daily_usd = _load_daily_cost()
    if daily_usd >= MAX_DAILY_COST_USD and tier != "tier1":
        original = tier
        tier = "tier1"
        reason = f"daily cost cap exceeded (${daily_usd:.2f} ≥ ${MAX_DAILY_COST_USD}). Downgraded from {original}."

    return ModelDecision(
        tier=tier,
        model=MODELS[tier],
        model_short=MODEL_SHORT[tier],
        allowed=True,
        reason=reason,
        max_output_tokens=MAX_OUTPUT_TOKENS[tier],
        cost_guard={
            "daily_usd": daily_usd,
            "limit_usd": MAX_DAILY_COST_USD,
            "exceeded": daily_usd >= MAX_DAILY_COST_USD,
        },
    )


# ── Legacy shim (keeps existing callers working) ──────────────────────────────

def get_tier_for_domain(domain: str) -> str:
    return DOMAIN_DEFAULT_TIER.get(domain, "tier2")

def get_model_for_tier(tier: str) -> str:
    return MODELS.get(tier, MODELS["tier2"])


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    import sys, argparse
    parser = argparse.ArgumentParser(description="Model selector enforcer")
    parser.add_argument("--domain",    default="general")
    parser.add_argument("--tier",      default="", dest="recommended_tier")
    parser.add_argument("--legal-high", action="store_true", dest="requires_high_accuracy")
    parser.add_argument("--justification", default="")
    parser.add_argument("--no-reply",  action="store_true", dest="no_reply")
    args = parser.parse_args()

    ctx = {
        "domain":               args.domain,
        "recommended_tier":     args.recommended_tier or DOMAIN_DEFAULT_TIER.get(args.domain, "tier2"),
        "requires_high_accuracy": args.requires_high_accuracy,
        "justification":        args.justification,
        "no_reply":             args.no_reply,
    }
    d = select_model(ctx)
    print(json.dumps(d.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
