# PR1 — Deterministic History Selector v1

## Goal
Add a deterministic history selector to Dvorah so model calls stop receiving broad conversation/state payloads by default.

This is the first concrete runtime change for closing the cost gap versus Limor.

---

## Why this PR comes first
Right now Dvorah has:
- strong routing discipline
- model governance
- context guards
- domain ownership

But she still lacks a proven hot-path equivalent to Limor's `history-selector.ts`.

That means repeated conversations can still send too much history and state to the model.

This PR adds a small, deterministic, model-free selector that sharply reduces conversation history before prompt assembly.

---

## Scope
Implement all of the following in v1:

1. new file: `core/history_selector.py`
2. wire it into the model-facing execution path
3. add trace fields to prove it is actually reducing payload size
4. do not change agent boundaries or routing behavior

---

## New file
Create:
- `core/history_selector.py`

## Required API
```python
from typing import List, Dict, Any

def select_relevant_history(
    history: List[Dict[str, Any]],
    current_message: str,
    mentioned_entities: List[str] | None = None,
    recency_window: int = 12,
    max_selected: int = 40,
) -> List[Dict[str, Any]]:
    """
    Deterministically select the most relevant prior turns.

    Rules:
    - always include recent turns
    - include messages with entity overlap
    - include messages containing decisions / commitments
    - include messages containing dates / schedule references
    - include prior tool/action result markers
    - return in chronological order
    - never call a model
    """
```

---

## Selection rules

### 1. Always include recent turns
Always include the last 10–12 turns.

### 2. Entity overlap
If the current message mentions entities such as:
- Villa Lithos
- Dana
- Tali
- Postiz
- Google Drive
- WhatsApp
- names / projects / dates

then include prior messages containing those entities.

### 3. Decision markers
Boost messages containing explicit commitments / decisions, such as:
- "סיכמנו"
- "הוחלט"
- "שלחתי"
- "קבעתי"
- "תמשכי"
- "commit"
- "scheduled"
- "approved"

### 4. Date and schedule markers
Boost messages containing:
- dates
- times
- day names
- schedule references
- queue / calendar / publish timing

### 5. Tool / action markers
Boost messages that indicate a real action or result, such as:
- Postiz IDs
- commit hashes
- scheduled_count
- draft_count
- queue_health
- status fields

### 6. Chronological output
Return selected messages sorted chronologically.

---

## Hard rules
- no LLM call inside selector
- no semantic embedding search
- no full-history default
- if history is small, return it unchanged
- if history is large, cap aggressively

---

## Integration point
Wire the selector into the model-facing path before prompt assembly.

### Required behavior
Before any model call:
1. load raw conversation history
2. run `select_relevant_history(...)`
3. only pass selected history onward

### Important
Do not break:
- direct deterministic handlers
- no_reply fast path
- owned-domain routing

---

## Trace fields to add
For every request that reaches model execution, log:
- `history_total_turns`
- `history_selected_turns`
- `history_dropped_turns`
- `history_selector_used: true`
- `history_selector_reason_summary`

Write these into the execution trace so cost reduction is measurable.

---

## Expected impact
Target for v1:
- reduce history payload by 50 percent or more in repeated conversations
- no regression in routing or agent ownership
- no change in final answer format

---

## Proof traces required
### Trace 1
Long repeated direct conversation
Expected:
- selected history much smaller than total
- answer still coherent

### Trace 2
Tali scheduling context
Expected:
- prior scheduling messages with IDs and dates preserved
- irrelevant old chatter dropped

### Trace 3
Dana daily follow-up
Expected:
- recent health/logging context preserved
- unrelated history dropped

### Trace 4
Small history conversation
Expected:
- selector returns full history unchanged

---

## Acceptance criteria
Ship this PR only if all are true:
1. selector is deterministic
2. selector runs before model-facing prompt assembly
3. traces prove history reduction
4. no owned-domain routing regressions
5. no format regressions in final output

This is a real implementation PR, not a planning note.
