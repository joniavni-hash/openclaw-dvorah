#!/usr/bin/env python3
"""
Model Selector — Cost Governance Enforcer (hardened)
Single source of truth for model selection.

CONTRACT:
  Router           → returns recommended_tier (advisory only)
  model_selector   → FINAL DECISION (this file, cannot be overridden)
  execution_pipeline → injects decision into routing_result["model_decision"]
  Agents           → read decision, do not select models themselves

HARD RULES:
  1. Tier3/Opus is BLOCKED unless domain=legal AND
     (requires_high_accuracy=True OR justification provided)
  2. NO_REPLY fast-path → no model, cost=$0
  3. Daily cap policy: DOWNGRADE_TO_TIER1 (not hard block)
     Rationale: system keeps working, just cheaper. Hard block would
     cause silent failures. If cap must be a hard block, set
     DVORAH_DAILY_BUDGET_POLICY=block in environment.
  4. Tier comparison uses integer ranks, not string comparison.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# ── Tier ranks (deterministic comparison) ─────────────────────────────────────

TIER_RANK = {"none": 0, "tier1": 1, "tier2": 2, "tier3": 3}

def _rank(tier: str) -> int:
    return TIER_RANK.get(tier, 2)  # unknown → tier2 rank

def _lower_tier(a: str, b: str) -> str:
    """Return the lower-rank tier of the two."""
    return a if _rank(a) <= _rank(b) else b

def _higher_tier(a: str, b: str) -> str:
    """Return the higher-rank tier of the two."""
    return a if _rank(a) >= _rank(b) else b

# ── Model registry ─────────────────────────────────────────────────────────────

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

MAX_OUTPUT_TOKENS = {
    "tier1": 300,
    "tier2": 800,
    "tier3": 1500,
    "none":  0,
}

MAX_DAILY_COST_USD = float(os.environ.get("DVORAH_DAILY_BUDGET", "5.0"))

# "downgrade" (default) or "block"
DAILY_CAP_POLICY = os.environ.get("DVORAH_DAILY_BUDGET_POLICY", "downgrade").lower()

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
    "legal":            "tier2",   # tier3 requires explicit justification
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

# ── ModelDecision ─────────────────────────────────────────────────────────────

@dataclass
class ModelDecision:
    tier: str
    model: str
    model_short: str
    allowed: bool
    reason: str
    max_output_tokens: int
    recommended_tier: str = "tier2"   # what router suggested
    downgraded: bool = False           # tier was lowered vs recommendation
    blocked: bool = False              # tier3 attempt was denied
    no_reply: bool = False             # no_reply fast-path
    cost_guard: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            # Traceability fields
            "recommended_tier":  self.recommended_tier,
            "final_tier":        self.tier,
            "final_model":       self.model,
            "model_short":       self.model_short,
            "allowed":           self.allowed,
            "reason":            self.reason,
            "max_output_tokens": self.max_output_tokens,
            # Decision flags
            "downgraded":        self.downgraded,
            "blocked":           self.blocked,
            "no_reply":          self.no_reply,
            "cost_guard":        self.cost_guard,
        }

# ── Core enforcer ─────────────────────────────────────────────────────────────

def select_model(context: dict) -> ModelDecision:
    """
    ENFORCER — single source of truth.

    context keys (all optional, safe to omit):
      domain                str  — e.g. "legal", "fitness"
      recommended_tier      str  — advisory from router
      requires_high_accuracy bool
      justification         str  — free-text reason for tier3
      no_reply              bool — True → no model needed
    """
    domain      = context.get("domain", "general")
    recommended = context.get("recommended_tier", DOMAIN_DEFAULT_TIER.get(domain, "tier2"))
    no_reply    = bool(context.get("no_reply", False))
    daily_usd   = _load_daily_cost()

    # ── Fast path: NO_REPLY ───────────────────────────────────────────────────
    if no_reply:
        return ModelDecision(
            tier="none", model="", model_short="—",
            allowed=True, no_reply=True,
            reason="no_reply fast-path — no model needed, cost=$0",
            max_output_tokens=0,
            recommended_tier=recommended,
            cost_guard={"no_reply": True},
        )

    # ── Domain default tier ───────────────────────────────────────────────────
    domain_tier = DOMAIN_DEFAULT_TIER.get(domain, "tier2")

    # Router may recommend lower; it may NOT upgrade beyond domain default
    # (except tier3 which has its own gate below)
    if _rank(recommended) <= _rank(domain_tier) and recommended != "tier3":
        base_tier = recommended
    else:
        base_tier = domain_tier

    # ── Tier3/Opus gate ───────────────────────────────────────────────────────
    wants_tier3 = (
        _rank(recommended) == _rank("tier3")
        or bool(context.get("requires_high_accuracy", False))
        or bool(context.get("justification", ""))
    )

    if wants_tier3:
        legal_ok = domain == "legal"
        justified = (
            bool(context.get("requires_high_accuracy", False))
            or bool(context.get("justification", ""))
        )
        if legal_ok and justified:
            final_tier = "tier3"
            reason = (
                f"tier3 APPROVED: domain=legal, "
                f"justification={context.get('justification','requires_high_accuracy')}"
            )
            return ModelDecision(
                tier=final_tier, model=MODELS[final_tier], model_short=MODEL_SHORT[final_tier],
                allowed=True, recommended_tier=recommended, blocked=False,
                reason=reason, max_output_tokens=MAX_OUTPUT_TOKENS[final_tier],
                cost_guard={"daily_usd": daily_usd, "limit_usd": MAX_DAILY_COST_USD},
            )
        else:
            # BLOCKED — fall back to tier2
            reason = (
                f"tier3 BLOCKED: domain={domain} (opus requires domain=legal + justification). "
                f"Fallback: tier2/sonnet."
            )
            return ModelDecision(
                tier="tier2", model=MODELS["tier2"], model_short=MODEL_SHORT["tier2"],
                allowed=False, recommended_tier=recommended, blocked=True,
                reason=reason, max_output_tokens=MAX_OUTPUT_TOKENS["tier2"],
                cost_guard={"daily_usd": daily_usd, "limit_usd": MAX_DAILY_COST_USD},
            )

    # ── Daily cost cap ────────────────────────────────────────────────────────
    cap_exceeded = daily_usd >= MAX_DAILY_COST_USD
    final_tier = base_tier
    downgraded = False

    if cap_exceeded and _rank(base_tier) > _rank("tier1"):
        if DAILY_CAP_POLICY == "block":
            reason = (
                f"HARD BLOCK: daily cost cap exceeded "
                f"(${daily_usd:.2f} ≥ ${MAX_DAILY_COST_USD}). "
                f"Set DVORAH_DAILY_BUDGET_POLICY=downgrade to allow tier1 fallback."
            )
            return ModelDecision(
                tier="none", model="", model_short="—",
                allowed=False, recommended_tier=recommended, blocked=True,
                reason=reason, max_output_tokens=0,
                cost_guard={"daily_usd": daily_usd, "limit_usd": MAX_DAILY_COST_USD, "policy": "block"},
            )
        else:  # downgrade (default)
            final_tier = "tier1"
            downgraded = True
            reason = (
                f"DOWNGRADED to tier1/haiku: daily cost cap exceeded "
                f"(${daily_usd:.2f} ≥ ${MAX_DAILY_COST_USD}). "
                f"Policy: downgrade (set DVORAH_DAILY_BUDGET_POLICY=block for hard stop)."
            )
    else:
        reason = f"domain={domain} → {final_tier} (default)"
        if final_tier != recommended and _rank(final_tier) != _rank(recommended):
            downgraded = _rank(final_tier) < _rank(recommended)
            if downgraded:
                reason = f"downgraded from {recommended} to {final_tier}: domain default caps upgrade"

    return ModelDecision(
        tier=final_tier, model=MODELS[final_tier], model_short=MODEL_SHORT[final_tier],
        allowed=True, recommended_tier=recommended, downgraded=downgraded,
        reason=reason, max_output_tokens=MAX_OUTPUT_TOKENS[final_tier],
        cost_guard={
            "daily_usd": daily_usd, "limit_usd": MAX_DAILY_COST_USD,
            "exceeded": cap_exceeded, "policy": DAILY_CAP_POLICY,
        },
    )

# ── Legacy shims ───────────────────────────────────────────────────────────────

def get_tier_for_domain(domain: str) -> str:
    return DOMAIN_DEFAULT_TIER.get(domain, "tier2")

def get_model_for_tier(tier: str) -> str:
    return MODELS.get(tier, MODELS["tier2"])

# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    import sys, argparse
    parser = argparse.ArgumentParser(description="Model selector enforcer — Cost Governance")
    parser.add_argument("--domain",        default="general")
    parser.add_argument("--tier",          default="", dest="recommended_tier")
    parser.add_argument("--legal-high",    action="store_true", dest="requires_high_accuracy")
    parser.add_argument("--justification", default="")
    parser.add_argument("--no-reply",      action="store_true", dest="no_reply")
    parser.add_argument("--simulate-cap",  action="store_true", help="Simulate daily cap exceeded")
    args = parser.parse_args()

    ctx = {
        "domain":               args.domain,
        "recommended_tier":     args.recommended_tier or DOMAIN_DEFAULT_TIER.get(args.domain, "tier2"),
        "requires_high_accuracy": args.requires_high_accuracy,
        "justification":        args.justification,
        "no_reply":             args.no_reply,
    }
    if args.simulate_cap:
        # Temporarily override daily cost to exceed cap
        import unittest.mock as mock
        with mock.patch("core.model_selector._load_daily_cost", return_value=MAX_DAILY_COST_USD + 1):
            d = select_model(ctx)
    else:
        d = select_model(ctx)
    print(json.dumps(d.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
