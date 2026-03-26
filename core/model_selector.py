#!/usr/bin/env python3
"""
Model Selector - Advisory tier mapping.

NOTE (PR1 2026-03-26): Stripped to advisory only.
This script does NOT select models for OpenClaw. 
Model selection is enforced by AGENTS.md governance rules.
Kept for reference and potential future use.
"""

# Tier definitions (reference only — not enforced by this code)
TIERS = {
    "tier1": "anthropic/claude-haiku-4",        # Simple: greetings, acks, data entry
    "tier2": "anthropic/claude-sonnet-4-6",      # Default: most tasks
    "tier3": "anthropic/claude-opus-4-6"         # Restricted: legal, critical only
}

DOMAIN_TIERS = {
    "fitness": "tier1",
    "general": "tier2",
    "email": "tier2",
    "group": "tier1",
    "legal": "tier3",
    "marketing": "tier2",
    "research": "tier2",
    "scheduling": "tier1",
}

def get_tier_for_domain(domain: str) -> str:
    """Advisory: returns recommended tier for domain."""
    return DOMAIN_TIERS.get(domain, "tier2")

def get_model_for_tier(tier: str) -> str:
    """Advisory: returns model ID for tier."""
    return TIERS.get(tier, TIERS["tier2"])
