# Limor Cost Gap Closure Plan

## Goal
Close the runtime cost gap between `openclaw-dvorah` and `OpenClaw-Limor` without weakening Dvorah's agent boundaries, routing discipline, or safety contracts.

## Why the gap exists
Dvorah already has strong governance:
- domain ownership
- single-send enforcement
- output contracts
- budget policy
- routing guards

But Limor is cheaper in the hot path because it applies runtime cost optimizations more aggressively:
- Sonnet-first model routing
- deterministic filtering before model calls
- prompt caching in the real API call path
- relevance-based history selection
- fewer repeated static/dynamic context loads

This plan keeps Dvorah's architecture and imports only the high-leverage cost optimizations.

---

## Change 1 — Add deterministic history selector before any model call

### Problem
Dvorah loads static identity files plus domain state files, but there is no proven equivalent to Limor's `history-selector.ts` that aggressively shrinks conversation history before the model call.

### Required implementation
Add a deterministic selector that returns only:
- recent turns
- entity hits
- explicit commitments / decisions
- dates / scheduled actions
- prior tool outcomes relevant to current task

### Suggested file
- `core/history_selector.py`

### Required behavior
- always include last 10–20 turns
- include messages containing named entities from current message
- include prior decision / action messages
- cap selected history sharply
- return messages in chronological order

### Hard rule
Never send full history by default.

### Success metric
Reduce average history payload by at least 50 percent on repeated conversations.

---

## Change 2 — Split prompt into cached static prefix + tiny dynamic suffix

### Problem
Dvorah repeatedly loads static files such as:
- `IDENTITY.md`
- `SOUL.md`
- `USER.md`
- `CAPABILITY_INDEX.md`
- `MEMORY_INDEX.md`

This is expensive unless the model provider call path uses real prompt caching.

### Required implementation
Use `context_guard.build_ordered_prompt()` as the canonical builder for model-facing prompt assembly.

### Required structure
1. static cached prefix
   - identity
   - soul
   - user
   - capability map
   - stable agent prompt
2. dynamic suffix
   - selected history only
   - tiny state summary
   - current message

### Hard rule
Dynamic state files must not be mixed into the static prefix.

### Success metric
Stable prefix reused across same-agent requests; dynamic suffix stays small and changes per request.

---

## Change 3 — Enforce deterministic no-model paths for known cheap domains

### Problem
Dvorah has routing and cost governance, but too many low-value requests can still drift into model-shaped flows.

### Required implementation
For these request types, return from code when structured state already exists:
- queue status
- scheduled count / draft count
- health summary
- daily status
- weekly summary from structured data
- cost usage summary
- integration connected / disconnected checks

### Suggested files
- `core/deterministic_handlers.py`
- call from `execution_pipeline.py` before agent/model execution

### Hard rule
If answer shape is known and source data already exists, do not call the model.

### Success metric
Cut model calls for status / summary queries by at least 70 percent.

---

## Change 4 — Make Sonnet-first routing real in the execution path

### Problem
Dvorah has `model_selector.py`, but Limor's real runtime remains cheap because almost everything routes to Sonnet, and Opus is extremely rare.

### Required implementation
Keep existing budget governance, but strengthen the runtime default:
- `tier1` or `tier2` for almost all user traffic
- `tier3` only for explicitly justified legal / capability-grade cases
- marketing, fitness, scheduling, cto, group retrieval should never escalate above their declared cheap tier without a recorded reason

### Required tracing
Every model call must record:
- domain
- recommended tier
- final tier
- reason
- context chars
- selected history size

### Hard rule
No silent escalation.

### Success metric
Opus / tier3 usage becomes near-zero in daily normal operation.

---

## Change 5 — Add real per-request cost telemetry by domain and agent

### Problem
Dvorah has budget policy, but cost optimization is hard without per-domain visibility.

### Required implementation
Track for every request:
- agent
- domain
- model
- input tokens
- output tokens
- cache read tokens if available
- cache write tokens if available
- estimated / actual USD cost
- whether response came from deterministic path or model path

### Suggested files
- `core/cost_trace.py`
- append to `workspace/state/traces/cost_YYYY-MM-DD.jsonl`

### Required rollups
Produce daily totals by:
- domain
- agent
- model
- deterministic vs model path

### Hard rule
Do not optimize blindly. Every future cost decision must be backed by traces.

### Success metric
Within one day, identify top 3 most expensive request classes in Dvorah.

---

## Implementation order
1. deterministic history selector
2. cached static prefix + dynamic suffix
3. deterministic no-model handlers
4. Sonnet-first runtime enforcement
5. per-request cost telemetry

---

## Acceptance criteria
A good v1 should prove:
1. repeated direct conversations send much less history
2. static prompt prefix is separated from dynamic suffix
3. queue / health / status questions bypass the model
4. tier3 usage is nearly eliminated in normal traffic
5. cost report can show top expensive domains and agents

This is a runtime optimization plan, not documentation only.
