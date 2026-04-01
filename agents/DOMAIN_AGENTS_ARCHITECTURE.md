# 🎭 Domain Agents Architecture
<!-- Status: Active -->
<!-- Purpose: Complete agent ecosystem documentation -->
<!-- Version: 1.0 — 2026-03-23 -->

## Overview

Dvorah's agent ecosystem consists of **8 domain agents**, each specialized for a specific area.
All agents share a unified architecture with multi-tier cost optimization.

```
                        ┌─────────────────┐
                        │   📨 Message     │
                        │   (DM/Group)     │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │  🧠 Orchestrator │
                        │  (orchestrator.py)│
                        │  classify → route │
                        └────────┬────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
     ┌────────▼──┐    ┌────────▼──┐      ┌────────▼──┐
     │ Domain     │    │ Domain     │      │ Direct    │
     │ Agent      │    │ Agent      │      │ (דבורה)   │
     │ Registry   │    │ Registry   │      │           │
     └────────┬──┘    └────────┬──┘      └───────────┘
              │                │
     ┌────────▼──────────────▼──────────┐
     │      Multi-Tier Model Router      │
     │  T1 (Sonnet) → T2 (Mid) → T3 (Opus)│
     └────────┬──────────────┬──────────┘
              │              │
     ┌────────▼──┐    ┌────▼─────┐
     │ QA Gate   │    │ Trace    │
     │ (qa_svc)  │    │ (trace)  │
     └───────────┘    └──────────┘
```

## Agent Lineup

| # | Emoji | Name | Domain | Directory | Tier Split |
|---|-------|------|--------|-----------|------------|
| 1 | 🏋️ | דנה (Dana) | fitness | `agents/dana-fitness/` | T1:80% T2:15% T3:5% |
| 2 | 🏖️ | טלי (Tali) | marketing | `agents/tali-marketing/` | T1:70% T2:20% T3:10% |
| 3 | 🔍 | צופית (Tzofit) | research | `agents/tzofit-research/` | T1:70% T2:20% T3:10% |
| 4 | 🤖 | אתי (Eti) | automation | `agents/eti-automation/` | T1:75% T2:20% T3:5% |
| 5 | 📱 | אודיה (Odya) | group | `agents/odya-whatsapp/` | T1:85% T2:10% T3:5% |
| 6 | ⚖️ | מאשה (Masha) | legal | `agents/legal-agent/` | T1:70% T2:20% T3:10% |
| 7 | 🔧 | גבי (Gabi) | cto | `agents/gabi-cto/` | T1:80% T2:20% T3:0% |
| 8 | 👑 | דבורה (Dvorah) | general | orchestrator | Session model |

## Unified Architecture

### Every Domain Agent provides:

```python
class DomainAgent(ABC):
    AGENT_NAME: str       # Hebrew name
    AGENT_EMOJI: str      # Visual identifier
    DOMAIN: str           # Routing domain key
    KEYWORDS: List[str]   # Detection keywords
    
    def can_handle(msg, ctx, attachments) → RoutingResult
    def process(msg, ctx, attachments) → AgentOutput
```

### RoutingResult (from can_handle)
```python
{
    "canHandle": true/false,
    "confidence": 0.0-1.0,
    "domain": "fitness",
    "tier": "tier1",           # Selected model tier
    "estimatedCostUsd": 0.0045,
    "reason": "Fitness task: meal_log → tier1"
}
```

### AgentOutput (from process)
```python
{
    "decision": "complete/partial/needs_approval/failed",
    "confidence": 0.85,
    "domain": "fitness",
    "agentName": "דנה",
    "modelTier": "tier1",
    "costUsd": 0.0045,
    "summary": "...",
    "details": "...",
    "draft": {...},
    "toolsUsed": ["read", "exec"],
    "durationMs": 150,
    "qaResult": "pass",
    "memoryDelta": "",
    "stateDelta": "update fitness_tracker.md"
}
```

## Multi-Tier Cost Optimization

All agents share the same 3-tier model architecture:

| Tier | Model | Cost (in/out per 1M) | Usage |
|------|-------|---------------------|-------|
| T1 Cheap | claude-sonnet-4-20250514 | $3/$15 | 70-85% of work |
| T2 Mid | claude-sonnet-4-20250514 (enhanced) | $3/$15 | 10-25% of work |
| T3 Premium | claude-opus-4-20250514 | $15/$75 | 5-10% of work |

### Routing Decision Flow
```
complexity_score < 45 → Tier 1
complexity_score 45-75 → Tier 2
complexity_score > 75 OR risk=critical → Tier 3
```

### Projected Cost (all agents combined)
| Scenario | Est. Monthly Cost |
|----------|------------------|
| All-Opus (old) | ~$250-400 |
| Multi-tier (new) | ~$70-120 |
| **Savings** | **~65-70%** |

## File Structure

```
agents/
├── _shared/
│   ├── __init__.py                  # Shared exports
│   ├── domain_agent_base.py         # Base class + types
│   └── agent_registry.py            # Central registry + routing
├── dana-fitness/
│   ├── dana_agent.py                # DanaAgent class
│   └── dana_prompt.md               # Spawn prompt
├── tali-marketing/
│   ├── tali_agent.py                # TaliAgent class
│   └── tali_prompt.md               # Spawn prompt
├── tzofit-research/
│   ├── tzofit_agent.py              # TzofitAgent class
│   └── tzofit_prompt.md             # Spawn prompt (migrated from research_agent_prompt.md)
├── eti-automation/
│   ├── eti_agent.py                 # EtiAgent class
│   └── eti_prompt.md                # Spawn prompt (migrated from automation_agent_prompt.md)
├── odya-whatsapp/
│   ├── odya_agent.py                # OdyaAgent class
│   ├── odya_prompt.md               # Spawn prompt (migrated from group_agent_prompt.md)
│   └── odya_agent_legacy.py         # Backward-compat wrapper
├── gabi-cto/
│   ├── gabi_agent.py                # GabiAgent class
│   └── gabi_prompt.md               # Spawn prompt
├── legal-agent/                     # Existing — מאשה (unchanged)
│   ├── advanced/                    # Multi-tier pipeline
│   └── ...
├── DOMAIN_AGENTS_ARCHITECTURE.md    # This file
├── group_agent_prompt.md            # Legacy (still works, use odya_prompt.md)
├── research_agent_prompt.md         # Legacy (still works, use tzofit_prompt.md)
├── automation_agent_prompt.md       # Legacy (still works, use eti_prompt.md)
└── whatsapp_group_agent.py          # Legacy (still works, wrapped by odya_agent.py)
```

## Orchestrator Integration

### orchestrator.py Changes
- `DOMAIN_KEYWORDS` — Added: marketing, automation, research domains
- `ROUTING_TABLE` — Updated: all domains → named agents with multi-tier
- `route()` — Domain agents handle their domain (not just conversation)
- Backward compatible: old `WhatsAppGroupAgent` → `אודיה`, `ResearchAgent` → `צופית`

### Agent Registry (agent_registry.py)
- `find_best_agent(msg, ctx)` — scores all agents, returns best match
- `route_message(msg, source)` — orchestrator-compatible routing
- `get_agents()` — lazy-loaded agent instances
- `AGENT_INVENTORY` — full metadata for all agents

## Integration Points

### Core Services (shared by all agents)
1. **ContextService** — load relevant files per domain
2. **PolicyService** — check constraints and approval gates
3. **QAService** — validate output before external actions
4. **TraceService** — log all operations
5. **Orchestrator** — route messages to agents
6. **Agent Registry** — discover and score agents

### Per-Agent Integrations
| Agent | Key Integrations |
|-------|-----------------|
| דנה | `state/fitness_tracker.md`, HEARTBEAT (weigh-in reminders) |
| טלי | `villa-lithos-tiktok/larry-system/`, Postiz API |
| צופית | `web_search`, `web_fetch`, `pdf` tools |
| אתי | `workspace-eti/`, `scripts/health_check.py`, HEARTBEAT |
| אודיה | `state/KNOWN_GROUPS.md`, `scripts/group_messages.py` |
| מאשה | `legal_intent_classifier.py`, multi-tier pipeline |
| גבי | `scripts/health_check.py`, `scripts/error_digest.py`, `scripts/metrics.py` |

## Backward Compatibility

All existing interfaces continue to work:
- `python3 scripts/orchestrator.py --message "..." --source dm` ✅
- `python3 agents/whatsapp_group_agent.py --prepare ...` ✅ (wrapped by Odya)
- `python3 scripts/masha_mvp.py` ✅ (imports MashaAdvanced)
- Legacy prompt files still exist alongside new ones ✅

## Migration Notes (2026-03-23)

### What Changed
1. Created `agents/_shared/` — unified base class and registry
2. Created 4 new domain agent directories (dana, tali, tzofit restructure, eti restructure)
3. Renamed WhatsApp Group Agent → אודיה with new directory
4. Updated orchestrator routing table and domain keywords
5. All agents now use multi-tier cost optimization

### What Didn't Change
- מאשה (legal) — already had multi-tier, untouched
- Legacy files — still in place for backward compatibility
- Core services (QA, trace, context, policy) — unchanged
- HEARTBEAT schedule — unchanged

### Testing
```bash
# Verify all agents load
python3 agents/_shared/agent_registry.py

# Test orchestrator routing
python3 scripts/orchestrator.py --message "אכלתי חזה עוף" --source dm
python3 scripts/orchestrator.py --message "Villa Lithos status" --source dm
python3 scripts/orchestrator.py --message "תחקרי טיסות" --source dm
python3 scripts/orchestrator.py --message "health check" --source dm
python3 scripts/orchestrator.py --message "שלום" --source group --group-id "family"
python3 scripts/orchestrator.py --message "סכמי חוזה" --source dm
```
