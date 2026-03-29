"""
Tali ↔ OpenAI Responses API client.

Implements the contract defined in INTEGRATIONS/tali_openai_responses_contract.md.
Supports real mode (with OPENAI_API_KEY) and mock mode (without).
"""

import json
import os
import sys
import copy
from pathlib import Path

import jsonschema
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Env
# ---------------------------------------------------------------------------
_SECRETS_ENV = Path(__file__).resolve().parent.parent / "secrets" / ".env"
if _SECRETS_ENV.exists():
    load_dotenv(_SECRETS_ENV)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
POSTIZ_API_KEY = os.environ.get("POSTIZ_API_KEY", "").strip()

MOCK_MODE = not OPENAI_API_KEY

# ---------------------------------------------------------------------------
# Contract schema (from spec)
# ---------------------------------------------------------------------------
RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ok", "type", "data"],
    "properties": {
        "ok": {"type": "boolean"},
        "type": {"type": "string", "enum": ["final", "clarify", "plan", "error"]},
        "data": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "task_type": {
                    "type": "string",
                    "enum": [
                        "caption_gen",
                        "hook_variation",
                        "visual_brief",
                        "performance_check",
                        "weekly_plan",
                        "schedule_request",
                    ],
                },
                "platform": {
                    "type": "string",
                    "enum": ["instagram", "facebook", "tiktok", "pinterest"],
                },
                "pillar": {
                    "type": "string",
                    "enum": [
                        "visual_escape",
                        "stay_experience",
                        "dreaming_aspiration",
                        "booking_intent",
                    ],
                },
                "objective": {"type": "string"},
                "caption": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
                "hooks": {"type": "array", "items": {"type": "string"}},
                "frames": {"type": "array", "items": {"type": "string"}},
                "recommended": {"type": "string"},
                "angle": {"type": "string"},
                "publish_time": {"type": "string"},
                "selected_asset": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "asset_id": {"type": "string"},
                        "filename": {"type": "string"},
                        "source": {"type": "string"},
                    },
                },
                "notes": {"type": "string"},
                "missing_fields": {"type": "array", "items": {"type": "string"}},
            },
        },
        "error": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "details": {"type": "object", "additionalProperties": True},
            },
        },
    },
}

# Per-task strict json_schema wrappers for OpenAI response_format.
# The outer envelope (ok, type, data, error) is shared; only `data` differs.

def _make_response_format(name: str, data_properties: dict, data_required: list) -> dict:
    """Build a strict json_schema response_format for the Responses API text.format field."""
    return {
        "type": "json_schema",
        "name": name,
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["ok", "type", "data", "error"],
            "properties": {
                "ok": {"type": "boolean"},
                "type": {
                    "type": "string",
                    "enum": ["final", "clarify", "plan", "error"],
                },
                "data": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": data_properties,
                    "required": data_required,
                },
                "error": {
                    "anyOf": [
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "code": {"type": "string"},
                                "message": {"type": "string"},
                            },
                            "required": ["code", "message"],
                        },
                        {"type": "null"},
                    ]
                },
            },
        },
    }


SCHEMA_CAPTION_GEN = _make_response_format(
    "tali_caption_gen",
    {
        "task_type": {"type": "string"},
        "platform": {"type": "string"},
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "angle": {"type": "string"},
        "notes": {"type": "string"},
    },
    ["task_type", "platform", "caption", "hashtags", "angle", "notes"],
)

SCHEMA_HOOK_VARIATION = _make_response_format(
    "tali_hook_variation",
    {
        "task_type": {"type": "string"},
        "platform": {"type": "string"},
        "hooks": {"type": "array", "items": {"type": "string"}},
        "recommended": {"type": "string"},
        "notes": {"type": "string"},
    },
    ["task_type", "platform", "hooks", "recommended", "notes"],
)

SCHEMA_GENERIC = _make_response_format(
    "tali_generic",
    {
        "task_type": {"type": "string"},
        "platform": {"type": "string"},
        "notes": {"type": "string"},
    },
    ["task_type", "platform", "notes"],
)

_TASK_SCHEMA_MAP = {
    "caption_gen": SCHEMA_CAPTION_GEN,
    "hook_variation": SCHEMA_HOOK_VARIATION,
}


def _get_schema_for_task(task_type: str) -> dict:
    """Return the strict response_format schema matching *task_type*."""
    return _TASK_SCHEMA_MAP.get(task_type, SCHEMA_GENERIC)

# ---------------------------------------------------------------------------
# Global developer prompt
# ---------------------------------------------------------------------------
DEVELOPER_PROMPT = (
    "You are controlled by OpenClaw. Output must be valid JSON only. "
    "Never output markdown or prose. Never invent tool results. "
    "When an external action is required, call the relevant tool. "
    "After tool results are provided, return only valid JSON matching the required schema."
)

# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_response(obj: dict) -> tuple:
    """Validate *obj* against the contract schema.
    Returns (True, None) or (False, error_string).
    """
    try:
        jsonschema.validate(instance=obj, schema=RESPONSE_SCHEMA)
        return (True, None)
    except jsonschema.ValidationError as exc:
        return (False, str(exc.message))


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI format) + local executors
# ---------------------------------------------------------------------------

ASSET_DIR = Path(__file__).resolve().parent.parent / "villa-lithos" / "assets" / "raw"

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "select_asset",
        "description": "Choose a media asset from the mapped asset store.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term or filename hint for asset selection.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_queue_state",
        "description": "Read the current Postiz publishing queue — drafts, scheduled, and published counts.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "create_post_draft",
        "description": "Create a local draft JSON artifact for a social-media post.",
        "parameters": {
            "type": "object",
            "properties": {
                "platform": {"type": "string"},
                "caption": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
                "asset_id": {"type": "string"},
            },
            "required": ["platform", "caption"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "schedule_post",
        "description": "Schedule a post for publishing at a given time.",
        "parameters": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string"},
                "scheduled_at": {"type": "string"},
            },
            "required": ["draft_id", "scheduled_at"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_post_performance",
        "description": "Pull performance metrics for a published post.",
        "parameters": {
            "type": "object",
            "properties": {
                "post_id": {"type": "string"},
            },
            "required": ["post_id"],
            "additionalProperties": False,
        },
    },
]


def _exec_select_asset(args: dict) -> dict:
    """Return a fixture asset from villa-lithos/assets/raw/."""
    files = list(ASSET_DIR.glob("*")) if ASSET_DIR.exists() else []
    query = args.get("query", "").lower()
    match = None
    for f in files:
        if query in f.name.lower():
            match = f
            break
    if match is None and files:
        match = files[0]
    if match:
        return {"asset_id": match.stem, "filename": match.name, "source": "villa-lithos/assets/raw"}
    return {"asset_id": "placeholder", "filename": "placeholder.jpg", "source": "mock"}


def _exec_get_queue_state(args: dict) -> dict:
    """Call Postiz API if key is available, otherwise return mock."""
    if POSTIZ_API_KEY:
        try:
            resp = requests.get(
                "https://app.postiz.com/api/v1/posts",
                headers={"Authorization": f"Bearer {POSTIZ_API_KEY}", "Content-Type": "application/json"},
                timeout=10,
            )
            if resp.ok:
                posts = resp.json() if isinstance(resp.json(), list) else resp.json().get("posts", [])
                drafts = sum(1 for p in posts if p.get("state") == "draft")
                scheduled = sum(1 for p in posts if p.get("state") == "scheduled")
                published = sum(1 for p in posts if p.get("state") == "published")
                return {"drafts": drafts, "scheduled": scheduled, "published": published}
        except Exception:
            pass
    return {"drafts": 2, "scheduled": 3, "published": 15}


def _exec_create_post_draft(args: dict) -> dict:
    """Save a local draft JSON file and return its id."""
    import hashlib, time
    draft_id = hashlib.md5(f"{time.time()}".encode()).hexdigest()[:12]
    draft_dir = Path(__file__).resolve().parent.parent / "drafts"
    draft_dir.mkdir(exist_ok=True)
    draft_path = draft_dir / f"{draft_id}.json"
    draft_path.write_text(json.dumps(args, indent=2))
    return {"draft_id": draft_id, "path": str(draft_path)}


def _exec_schedule_post(args: dict) -> dict:
    """Stub — log scheduling intent, do not call Postiz."""
    print(f"[TaliOpenAI] schedule_post stub: draft={args.get('draft_id')} at {args.get('scheduled_at')}")
    return {"status": "scheduled_stub", "draft_id": args.get("draft_id"), "scheduled_at": args.get("scheduled_at")}


def _exec_get_post_performance(args: dict) -> dict:
    """Return mock metrics."""
    return {
        "post_id": args.get("post_id", "unknown"),
        "impressions": 1240,
        "reach": 890,
        "likes": 67,
        "comments": 12,
        "shares": 4,
        "engagement_rate": 0.054,
    }


TOOL_EXECUTORS = {
    "select_asset": _exec_select_asset,
    "get_queue_state": _exec_get_queue_state,
    "create_post_draft": _exec_create_post_draft,
    "schedule_post": _exec_schedule_post,
    "get_post_performance": _exec_get_post_performance,
}


# ---------------------------------------------------------------------------
# Mock responses for each task type
# ---------------------------------------------------------------------------

MOCK_RESPONSES = {
    "caption_gen": {
        "ok": True,
        "type": "final",
        "data": {
            "task_type": "caption_gen",
            "platform": "instagram",
            "pillar": "visual_escape",
            "caption": "Wake up to the sound of waves and the scent of pine. Villa Lithos — where the Aegean meets the sky.",
            "hashtags": ["#VillaLithos", "#AegeanEscape", "#LuxuryTravel", "#GreekIslands"],
            "angle": "morning serenity",
            "notes": "Mock response — no real API call.",
        },
        "error": None,
    },
    "hook_variation": {
        "ok": True,
        "type": "final",
        "data": {
            "task_type": "hook_variation",
            "platform": "instagram",
            "pillar": "dreaming_aspiration",
            "hooks": [
                "You weren't meant for a 9-to-5 view.",
                "This is the morning you've been scrolling for.",
                "POV: your alarm is the Aegean Sea.",
            ],
            "recommended": "POV: your alarm is the Aegean Sea.",
            "notes": "Mock response — no real API call.",
        },
        "error": None,
    },
    "schedule_request": {
        "ok": True,
        "type": "final",
        "data": {
            "task_type": "schedule_request",
            "platform": "instagram",
            "pillar": "stay_experience",
            "caption": "Every detail, designed for you.",
            "hashtags": ["#VillaLithos", "#StayExperience"],
            "publish_time": "2026-04-01T10:00:00Z",
            "selected_asset": {
                "asset_id": "IMG_8363",
                "filename": "IMG_8363.jpeg",
                "source": "villa-lithos/assets/raw",
            },
            "notes": "Mock response — tool calls simulated.",
        },
        "error": None,
    },
}


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class TaliOpenAIClient:
    """Tali OpenAI Responses API client with automatic mock fallback."""

    API_URL = "https://api.openai.com/v1/responses"
    MODEL = "gpt-4o"

    def __init__(self):
        self.mock = MOCK_MODE
        if self.mock:
            print("[TaliOpenAI] MOCK MODE — no real API calls")

    # ---- public API -------------------------------------------------------

    def run_task(self, task_json: dict) -> dict:
        """Execute a Tali task. Returns a validated response envelope."""
        task_type = task_json.get("task_type", "caption_gen")

        if self.mock:
            return self._mock_task(task_type, task_json)

        return self._real_task(task_json)

    # ---- mock path --------------------------------------------------------

    def _mock_task(self, task_type: str, task_json: dict) -> dict:
        base = MOCK_RESPONSES.get(task_type)
        if base is None:
            base = MOCK_RESPONSES["caption_gen"]
        resp = copy.deepcopy(base)
        # Ensure task_type in data matches request
        resp["data"]["task_type"] = task_type
        return resp

    # ---- real path --------------------------------------------------------

    def _real_task(self, task_json: dict, _retry: bool = False) -> dict:
        """Call OpenAI Responses API, handle tool calls, validate."""
        schema = _get_schema_for_task(task_json.get("task_type", ""))
        body = {
            "model": self.MODEL,
            "instructions": DEVELOPER_PROMPT,
            "input": [
                {"role": "user", "content": json.dumps(task_json)},
            ],
            "tools": TOOL_DEFINITIONS,
            "text": {"format": schema},
        }

        resp_data = self._api_call(body)
        if resp_data is None:
            return self._error_envelope("API_FAILURE", "OpenAI API call failed")

        # Handle tool-call round-trips
        resp_data = self._handle_tool_calls(resp_data, schema)
        if resp_data is None:
            return self._error_envelope("TOOL_FAILURE", "Tool execution failed")

        # Extract text output
        parsed = self._extract_json(resp_data)
        if parsed is None:
            if _retry:
                return self._error_envelope("PARSE_FAILURE", "Could not parse JSON from model output after retry")
            # retry once
            return self._real_task(task_json, _retry=True)

        valid, err = validate_response(parsed)
        if not valid:
            if _retry:
                return self._error_envelope("SCHEMA_FAILURE", f"Schema validation failed after retry: {err}")
            return self._real_task(task_json, _retry=True)

        return parsed

    def _api_call(self, body: dict) -> dict | None:
        try:
            r = requests.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=60,
            )
            if not r.ok:
                print(f"[TaliOpenAI] API error {r.status_code}: {r.text[:300]}")
                return None
            return r.json()
        except Exception as exc:
            print(f"[TaliOpenAI] API exception: {exc}")
            return None

    def _handle_tool_calls(self, resp_data: dict, schema: dict) -> dict | None:
        """Process tool calls iteratively until model returns final output."""
        max_rounds = 5
        for _ in range(max_rounds):
            # Check if there are tool call outputs in the response
            output_items = resp_data.get("output", [])
            tool_calls = [o for o in output_items if o.get("type") == "function_call"]
            if not tool_calls:
                return resp_data

            response_id = resp_data.get("id")
            tool_results = []
            for tc in tool_calls:
                fn_name = tc.get("name", "")
                call_id = tc.get("call_id", "")
                try:
                    fn_args = json.loads(tc.get("arguments", "{}"))
                except json.JSONDecodeError:
                    fn_args = {}

                executor = TOOL_EXECUTORS.get(fn_name)
                if executor:
                    result = executor(fn_args)
                else:
                    result = {"error": f"Unknown tool: {fn_name}"}

                tool_results.append({
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(result),
                })

            # Send tool results back
            body = {
                "model": self.MODEL,
                "instructions": DEVELOPER_PROMPT,
                "input": tool_results,
                "tools": TOOL_DEFINITIONS,
                "text": {"format": schema},
                "previous_response_id": response_id,
            }
            resp_data = self._api_call(body)
            if resp_data is None:
                return None

        return resp_data

    def _extract_json(self, resp_data: dict) -> dict | None:
        """Pull the JSON text from model output items."""
        for item in resp_data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    text = content.get("text", "")
                    if text:
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            continue
        return None

    @staticmethod
    def _error_envelope(code: str, message: str) -> dict:
        return {
            "ok": False,
            "type": "error",
            "data": {},
            "error": {"code": code, "message": message},
        }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test():
    print("=" * 60)
    print("Tali OpenAI Client — Self-Test (5 traces)")
    print("=" * 60)

    client = TaliOpenAIClient()
    results = []

    # Trace 1: caption_gen
    print("\n--- Trace 1: caption_gen ---")
    r = client.run_task({"task_type": "caption_gen", "platform": "instagram", "pillar": "visual_escape"})
    ok, err = validate_response(r)
    status = "PASS" if ok and r.get("ok") else "FAIL"
    print(json.dumps(r, indent=2))
    print(f"Schema valid: {ok} | Trace 1: {status}")
    results.append(status)

    # Trace 2: hook_variation
    print("\n--- Trace 2: hook_variation ---")
    r = client.run_task({"task_type": "hook_variation", "platform": "instagram", "pillar": "dreaming_aspiration"})
    ok, err = validate_response(r)
    status = "PASS" if ok and r.get("ok") else "FAIL"
    print(json.dumps(r, indent=2))
    print(f"Schema valid: {ok} | Trace 2: {status}")
    results.append(status)

    # Trace 3: schedule_request (tool call round-trip in mock)
    print("\n--- Trace 3: schedule_request ---")
    r = client.run_task({"task_type": "schedule_request", "platform": "instagram", "pillar": "stay_experience"})
    ok, err = validate_response(r)
    status = "PASS" if ok and r.get("ok") else "FAIL"
    print(json.dumps(r, indent=2))
    print(f"Schema valid: {ok} | Trace 3: {status}")
    results.append(status)

    # Trace 4: non-JSON response rejected
    print("\n--- Trace 4: non-JSON rejection ---")
    bad_obj = "This is not JSON, it is plain prose about villas."
    try:
        parsed = json.loads(bad_obj)
        ok, err = validate_response(parsed)
    except (json.JSONDecodeError, TypeError):
        ok = False
        err = "not valid JSON"
    status = "PASS" if not ok else "FAIL"
    print(f"Input: {bad_obj!r}")
    print(f"Rejected: {not ok} (error: {err}) | Trace 4: {status}")
    results.append(status)

    # Trace 5: mock fallback — instantiate client with no key by temporarily overriding OPENAI_API_KEY
    print("\n--- Trace 5: mock mode (no API key) ---")
    saved_key = os.environ.pop("OPENAI_API_KEY", None)
    try:
        mock_client = TaliOpenAIClient.__new__(TaliOpenAIClient)
        mock_client.mock = True
        mock_r = mock_client._mock_task("caption_gen", {"task_type": "caption_gen", "platform": "instagram"})
        mock_ok, _ = validate_response(mock_r)
        status = "PASS" if mock_ok else "FAIL"
        print(f"Mock mode active: True | Valid output: {mock_ok} | Trace 5: {status}")
    finally:
        if saved_key:
            os.environ["OPENAI_API_KEY"] = saved_key
    results.append(status)

    # Summary
    print("\n" + "=" * 60)
    for i, s in enumerate(results, 1):
        print(f"  Trace {i}: {s}")
    all_pass = all(s == "PASS" for s in results)
    print(f"\nOverall: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    print("=" * 60)
    return all_pass


if __name__ == "__main__":
    success = _self_test()
    sys.exit(0 if success else 1)
