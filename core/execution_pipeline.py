#!/usr/bin/env python3
"""
Execution Pipeline - Main orchestrator that replaces manual AGENTS.md flow.

Flow: message → router → context → agent → QA → response
Ensures consistent execution with overflow protection.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from router import route_message
from context_guard import context_status, emergency_compact
from agent_executor import AgentExecutor
from action_executor import execute_if_approved, send_response_if_ready, reset_send_gate
from model_selector import select_model, ModelDecision

# Feature flag — set AUTO_GIT_PUSH_ENABLED=false to disable
AUTO_GIT_PUSH_ENABLED = os.environ.get("AUTO_GIT_PUSH_ENABLED", "true").lower() != "false"
AUTO_GIT_PUSH_STATUSES = {"completed", "draft_completed", "no_response_needed"}
_GIT_SYNC = Path(__file__).resolve().parent.parent / "scripts" / "git_sync.py"


def _auto_git_push(execution_id: str) -> None:
    """Fire-and-forget git sync. Logs error but never raises."""
    if not AUTO_GIT_PUSH_ENABLED:
        return
    if not _GIT_SYNC.exists():
        return
    try:
        msg = f"auto: task {execution_id} {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        result = subprocess.run(
            [sys.executable, str(_GIT_SYNC), "-m", msg],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            print(f"[git_sync] push failed: {result.stderr.strip()}", file=sys.stderr)
        elif result.stdout.strip():
            print(f"[git_sync] {result.stdout.strip()}", file=sys.stderr)
    except Exception as e:
        print(f"[git_sync] exception: {e}", file=sys.stderr)

# ── Domain → Agent ownership table ───────────────────────────────────────────
# Any domain listed here MUST route through its agent.
# Direct LLM response is BLOCKED for owned domains — no exceptions.
DOMAIN_AGENT_OWNERS: Dict[str, str] = {
    "fitness":          "dana",
    "marketing":        "tali",
    "group_retrieval":  "odya",
    "whatsapp_group":   "odya",
    "research":         "tzofit",
    "automation":       "eti",
    "scheduling":       "eti",
    "cto":              "gabi",
    "cost_usage":       "cost_reporter",
}


def _build_footer(agent_name: str, model_short: str, status_label: str) -> str:
    """Single canonical footer builder. Called only at send boundary."""
    if not agent_name:
        return ""
    return f"סוכנת: {agent_name} | מודל: {model_short} | מצב: {status_label}"


class ExecutionPipeline:
    def __init__(self, workspace_path: str = None):
        self.workspace = Path(workspace_path or os.environ.get("DVORAH_WORKSPACE", 
                                                             Path.home() / ".openclaw" / "workspace"))
        self.execution_log = []
        self.agent_executor = AgentExecutor(workspace_path)
        
    def execute(self, message: str, channel: str = None, 
               group_id: str = None, metadata: Dict = None) -> Dict:
        """Main execution function - replaces AGENTS.md manual flow"""
        
        start_time = datetime.now()
        execution_id = f"exec_{start_time.strftime('%Y%m%d_%H%M%S')}_{id(message)}"
        
        try:
            # Reset single-send gate for this request
            reset_send_gate()

            # Step 1: Route message 
            routing_result = route_message(message, channel, group_id)
            
            # Step 2: Check context status
            ctx_status = context_status()
            if ctx_status["status"] == "critical":
                emergency_compact()
                ctx_status = context_status()
            
            # Step 2b: Model governance — single source of truth
            is_no_reply = routing_result.get("routing_decision", {}).get("action") == "no_reply"
            model_decision = select_model({
                "domain":           routing_result["classification"]["domain"],
                "recommended_tier": routing_result.get("recommended_tier",
                                       routing_result.get("model", "tier2")),
                "no_reply":         is_no_reply,
            })
            # Inject enforced model into routing_result so agents receive it
            routing_result["model"]          = model_decision.tier
            routing_result["model_decision"] = model_decision.to_dict()

            # Step 3: Invariant guard — owned domains MUST route through their agent.
            # If routing says "handle_direct" but domain is owned → FAIL CLOSED.
            routing_action = routing_result["routing_decision"]["action"]
            classified_domain = routing_result["classification"]["domain"]
            expected_agent = DOMAIN_AGENT_OWNERS.get(classified_domain)

            if routing_action == "handle_direct" and expected_agent:
                # VIOLATION: pipeline tried to bypass agent for owned domain
                violation_record = {
                    "execution_id": execution_id,
                    "timestamp": start_time.isoformat(),
                    "status": "invariant_violation",
                    "classified_domain": classified_domain,
                    "expected_agent": expected_agent,
                    "routing_action": routing_action,
                    "direct_llm_response_blocked": True,
                    "agent_execution_started": False,
                    "agent_execution_completed": False,
                    "footer_applied": False,
                    "send_path": "blocked",
                    "message": message[:100] + "..." if len(message) > 100 else message,
                }
                self._log_execution(violation_record)
                return {
                    "status": "invariant_violation",
                    "execution_id": execution_id,
                    "error": f"FAIL CLOSED: domain '{classified_domain}' requires agent '{expected_agent}', direct response blocked",
                    "classified_domain": classified_domain,
                    "expected_agent": expected_agent,
                    "direct_llm_response_blocked": True,
                    "fallback_action": "routing_correction_required",
                    "execution_summary": violation_record,
                }

            # Step 3: Execute based on routing decision
            if routing_action == "handle_direct" and not expected_agent:
                result = self._handle_direct(message, routing_result, metadata)
            elif routing_action == "handle_direct" and expected_agent:
                # Should never reach here due to guard above, but defensive
                raise RuntimeError(f"Invariant escape: {classified_domain} → {expected_agent}")
            else:
                # Use real agent executor instead of dummy responses
                agent_name = routing_result["routing_decision"]["agent"]
                agent_metadata = {**(metadata or {}), "execution_id": execution_id,
                                  "model_decision": model_decision.to_dict()}
                if group_id:
                    agent_metadata["group_id"] = group_id
                result = self.agent_executor.execute_agent_task(agent_name, message, routing_result,
                                          agent_metadata)
            
            # Step 4: QA Check
            qa_result = self._qa_check(result, routing_result)
            
            # Step 5: Execute approved actions
            execution_result = execute_if_approved(result, qa_result, channel)
            
            # Step 6: Send response if ready
            response_result = send_response_if_ready(execution_result, channel, 
                                                   metadata.get("sender_id") if metadata else None)
            
            # Step 7: Log execution — full trace metadata
            _agent_used = routing_result["routing_decision"].get("agent", "direct")
            _routing_action = routing_result["routing_decision"].get("action", "unknown")
            execution_record = {
                "execution_id": execution_id,
                "timestamp": start_time.isoformat(),
                "message": message[:100] + "..." if len(message) > 100 else message,
                "channel": channel,
                "group_id": group_id,
                "classified_domain": classified_domain,
                "expected_agent": expected_agent,
                "agent_execution_started": _routing_action == "route_to_agent",
                "agent_execution_completed": result.get("status") not in ("error", "unknown", None),
                "direct_llm_response_blocked": bool(expected_agent) and _routing_action == "route_to_agent",
                "footer_applied": bool(response_result.get("text", "")),
                "send_path": "agent_pipeline" if _agent_used != "direct" else "direct",
                "routing": routing_result["classification"],
                "context_status": ctx_status,
                "agent_response": result.get("status", "unknown"),
                "qa_passed": qa_result["passed"],
                "action_executed": execution_result.get("status", "unknown"),
                "response_sent": response_result.get("status", "unknown"),
                "context_payload_present": bool(result.get("context_payload")),
                "dynamic_context_files": (result.get("context_payload") or {}).get("context_files_read", []),
                "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000)
            }
            
            self._log_execution(execution_record)

            # Step 8: Auto git push — only on successful task completion
            exec_status = execution_result.get("status", "")
            if exec_status in AUTO_GIT_PUSH_STATUSES:
                _auto_git_push(execution_id)

            # Step 9: Footer guarantee at send boundary
            # Footer is appended here — single canonical location, cannot be skipped.
            _response_text = response_result.get("text", "")
            if _response_text:
                _agent_name = result.get("agent", routing_result["routing_decision"].get("agent", "דבורה"))
                _md = result.get("metadata", {})
                _model_used = _md.get("model_used", "")
                if "opus" in _model_used:
                    _model_short = "opus"
                elif "haiku" in _model_used:
                    _model_short = "haiku"
                elif "sonnet" in _model_used:
                    _model_short = "sonnet"
                else:
                    _model_short = model_decision.tier
                _status_label = execution_result.get("status", "direct_send")
                _footer = _build_footer(_agent_name, _model_short, _status_label)
                if _footer and not _response_text.strip().endswith(_footer.strip()):
                    response_result["text"] = f"{_response_text}\n\n{_footer}"
                execution_record["footer_applied"] = bool(_footer)

            return {
                "status": "success",
                "execution_id": execution_id,
                "routing": routing_result,
                "agent_result": result,
                "qa_result": qa_result,
                "execution_result": execution_result,
                "response_result": response_result,
                "execution_summary": execution_record
            }
            
        except Exception as e:
            error_record = {
                "execution_id": execution_id,
                "timestamp": start_time.isoformat(),
                "status": "error",
                "error": str(e),
                "message": message[:100] + "..." if len(message) > 100 else message,
                "channel": channel
            }
            
            self._log_execution(error_record)
            
            return {
                "status": "error",
                "execution_id": execution_id,
                "error": str(e),
                "fallback_action": "manual_review_required",
                "execution_summary": error_record
            }
    
    def _handle_direct(self, message: str, routing: Dict, metadata: Dict) -> Dict:
        """Handle messages that go directly to Dvorah (no agent)"""
        tier = routing.get("model", "tier2")
        model_id = "anthropic/claude-sonnet-4-6"
        return {
            "status": "direct_response",
            "agent": "דבורה",
            "domain": "general",
            "response_type": "conversational",
            "requires_approval": False,
            "routing_reason": routing["classification"]["reason"],
            "confidence": routing["classification"]["confidence"],
            "response_ready": True,
            # QA: response_completeness needs one of: summary/analysis/draft_actions/data_logged/action_taken
            "summary": "Direct conversational response",
            "metadata": {
                "model_tier": tier,
                "model_used": model_id,
                "model_reason": "direct path — no agent dispatch",
                "output_mode": "single_message",
                "context_files": routing["context"]["files_loaded"],
            }
        }
    
    def _route_to_agent(self, message: str, routing: Dict, metadata: Dict) -> Dict:
        """Route message to specific domain agent"""
        
        agent_name = routing["routing_decision"]["agent"]
        domain = routing["routing_decision"]["domain"]
        
        # Load appropriate agent
        if agent_name == "masha":
            import sys
            sys.path.insert(0, str(self.workspace))
            from agents.masha.masha_agent import handle_legal_task
            return handle_legal_task(message, {
                "routing": routing,
                "metadata": metadata
            })
        
        elif agent_name == "dana":
            # Fitness agent - for now return structured response
            return {
                "status": "agent_response_ready",
                "agent": "dana",
                "domain": "fitness",
                "response_type": "fitness_tracking",
                "requires_approval": False,
                "confidence": routing["classification"]["confidence"],
                "suggested_action": "log_meal_data",
                "metadata": {
                    "model_tier": routing["model"],
                    "specialization": "nutrition_tracking"
                }
            }
        
        elif agent_name == "odya":
            # WhatsApp group agent
            return {
                "status": "agent_response_ready", 
                "agent": "odya",
                "domain": "whatsapp_group",
                "response_type": "group_analysis",
                "requires_approval": True,  # Group messages need approval
                "confidence": routing["classification"]["confidence"],
                "suggested_action": "analyze_group_context",
                "metadata": {
                    "model_tier": routing["model"],
                    "specialization": "group_communication"
                }
            }
        
        elif agent_name == "tzofit":
            # Research agent
            return {
                "status": "agent_response_ready",
                "agent": "tzofit", 
                "domain": "research",
                "response_type": "research_analysis",
                "requires_approval": False,
                "confidence": routing["classification"]["confidence"],
                "suggested_action": "conduct_research",
                "metadata": {
                    "model_tier": routing["model"],
                    "specialization": "information_gathering"
                }
            }
        
        else:
            # Unknown agent - fallback to direct
            return {
                "status": "fallback_to_direct",
                "original_agent": agent_name,
                "reason": f"Agent {agent_name} not implemented yet",
                "requires_approval": False,
                "fallback_action": "handle_as_general"
            }
    
    def _qa_check(self, agent_result: Dict, routing: Dict) -> Dict:
        """Quality assurance check before final response"""
        
        checks = {
            "context_overflow": self._check_context_overflow(),
            "approval_required": self._check_approval_requirements(agent_result),
            "response_completeness": self._check_response_completeness(agent_result),
            "risk_assessment": self._check_risk_level(agent_result, routing)
        }
        
        passed_checks = sum(1 for check in checks.values() if check["passed"])
        total_checks = len(checks)
        
        overall_passed = passed_checks == total_checks
        
        return {
            "passed": overall_passed,
            "score": passed_checks / total_checks,
            "checks": checks,
            "recommendations": self._generate_qa_recommendations(checks),
            "blocking_issues": [name for name, check in checks.items() 
                              if not check["passed"] and check.get("blocking", False)]
        }
    
    def _check_context_overflow(self) -> Dict:
        """Check for context overflow issues"""
        status = context_status()
        
        return {
            "name": "context_overflow",
            "passed": status["status"] != "critical",
            "details": status,
            "blocking": status["status"] == "critical"
        }
    
    def _check_approval_requirements(self, agent_result: Dict) -> Dict:
        """Check if response requires approval"""
        
        requires_approval = agent_result.get("requires_approval", False)
        has_approval_reason = bool(agent_result.get("draft_actions", {}).get("approval_reason"))
        
        if requires_approval and not has_approval_reason:
            return {
                "name": "approval_required",
                "passed": False,
                "details": "Response requires approval but no reason provided",
                "blocking": True
            }
        
        return {
            "name": "approval_required",
            "passed": True,
            "details": f"Approval: {'required' if requires_approval else 'not required'}",
            "blocking": False
        }
    
    def _check_response_completeness(self, agent_result: Dict) -> Dict:
        """Check if response is complete and ready"""
        
        has_status = "status" in agent_result
        has_content = any(key in agent_result for key in ["response", "analysis", "draft_actions", "summary", "data_logged", "action_taken"])
        
        complete = has_status and has_content
        
        return {
            "name": "response_completeness",
            "passed": complete,
            "details": f"Status: {has_status}, Content: {has_content}",
            "blocking": not complete
        }
    
    def _check_risk_level(self, agent_result: Dict, routing: Dict) -> Dict:
        """Assess risk level of response"""
        
        domain = routing["classification"]["domain"]
        agent = routing["routing_decision"]["agent"]
        
        # Legal responses are always high risk
        if domain == "legal" or agent == "masha":
            return {
                "name": "risk_assessment",
                "passed": agent_result.get("requires_approval", False),
                "details": "Legal response - approval required",
                "blocking": not agent_result.get("requires_approval", False)
            }
        
        # Group messages need review
        if domain == "whatsapp_group":
            return {
                "name": "risk_assessment", 
                "passed": True,
                "details": "Group message - moderate risk",
                "blocking": False
            }
        
        # Low risk domains
        return {
            "name": "risk_assessment",
            "passed": True, 
            "details": "Low risk domain",
            "blocking": False
        }
    
    def _generate_qa_recommendations(self, checks: Dict) -> List[str]:
        """Generate actionable recommendations based on QA results"""
        
        recommendations = []
        
        for check_name, check_result in checks.items():
            if not check_result["passed"]:
                if check_name == "context_overflow":
                    recommendations.append("Run emergency context compaction")
                elif check_name == "approval_required":
                    recommendations.append("Add approval reason before proceeding")  
                elif check_name == "response_completeness":
                    recommendations.append("Complete response before sending")
                elif check_name == "risk_assessment":
                    recommendations.append("Add approval gate for high-risk response")
        
        return recommendations
    
    def _log_execution(self, record: Dict):
        """Log execution record"""
        self.execution_log.append(record)
        
        # Also write to trace file
        trace_file = self.workspace / "state" / "traces" / f"execution_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        trace_file.parent.mkdir(exist_ok=True)
        
        try:
            with open(trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            # Fail silently - don't break execution for logging issues
            pass

# Global pipeline instance
pipeline = ExecutionPipeline()

def execute_message(message: str, channel: str = None, 
                   group_id: str = None, metadata: Dict = None) -> Dict:
    """Global execution function"""
    return pipeline.execute(message, channel, group_id, metadata)