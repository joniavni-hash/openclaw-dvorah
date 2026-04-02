#!/usr/bin/env python3
"""
Agent Spawner — Spawns domain agents as isolated API calls.

Instead of running agents inside Dvorah's growing context, each agent
gets its own small Claude API call with just its prompt + relevant context.
Result comes back as text that Dvorah forwards — no tool results accumulate.

This is the key cost optimization: 15K tokens per spawn vs 189K in Dvorah's context.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

WORKSPACE = Path(os.environ.get("DVORAH_WORKSPACE", Path.home() / ".openclaw" / "workspace"))

# Import model_client from shared
sys.path.insert(0, str(WORKSPACE / "agents" / "_shared"))
try:
    from model_client import call_model, ModelCallError, ModelResponse
except ImportError:
    # Fallback: try from legal-agent
    sys.path.insert(0, str(WORKSPACE / "agents" / "legal-agent" / "advanced"))
    from model_client import call_model, ModelCallError, ModelResponse


def _read_file(relative_path: str) -> str:
    """Read a workspace file, return empty string on failure."""
    try:
        full = WORKSPACE / relative_path
        if full.exists():
            text = full.read_text(encoding="utf-8")
            # Truncate large files to keep context small
            if len(text) > 8000:
                text = text[:8000] + "\n\n[... truncated to 8000 chars ...]"
            return text
    except Exception:
        pass
    return ""


def _build_context_block(files: List[str]) -> str:
    """Read multiple context files and format as a single block."""
    parts = []
    for f in files:
        content = _read_file(f)
        if content:
            parts.append(f"### {f}\n{content}")
    return "\n\n".join(parts)


def spawn_agent(
    agent_name: str,
    prompt_file: str,
    context_files: List[str],
    user_message: str,
    tier: str = "tier1",
    max_tokens: int = 2048,
    extra_context: str = "",
) -> Dict:
    """
    Spawn a domain agent as an isolated API call.

    Args:
        agent_name: Human name (e.g., "צופית")
        prompt_file: Path to agent's prompt.md (relative to workspace)
        context_files: List of state/context files to include
        user_message: The user's message to process
        tier: Model tier (tier1/tier2/tier3)
        max_tokens: Max output tokens
        extra_context: Additional context (e.g., assembled group prompt)

    Returns:
        Dict with: status, agent, response_text, tokens, cost, error
    """
    start = datetime.now()

    # Read the agent's system prompt
    system_prompt = _read_file(prompt_file)
    if not system_prompt:
        return {
            "status": "error",
            "agent": agent_name,
            "response_text": "",
            "error": f"Prompt file not found: {prompt_file}",
            "tokens": {"input": 0, "output": 0},
            "cost_usd": 0,
        }

    # Build user message with context
    context_block = _build_context_block(context_files)

    user_prompt_parts = []
    if context_block:
        user_prompt_parts.append(f"## Context\n{context_block}")
    if extra_context:
        user_prompt_parts.append(f"## Additional Context\n{extra_context}")
    user_prompt_parts.append(f"## Message\n{user_message}")

    user_prompt = "\n\n".join(user_prompt_parts)

    try:
        response = call_model(
            tier=tier,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=0.2,
        )

        duration_ms = int((datetime.now() - start).total_seconds() * 1000)

        return {
            "status": "ok",
            "agent": agent_name,
            "response_text": response.content,
            "tokens": {
                "input": response.input_tokens,
                "output": response.output_tokens,
                "cache_write": response.cache_creation_input_tokens,
                "cache_read": response.cache_read_input_tokens,
            },
            "cost_usd": response.cost_usd(tier),
            "model": response.model,
            "duration_ms": duration_ms,
        }

    except ModelCallError as e:
        return {
            "status": "error",
            "agent": agent_name,
            "response_text": "",
            "error": str(e),
            "tokens": {"input": 0, "output": 0},
            "cost_usd": 0,
        }
    except Exception as e:
        return {
            "status": "error",
            "agent": agent_name,
            "response_text": "",
            "error": f"Unexpected: {e}",
            "tokens": {"input": 0, "output": 0},
            "cost_usd": 0,
        }


# Agent-specific spawn helpers

def spawn_odya(message: str, group_id: str, role: str = "active",
               extra_context: str = "") -> Dict:
    """Spawn Odya for WhatsApp group message analysis."""
    context_files = [
        "state/KNOWN_GROUPS.md",
        "state/GROUP_MEMBERS.md",
        "state/GROUP_MEMORY.md",
    ]
    return spawn_agent(
        agent_name="אודיה",
        prompt_file="agents/odya-whatsapp/odya_prompt.md",
        context_files=context_files,
        user_message=f"Group: {group_id}\nRole: {role}\nMessage: {message}",
        tier="tier1",
        max_tokens=1500,
        extra_context=extra_context,
    )


def spawn_tzofit(message: str, scope: str = "focused") -> Dict:
    """Spawn Tzofit for research."""
    return spawn_agent(
        agent_name="צופית",
        prompt_file="agents/tzofit-research/tzofit_prompt.md",
        context_files=["state/OPEN_TASKS.md"],
        user_message=f"RESEARCH QUESTION:\n{message}\n\nSCOPE:\n{scope}\n\nLANGUAGE:\nhe",
        tier="tier2",
        max_tokens=4096,
    )


def spawn_eti(message: str) -> Dict:
    """Spawn Eti for automation tasks."""
    return spawn_agent(
        agent_name="אתי",
        prompt_file="agents/eti-automation/eti_prompt.md",
        context_files=["state/OPEN_TASKS.md"],
        user_message=f"AUTOMATION_TASK:\n{message}",
        tier="tier1",
        max_tokens=2048,
    )
