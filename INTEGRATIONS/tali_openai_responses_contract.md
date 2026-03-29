# Tali ↔ OpenAI Responses API Contract

## Goal
Run Tali through the OpenAI Responses API with strict JSON output, tool calling, and zero free-text leakage.

## Architecture
- Tali / OpenClaw = orchestrator and executor
- OpenAI Responses API = reasoning layer
- Postiz = publishing executor
- Google Drive = asset source
- Analytics = insight source

## Hard rules
- Model output must be JSON only
- No markdown
- No prose
- No process narration
- All external actions must go through tool calls
- OpenClaw validates schema before accepting output
- If schema validation fails, reject and retry once with the same contract

## Recommended response envelope
```json
{
  "ok": true,
  "type": "final",
  "data": {},
  "error": null
}
```

Allowed `type` values:
- `final`
- `clarify`
- `plan`
- `error`

## Global developer prompt
Use one global developer prompt for Tali:

"You are controlled by OpenClaw. Output must be valid JSON only. Never output markdown or prose. Never invent tool results. When an external action is required, call the relevant tool. After tool results are provided, return only valid JSON matching the required schema."

## Tali task schema
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["ok", "type", "data"],
  "properties": {
    "ok": { "type": "boolean" },
    "type": { "type": "string", "enum": ["final", "clarify", "plan", "error"] },
    "data": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "task_type": {
          "type": "string",
          "enum": [
            "caption_gen",
            "hook_variation",
            "visual_brief",
            "performance_check",
            "weekly_plan",
            "schedule_request"
          ]
        },
        "platform": {
          "type": "string",
          "enum": ["instagram", "facebook", "tiktok", "pinterest"]
        },
        "pillar": {
          "type": "string",
          "enum": ["visual_escape", "stay_experience", "dreaming_aspiration", "booking_intent"]
        },
        "objective": { "type": "string" },
        "caption": { "type": "string" },
        "hashtags": {
          "type": "array",
          "items": { "type": "string" }
        },
        "hooks": {
          "type": "array",
          "items": { "type": "string" }
        },
        "frames": {
          "type": "array",
          "items": { "type": "string" }
        },
        "recommended": { "type": "string" },
        "angle": { "type": "string" },
        "publish_time": { "type": "string" },
        "selected_asset": {
          "type": "object",
          "additionalProperties": true,
          "properties": {
            "asset_id": { "type": "string" },
            "filename": { "type": "string" },
            "source": { "type": "string" }
          }
        },
        "notes": { "type": "string" },
        "missing_fields": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "error": {
      "type": ["object", "null"],
      "additionalProperties": false,
      "properties": {
        "code": { "type": "string" },
        "message": { "type": "string" },
        "details": { "type": "object", "additionalProperties": true }
      }
    }
  }
}
```

## First tool surface for Tali
Define small tools only:
- `select_asset`
- `get_queue_state`
- `create_post_draft`
- `schedule_post`
- `get_post_performance`

### Tool guidance
- `select_asset`: choose media from Google Drive / mapped asset store
- `get_queue_state`: read current Postiz queue, drafts, scheduled counts
- `create_post_draft`: create draft artifact only
- `schedule_post`: create real scheduled post with `scheduled_at`
- `get_post_performance`: pull performance metrics for optimization

## Responses API pattern
### Step 1
Send:
- system prompt
- global developer prompt
- task-specific user JSON
- tools
- strict json_schema response_format

### Step 2
If model returns tool calls:
- OpenClaw executes tool calls
- OpenClaw sends tool results back using `previous_response_id`
- Model returns final JSON only

## Validation rules in OpenClaw
- Parse JSON strictly
- Validate against schema
- Reject any non-JSON output
- Reject markdown or prose leakage
- Reject tool hallucination
- Reject missing required envelope fields

## Failure contract
If model cannot complete task with current inputs:
```json
{
  "ok": false,
  "type": "clarify",
  "data": {
    "missing_fields": ["field_name"]
  },
  "error": null
}
```

If runtime/tool failure occurs:
```json
{
  "ok": false,
  "type": "error",
  "data": {},
  "error": {
    "code": "TOOL_FAILURE",
    "message": "Tool execution failed"
  }
}
```

## Recommended model strategy
- Use one global developer prompt
- Put task-specific details in user JSON
- Keep prompts short
- Use strict schema every time
- Use tool calling for all external actions

## Acceptance criteria
A valid implementation should prove:
1. caption_gen returns strict JSON only
2. hook_variation returns strict JSON only
3. schedule_request uses tool calls and returns final JSON only
4. non-JSON output is rejected by OpenClaw
5. tool result round-trip via `previous_response_id` works

This is a runtime contract, not documentation only.
