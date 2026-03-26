#!/usr/bin/env python3
"""
Cost Optimizer - Reference definitions only.

NOTE (PR1 2026-03-26): Stripped to reference.
Previous version tracked simulated costs that were never real.
Real cost tracking comes from OpenClaw session data.
Real enforcement comes from AGENTS.md governance rules.
"""

# Daily budget target (reference)
DAILY_BUDGET_USD = 5.0

# Domain tier mapping (reference — matches model_selector.py)
DOMAIN_TIERS = {
    "fitness": "tier1",
    "general": "tier2", 
    "email": "tier2",
    "group": "tier1",
    "legal": "tier3",
    "marketing": "tier2",
    "research": "tier2",
}

def main():
    print("Cost optimizer is now advisory only.")
    print(f"Daily budget target: ${DAILY_BUDGET_USD}")
    print("Real cost tracking: openclaw session logs")
    print("Real enforcement: AGENTS.md governance rules")

if __name__ == "__main__":
    main()
