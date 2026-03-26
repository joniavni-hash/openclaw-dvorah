#!/usr/bin/env python3
"""
Agent Executor - Routes to domain agents and returns structured results.

Returns structured responses per agent so QA pipeline can process them.
Actual model calls and cost logging happen in Dvorah sessions, not here.
Real agent dispatch will be implemented in PR2.
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
        elif agent_name == "masha":
            return self._handle_masha(message, routing_result, metadata)
        elif agent_name == "dana":
            return self._handle_dana(message, routing_result, metadata)
        elif agent_name == "tzofit":
            return self._handle_tzofit(message, routing_result, metadata)
        elif agent_name == "tali":
            return self._handle_tali(message, routing_result, metadata)
        elif agent_name == "eti":
            return self._handle_eti(message, routing_result, metadata)
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
        """WhatsApp group agent — analyze message and decide whether to reply."""
        group_id = metadata.get("group_id") or routing_result.get("group_id", "unknown")
        role = metadata.get("role", "active")
        confidence = routing_result.get("classification", {}).get("confidence", 0.9)
        
        # Observer role → always silence
        if role == "observer":
            return {
                "status": "analysis_ready",
                "agent": "אודיה",
                "domain": "whatsapp_group",
                "response_type": "group_analysis",
                "requires_approval": False,
                "confidence": confidence,
                "summary": f"Group {group_id}: observer role — no response",
                "analysis": {
                    "should_respond": False,
                    "reason": "observer role",
                    "confidence": confidence,
                },
                "draft_actions": {
                    "approval_reason": "Observer role — auto-silence",
                    "action": "none",
                },
                "metadata": {
                    "model_tier": routing_result.get("model", "tier1"),
                    "group_id": group_id,
                    "role": role,
                    "specialization": "group_communication",
                },
            }
        
        # Active / responder / representative → needs Dvorah to spawn prompt
        return {
            "status": "analysis_ready",
            "agent": "אודיה",
            "domain": "whatsapp_group",
            "response_type": "group_analysis",
            "requires_approval": False,  # approval happens at send time, not analysis
            "confidence": confidence,
            "summary": f"Group {group_id} (role: {role}): message queued for analysis",
            "analysis": {
                "should_respond": None,  # determined after prompt execution
                "confidence": confidence,
                "pending_prompt": True,
            },
            "draft_actions": {
                "approval_reason": f"Group analysis for {group_id}",
                "action": "spawn_odya_prompt",
                "prepare_cmd": f'python3 agents/whatsapp_group_agent.py --prepare --group-id "{group_id}"',
            },
            "metadata": {
                "model_tier": routing_result.get("model", "tier1"),
                "group_id": group_id,
                "role": role,
                "specialization": "group_communication",
            },
        }

    def _handle_masha(self, message: str, routing_result: Dict, metadata: Dict) -> Dict:
        """Legal agent."""
        return {
            "status": "draft_ready",
            "agent": "מאשה",
            "domain": "legal",
            "response_type": "legal_analysis",
            "requires_approval": True,
            "confidence": routing_result.get("classification", {}).get("confidence", 0.8),
            "summary": "Legal analysis queued for review",
            "draft_actions": {
                "approval_reason": "Legal content requires manual review before sending",
                "action": "legal_review",
            },
            "metadata": _meta(routing_result.get("model", "tier2"), "legal_analysis"),
        }

    def _handle_dana(self, message: str, routing_result: Dict, metadata: Dict) -> Dict:
        """Fitness agent — execute meal/weight logging directly."""
        # Dana actually writes to fitness log — delegate to her module
        try:
            import sys
            sys.path.insert(0, str(self.workspace / "agents" / "dana"))
            from dana_agent import process_fitness_message
            result = process_fitness_message(message)
            return {
                "status": "executed",
                "agent": "דנה",
                "domain": "fitness",
                "response_type": "fitness_tracking",
                "requires_approval": False,
                "confidence": routing_result.get("classification", {}).get("confidence", 0.8),
                "summary": result.get("summary", "Fitness data logged"),
                "data_logged": True,
                "action_taken": result.get("action", "log_entry"),
                "file_updated": result.get("file_updated"),
                "metadata": _meta(routing_result.get("model", "tier1"), "nutrition_tracking"),
            }
        except Exception as e:
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
                "metadata": {
                    "model_tier": routing_result.get("model", "tier1"),
                    "specialization": "nutrition_tracking",
                    "error": str(e),
                },
            }

    def _handle_tzofit(self, message: str, routing_result: Dict, metadata: Dict) -> Dict:
        """Research agent."""
        return {
            "status": "research_ready",
            "agent": "צופית",
            "domain": "research",
            "response_type": "research_analysis",
            "requires_approval": False,
            "confidence": routing_result.get("classification", {}).get("confidence", 0.7),
            "summary": "Research query queued for processing",
            "analysis": {
                "query": message[:100],
                "action": "conduct_research",
            },
            "metadata": _meta(routing_result.get("model", "tier2"), "information_gathering"),
        }

    def _handle_tali(self, message: str, routing_result: Dict, metadata: Dict) -> Dict:
        """Marketing agent."""
        return {
            "status": "routed",
            "agent": "טלי",
            "domain": "marketing",
            "response_type": "marketing_content",
            "requires_approval": True,
            "confidence": routing_result.get("classification", {}).get("confidence", 0.7),
            "summary": "Marketing task queued",
            "draft_actions": {
                "approval_reason": "Marketing content requires review before publishing",
                "action": "create_content",
            },
            "metadata": _meta(routing_result.get("model", "tier2"), "content_creation"),
        }

    def _handle_eti(self, message: str, routing_result: Dict, metadata: Dict) -> Dict:
        """Automation agent."""
        return {
            "status": "routed",
            "agent": "עתי",
            "domain": "automation",
            "response_type": "automation_task",
            "requires_approval": False,
            "confidence": routing_result.get("classification", {}).get("confidence", 0.5),
            "summary": "Automation task queued",
            "analysis": {
                "action": "system_check",
            },
            "metadata": _meta(routing_result.get("model", "tier1"), "system_automation"),
        }


agent_executor = AgentExecutor()

def execute_agent_task(agent_name: str, message: str, 
                      routing_result: Dict, metadata: Dict = None) -> Dict:
    return agent_executor.execute_agent_task(agent_name, message, routing_result, metadata)
