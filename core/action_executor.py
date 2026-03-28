#!/usr/bin/env python3
"""
Action Executor - Executes real actions (send messages, update files, etc.)

Only executes after QA approval to prevent unintended actions.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

sys.path.insert(0, str(Path(__file__).parent))
try:
    from output_sanitizer import shape_final_response as _shape, ContractViolation
except ImportError:
    def _shape(text, **kw): return text
    class ContractViolation(Exception): pass


class SingleSendGate:
    """
    Per-request send gate. Enforces: exactly ONE message sent per request.
    All paths that send to user must call acquire() first.
    acquire() returns False if already sent — caller must block.
    """
    def __init__(self):
        self._sent = False
        self._sent_text: Optional[str] = None

    def acquire(self) -> bool:
        """Returns True if this is the first send. False = already sent, block."""
        if self._sent:
            return False
        self._sent = True
        return True

    def record(self, text: str):
        self._sent_text = text

    def reset(self):
        self._sent = False
        self._sent_text = None

    @property
    def already_sent(self) -> bool:
        return self._sent


# Global per-request gate — reset at start of each pipeline execution
_send_gate = SingleSendGate()


def reset_send_gate():
    """Call at the start of each new request/pipeline execution."""
    _send_gate.reset()


class ActionExecutor:
    def __init__(self, workspace_path: str = None):
        self.workspace = Path(workspace_path or os.environ.get("DVORAH_WORKSPACE", 
                                                             Path.home() / ".openclaw" / "workspace"))
        
    def execute_if_approved(self, agent_result: Dict, qa_result: Dict, 
                          original_channel: str = None) -> Dict:
        """Execute actions only if QA passed and appropriate approvals exist"""
        
        if not qa_result["passed"]:
            return {
                "status": "blocked_by_qa", 
                "reason": "QA checks failed",
                "blocking_issues": qa_result["blocking_issues"],
                "recommendations": qa_result["recommendations"]
            }
        
        # Check if action requires approval
        requires_approval = agent_result.get("requires_approval", False)
        
        if requires_approval:
            # For now, all approval-required actions are held for manual review
            return {
                "status": "pending_approval",
                "agent": agent_result.get("agent", "unknown"),
                "approval_reason": agent_result.get("draft_actions", {}).get("approval_reason", "Manual review required"),
                "draft_ready": True,
                "next_step": "Manual review and approval needed before execution"
            }
        
        # Store for footer use
        self._last_agent_result = agent_result
        # Execute approved actions
        return self._execute_action(agent_result, original_channel)
    
    def _execute_action(self, agent_result: Dict, original_channel: str) -> Dict:
        """Execute the actual action"""
        
        agent_name = agent_result.get("agent", "unknown")
        status = agent_result.get("status", "unknown")
        
        if agent_name == "דנה" and status == "executed":
            # Fitness actions already executed in agent_executor
            return {
                "status": "completed",
                "action": "fitness_data_logged",
                "details": agent_result.get("summary", "Fitness data updated"),
                "file_updated": agent_result.get("file_updated")
            }
        
        elif agent_name == "מאשה" and status == "draft_ready":
            # Legal analysis ready, but needs approval
            return {
                "status": "draft_completed",
                "action": "legal_analysis_ready",
                "details": "Legal analysis completed and ready for review",
                "requires_manual_review": True
            }
        
        elif agent_name == "אודיה" and status == "analysis_ready":
            analysis = agent_result.get("analysis", {})
            domain = agent_result.get("domain", "")
            # DM query about a group → return summary text
            if domain == "group_retrieval":
                return {
                    "status": "completed",
                    "action": "group_retrieval_response",
                    "details": agent_result.get("summary", "אין הודעות שמורות מהקבוצה"),
                }
            elif analysis.get("should_respond", False):
                return {
                    "status": "response_recommended",
                    "action": "group_response_suggested",
                    "confidence": analysis.get("confidence", 0),
                    "draft_needed": True,
                }
            else:
                return {
                    "status": "no_response_needed",
                    "action": "group_message_analyzed",
                    "reason": "Message doesn't require response",
                }
        
        elif agent_name == "צופית":
            # Research tasks
            return {
                "status": "research_initiated", 
                "action": "research_query_processed",
                "next_step": "Web search and analysis needed"
            }
        
        else:
            # Default action for other cases
            return {
                "status": "completed",
                "action": "direct_response",
                "details": "Standard conversation handled"
            }
    
    def send_response_if_ready(self, execution_result: Dict, original_channel: str, 
                              original_sender: str = None) -> Dict:
        """Send response via appropriate channel if ready"""
        
        if execution_result["status"] not in ["completed", "response_recommended"]:
            return {
                "status": "no_response_sent",
                "reason": f"Execution status: {execution_result['status']}"
            }
        
        # Prepare response text — full contract enforcement at send boundary
        agent_result = getattr(self, '_last_agent_result', {})
        raw_text = self._prepare_response_text(execution_result, agent_result)
        domain = agent_result.get("domain", "") if isinstance(agent_result, dict) else ""
        mode = "analysis" if domain in ("legal", "research", "fitness") else "default"

        # Extract agent/model for footer
        metadata = agent_result.get("metadata", {}) if isinstance(agent_result, dict) else {}
        model_used = metadata.get("model_used", "")
        if "opus" in model_used:
            model_short = "opus"
        elif "haiku" in model_used:
            model_short = "haiku"
        else:
            model_short = "sonnet"
        agent_name = agent_result.get("agent", "דבורה") if isinstance(agent_result, dict) else "דבורה"
        exec_status = execution_result.get("status", "direct_send")

        try:
            response_text = _shape(raw_text, mode=mode, agent=agent_name,
                                   model=model_short, status=exec_status)
        except ContractViolation:
            return {"status": "no_response_needed", "reason": "contract_violation_empty_after_enforcement"}
        
        if not response_text:
            return {
                "status": "no_response_needed",
                "reason": "No response text to send"
            }
        
        # Single-send gate: block if already sent this request
        if not _send_gate.acquire():
            return {
                "status": "blocked_duplicate_send",
                "reason": "Single-send gate: message already sent this request",
                "text": response_text,
            }
        _send_gate.record(response_text)

        # Send via appropriate channel
        if original_channel == "whatsapp" and original_sender:
            return self._send_whatsapp_response(response_text, original_sender)
        elif original_channel == "telegram" and original_sender:
            return self._send_telegram_response(response_text, original_sender)
        else:
            return {
                "status": "response_ready",
                "text": response_text,
                "note": "Response prepared but no valid channel/sender"
            }
    
    def _prepare_response_text(self, execution_result: Dict, agent_result: Dict = None) -> str:
        """Prepare response text from execution result, with transparency footer."""

        action = execution_result.get("action", "")

        if action == "fitness_data_logged":
            text = execution_result.get("details", "✅ נתונים נרשמו במעקב הכושר")
        elif action == "legal_analysis_ready":
            text = "⚖️ הניתוח המשפטי הושלם ומחכה לבדיקתך"
        elif action == "group_retrieval_response":
            text = execution_result.get("details", "אין הודעות שמורות מהקבוצה")
        elif action == "group_response_suggested":
            return ""
        elif action == "direct_response":
            text = execution_result.get("details", "")
        else:
            return ""

        # Transparency footer — appended to every non-empty response
        if text and agent_result:
            footer = self._build_footer(agent_result, execution_result)
            if footer:
                text = f"{text}\n\n{footer}"

        return text

    def _build_footer(self, agent_result: Dict, execution_result: Dict) -> str:
        """Build short transparency footer. Returns '' for no_reply / empty."""
        agent = agent_result.get("agent", "")
        if not agent:
            return ""

        # model_used — from FinalPayload metadata or legacy fields
        metadata = agent_result.get("metadata", {})
        model_used = metadata.get("model_used", agent_result.get("execution_details", {}).get("model_used", ""))
        # Shorten model id: anthropic/claude-sonnet-4-20250514 → sonnet
        if "opus" in model_used:
            model_short = "opus"
        elif "sonnet" in model_used:
            model_short = "sonnet"
        elif "haiku" in model_used:
            model_short = "haiku"
        else:
            model_short = model_used.split("/")[-1] if "/" in model_used else model_used or "—"

        status = execution_result.get("status", "")
        status_map = {
            "completed":           "נשלח",
            "draft_completed":     "טיוטה מוכנה",
            "response_recommended": "ממתין לאישור",
            "pending_approval":    "ממתין לאישור",
        }
        status_label = status_map.get(status, status)

        return f"_{agent} · {model_short} · {status_label}_"
    
    def _send_whatsapp_response(self, text: str, target: str) -> Dict:
        """Send WhatsApp response via message tool"""
        
        try:
            # Import the message tool (should be available in OpenClaw context)
            # For now, return what would be sent
            return {
                "status": "would_send_whatsapp",
                "target": target,
                "text": text,
                "note": "Would send via message tool - implement when available"
            }
        except Exception as e:
            return {
                "status": "send_failed",
                "error": str(e),
                "channel": "whatsapp"
            }
    
    def _send_telegram_response(self, text: str, target: str) -> Dict:
        """Send Telegram response"""
        
        try:
            return {
                "status": "would_send_telegram", 
                "target": target,
                "text": text,
                "note": "Would send via message tool - implement when available"
            }
        except Exception as e:
            return {
                "status": "send_failed",
                "error": str(e),
                "channel": "telegram"
            }

# Global instance
action_executor = ActionExecutor()

def execute_if_approved(agent_result: Dict, qa_result: Dict, 
                       original_channel: str = None) -> Dict:
    """Global function to execute approved actions"""
    return action_executor.execute_if_approved(agent_result, qa_result, original_channel)

def send_response_if_ready(execution_result: Dict, original_channel: str,
                          original_sender: str = None) -> Dict:
    """Global function to send responses when ready"""
    return action_executor.send_response_if_ready(execution_result, original_channel, original_sender)


def reset_send_gate():
    """Reset per-request single-send gate. Call at start of each pipeline execution."""
    _send_gate.reset()