#!/usr/bin/env python3
"""
Agent Executor - Routes to domain agents via isolated spawns or local execution.

PR3: Spawn-based architecture.
- Tzofit, Eti, Odya (group msgs): SPAWN as isolated API calls (small context)
- Dana, Tali, Gabi: LOCAL execution (they do real computation, no API needed)
- Masha: REMOVED

This keeps Dvorah's context small — agent work happens in separate API calls.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Model short names for footer transparency
_TIER_MODEL = {
    "tier1": ("anthropic/claude-sonnet-4-6",  "sonnet", "cheap/fast"),
    "tier2": ("anthropic/claude-sonnet-4-6",  "sonnet", "default"),
    "tier3": ("anthropic/claude-opus-4-6",    "opus",   "premium/legal"),
}

def _meta(tier: str, specialization: str) -> dict:
    model_id, _, reason = _TIER_MODEL.get(tier, _TIER_MODEL["tier2"])
    return {
        "model_tier": tier,
        "model_used": model_id,
        "model_reason": reason,
        "output_mode": "single_message",
        "specialization": specialization,
    }


class AgentExecutor:
    def __init__(self, workspace_path: str = None):
        self.workspace = Path(workspace_path or os.environ.get("DVORAH_WORKSPACE", 
                                                             Path.home() / ".openclaw" / "workspace"))

    def execute_agent_task(self, agent_name: str, message: str, 
                          routing_result: Dict, metadata: Dict = None) -> Dict:
        """
        Returns structured routing info per agent type.
        Actual execution is done by Dvorah via sessions_spawn.
        This script does NOT call models or log costs.
        """
        metadata = metadata or {}
        classification = routing_result.get("classification", {})
        confidence = classification.get("confidence", 0.5)
        model_tier = routing_result.get("model", "unknown")
        
        if agent_name == "odya":
            return self._handle_odya(message, routing_result, metadata)
        elif agent_name == "gabi":
            return self._handle_gabi(message, routing_result, metadata)
        elif agent_name == "dana":
            return self._handle_dana(message, routing_result, metadata)
        elif agent_name == "tzofit":
            return self._handle_tzofit(message, routing_result, metadata)
        elif agent_name == "tali":
            return self._handle_tali(message, routing_result, metadata)
        elif agent_name == "eti":
            return self._handle_eti(message, routing_result, metadata)
        elif agent_name == "cost_reporter" or classification.get("domain") == "cost_usage":
            return self._handle_cost_usage(message, routing_result, metadata)
        else:
            return {
                "status": "routed",
                "agent": agent_name,
                "domain": classification.get("domain", "unknown"),
                "summary": f"Message routed to {agent_name}",
                "message": message[:100],
                "note": "Execution handled by Dvorah, not by this script",
                "timestamp": datetime.now().isoformat()
            }

    def _handle_odya(self, message: str, routing_result: Dict, metadata: Dict) -> Dict:
        """WhatsApp group agent — SPAWNS as isolated API call."""
        from agent_spawner import spawn_odya

        domain = routing_result.get("classification", {}).get("domain", "whatsapp_group")
        group_id = metadata.get("group_id") or routing_result.get("group_id", "unknown")
        role = metadata.get("role", "active")
        tier = routing_result.get("model", "tier1")

        # Observer role → always silence (no API call needed)
        if role == "observer":
            return {
                "status": "analysis_ready",
                "agent": "אודיה",
                "domain": "whatsapp_group",
                "response_type": "group_analysis",
                "requires_approval": False,
                "summary": f"Group {group_id}: observer role — no response",
                "analysis": {"should_respond": False, "reason": "observer role"},
                "metadata": {**_meta(tier, "group_communication"),
                    "group_id": group_id, "role": role},
            }

        # Assemble extra context from group_agent_context if available
        extra_ctx = ""
        try:
            import sys as _sys
            _sys.path.insert(0, str(self.workspace / "scripts"))
            from group_agent_context import assemble_prompt
            extra_ctx = assemble_prompt(group_id, message, metadata.get("recent_messages")) or ""
        except Exception:
            pass

        # SPAWN: isolated API call with small context
        result = spawn_odya(message, group_id, role, extra_context=extra_ctx)

        if result["status"] == "ok":
            return {
                "status": "analysis_ready",
                "agent": "אודיה",
                "domain": domain,
                "response_type": "group_analysis",
                "requires_approval": False,
                "summary": result["response_text"],
                "analysis": {"should_respond": True, "spawned": True},
                "metadata": {**_meta(tier, "group_communication"),
                    "group_id": group_id, "role": role,
                    "spawn_tokens": result.get("tokens", {}),
                    "spawn_cost": result.get("cost_usd", 0),
                    "spawn_duration_ms": result.get("duration_ms", 0)},
            }
        else:
            return {
                "status": "analysis_ready",
                "agent": "אודיה",
                "domain": domain,
                "summary": f"Group {group_id}: spawn failed",
                "analysis": {"should_respond": False},
                "metadata": {**_meta(tier, "group_communication"),
                    "group_id": group_id, "error": result.get("error", "unknown")},
            }

    def _handle_dana(self, message: str, routing_result: Dict, metadata: Dict) -> Dict:
        """Fitness agent — delegates to DanaAgent.execute()."""
        tier = routing_result.get("model", "tier1")
        try:
            import sys as _sys
            _sys.path.insert(0, str(self.workspace / "agents" / "dana-fitness"))
            from dana_agent import DanaAgent
            agent = DanaAgent()
            ctx = {**metadata, "model_decision": routing_result.get("model_decision", {})}
            payload = agent.execute(message, ctx)
            pd = payload.to_dict()
            # Execute write actions (append to fitness tracker)
            for wa in pd.get("write_actions", []):
                if wa.get("type") == "append_file":
                    fpath = self.workspace / wa["path"]
                    try:
                        with open(fpath, "a", encoding="utf-8") as f:
                            f.write(wa["content"])
                    except Exception:
                        pass
            return {
                "status": "executed",
                "agent": "דנה",
                "domain": "fitness",
                "response_type": "fitness_tracking",
                "requires_approval": False,
                "confidence": routing_result.get("classification", {}).get("confidence", 0.8),
                "summary": pd.get("final_text", "Fitness data logged"),
                "data_logged": True,
                "action_taken": pd.get("metadata", {}).get("task_type", "log_entry"),
                "metadata": {**_meta(tier, "nutrition_tracking"),
                             **pd.get("metadata", {})},
            }
        except Exception as e:
            m = _meta(tier, "nutrition_tracking")
            m["error"] = str(e)
            return {
                "status": "executed",
                "agent": "דנה",
                "domain": "fitness",
                "response_type": "fitness_tracking",
                "requires_approval": False,
                "confidence": routing_result.get("classification", {}).get("confidence", 0.5),
                "summary": f"Fitness message received (processing pending): {message[:60]}",
                "data_logged": True,
                "action_taken": "queued",
                "metadata": m,
            }

    def _handle_tzofit(self, message: str, routing_result: Dict, metadata: Dict) -> Dict:
        """Research agent — SPAWNS as isolated API call."""
        from agent_spawner import spawn_tzofit
        tier = routing_result.get("model", "tier2")

        result = spawn_tzofit(message)

        if result["status"] == "ok":
            return {
                "status": "ok",
                "agent": "צופית",
                "domain": "research",
                "response_type": "research_analysis",
                "requires_approval": False,
                "confidence": routing_result.get("classification", {}).get("confidence", 0.7),
                "summary": result["response_text"],
                "analysis": {"query": message[:100], "spawned": True},
                "metadata": {**_meta(tier, "information_gathering"),
                    "spawn_tokens": result.get("tokens", {}),
                    "spawn_cost": result.get("cost_usd", 0),
                    "spawn_duration_ms": result.get("duration_ms", 0)},
            }
        else:
            return {
                "status": "research_ready",
                "agent": "צופית",
                "domain": "research",
                "summary": f"Research spawn failed: {result.get('error', 'unknown')}",
                "analysis": {"query": message[:100]},
                "metadata": {**_meta(tier, "information_gathering"), "error": result.get("error")},
            }

    def _handle_tali(self, message: str, routing_result: Dict, metadata: Dict) -> Dict:
        """Marketing agent — delegates to TaliAgent.execute()."""
        tier = routing_result.get("model", "tier1")
        try:
            import sys as _sys
            _sys.path.insert(0, str(self.workspace / "agents" / "tali-marketing"))
            from tali_agent import TaliAgent
            agent = TaliAgent()
            payload = agent.execute(message, {**metadata})
            pd = payload.to_dict()
            return {
                "status": pd.get("status", "ok"),
                "agent": "טלי",
                "domain": "marketing",
                "response_type": "marketing_content",
                "requires_approval": pd.get("requires_approval", False),
                "confidence": routing_result.get("classification", {}).get("confidence", 0.7),
                "summary": pd.get("final_text", ""),
                "metadata": {**_meta(tier, "content_creation"),
                             **pd.get("metadata", {})},
            }
        except Exception as e:
            return {
                "status": "routed",
                "agent": "טלי",
                "domain": "marketing",
                "response_type": "marketing_content",
                "requires_approval": True,
                "confidence": routing_result.get("classification", {}).get("confidence", 0.7),
                "summary": "Marketing task queued (agent error)",
                "metadata": {**_meta(tier, "content_creation"), "error": str(e)},
            }

    def _handle_eti(self, message: str, routing_result: Dict, metadata: Dict) -> Dict:
        """Automation agent — SPAWNS as isolated API call."""
        from agent_spawner import spawn_eti
        tier = routing_result.get("model", "tier1")

        result = spawn_eti(message)

        if result["status"] == "ok":
            return {
                "status": "ok",
                "agent": "אתי",
                "domain": "automation",
                "response_type": "automation_task",
                "requires_approval": False,
                "confidence": routing_result.get("classification", {}).get("confidence", 0.5),
                "summary": result["response_text"],
                "analysis": {"action": "system_check", "spawned": True},
                "metadata": {**_meta(tier, "system_automation"),
                    "spawn_tokens": result.get("tokens", {}),
                    "spawn_cost": result.get("cost_usd", 0),
                    "spawn_duration_ms": result.get("duration_ms", 0)},
            }
        else:
            return {
                "status": "routed",
                "agent": "אתי",
                "domain": "automation",
                "summary": f"Automation spawn failed: {result.get('error', 'unknown')}",
                "analysis": {"action": "system_check"},
                "metadata": {**_meta(tier, "system_automation"), "error": result.get("error")},
            }


    def _handle_gabi(self, message: str, routing_result: Dict, metadata: Dict) -> Dict:
        """CTO agent — delegates to GabiAgent.execute()."""
        tier = routing_result.get("model", "tier1")
        try:
            import sys as _sys
            _sys.path.insert(0, str(self.workspace / "agents" / "gabi-cto"))
            from gabi_agent import GabiAgent
            agent = GabiAgent()
            payload = agent.execute(message, {**metadata})
            pd = payload.to_dict()
            return {
                "status": pd.get("status", "ok"),
                "agent": "גבי",
                "domain": "cto",
                "response_type": "system_report",
                "requires_approval": pd.get("requires_approval", False),
                "confidence": routing_result.get("classification", {}).get("confidence", 0.8),
                "summary": pd.get("final_text", ""),
                "analysis": {"action": "system_report"},
                "metadata": {**_meta(tier, "system_guardian"),
                             **pd.get("metadata", {})},
            }
        except Exception as e:
            return {
                "status": "routed",
                "agent": "גבי",
                "domain": "cto",
                "response_type": "system_report",
                "requires_approval": False,
                "confidence": routing_result.get("classification", {}).get("confidence", 0.5),
                "summary": "System report unavailable",
                "analysis": {"action": "system_report"},
                "metadata": {**_meta(tier, "system_guardian"), "error": str(e)},
            }

    def _handle_cost_usage(self, message: str, routing_result: Dict, metadata: Dict) -> Dict:
        """Anthropic usage/cost reporter."""
        import sys
        sys.path.insert(0, str(self.workspace))
        try:
            from integrations.anthropic_usage import get_today_anthropic_usage, format_usage_response
            usage = get_today_anthropic_usage()
            response_text = format_usage_response(usage)
        except Exception as e:
            response_text = f"שגיאה בשליפת נתוני עלות: {e}"
        return {
            "status": "executed",
            "agent": "דבורה",
            "domain": "cost_usage",
            "response_type": "cost_report",
            "requires_approval": False,
            "summary": response_text,
            "action_taken": response_text,
            "data_logged": True,
            "metadata": _meta(routing_result.get("model", "tier1"), "cost_reporting"),
        }


agent_executor = AgentExecutor()

def execute_agent_task(agent_name: str, message: str, 
                      routing_result: Dict, metadata: Dict = None) -> Dict:
    return agent_executor.execute_agent_task(agent_name, message, routing_result, metadata)
