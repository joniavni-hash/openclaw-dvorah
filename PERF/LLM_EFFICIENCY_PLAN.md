# LLM Efficiency Plan (Hard Runtime Rules)

## Goal
Reduce token waste, latency, and unnecessary model calls across Dvorah and agents.

---

## 1. Do Not Generate Verbose Then Strip
Rule: forbidden user-facing structures must not be generated in the first place.

Forbidden:
- Diagnosis
- Implementation
- Proof
- Files changed
- Commit
- process narration

Required:
- prompts must enforce final answer only
- sanitizer is fallback only

---

## 2. Minimal Context Only
Rule: send minimal context to model

Exclude:
- old traces
- full execution history
- debug objects
- full analytics

Allow:
- user message
- task type
- minimal state

---

## 3. Prefer Code Over LLM
Rule: deterministic → no model call

Move to code:
- status checks
- queue health
- summaries from structured data
- scheduling summaries

---

## 4. Output Caps
- low max_tokens
- single completion
- no retries unless failure

---

## 5. Cache
Cache:
- health snapshot
- queue validation
- analytics summary

---

## 6. Routing Discipline
- deterministic routing first
- LLM only if ambiguous

---

## Implementation Targets
- core/action_executor.py
- core/output_sanitizer.py
- core/execution_pipeline.py

This is a runtime contract.
