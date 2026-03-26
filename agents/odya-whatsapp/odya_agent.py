#!/usr/bin/env python3
"""
📱 אודיה (Odya) — WhatsApp Group Domain Agent

Handles: WhatsApp group message analysis, response decisions,
         group memory, role-based behavior.
Integrates with: state/KNOWN_GROUPS.md, state/GROUP_MEMORY.md,
                 scripts/group_messages.py, scripts/group_agent_context.py.

Multi-tier routing:
- Tier 1 (70-85%): noise filtering, simple replies, reaction suggestions
- Tier 2 (10-25%): context-heavy responses, proxy questions, research-backed answers
- Tier 3 (5-10%): sensitive group dynamics, representative mode, complex proxy

Backward compatible with existing whatsapp_group_agent.py interface.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "_shared"))
from domain_agent_base import (
    DomainAgent, AgentOutput, FinalPayload, RoutingResult, ModelTier, WORKSPACE
)


class OdyaAgent(DomainAgent):
    """WhatsApp group messaging domain agent."""
    
    AGENT_NAME = "אודיה"
    AGENT_EMOJI = "📱"
    DOMAIN = "group"
    KEYWORDS = [
        "קבוצה", "group", "whatsapp", "וואטסאפ",
        "הודעה", "message", "תגובה", "reply",
        "דבורה", "דבי",  # Direct mentions in groups
    ]
    
    TASK_TYPES = {
        "noise_filter": {"tier": "tier1", "keywords": []},  # Default for most messages
        "simple_reply": {"tier": "tier1", "keywords": ["דבורה", "דבי"]},
        "reaction": {"tier": "tier1", "keywords": []},
        "proxy_response": {"tier": "tier2", "keywords": ["יוני", "yoni"]},
        "research_reply": {"tier": "tier2", "keywords": ["מה", "איך", "כמה", "?"]},
        "sensitive_reply": {"tier": "tier3", "keywords": []},
        "representative": {"tier": "tier3", "keywords": []},
    }
    
    def can_handle(self, message: str, context: Dict, attachments: List[str] = None) -> RoutingResult:
        """Check if this is a group message to handle."""
        # Group messages are always routed here by the orchestrator
        source = context.get("source", "")
        if source == "group":
            return RoutingResult(
                can_handle=True,
                confidence=0.95,
                domain=self.DOMAIN,
                tier=self._assess_tier(message, context),
                estimated_cost_usd=self.estimate_cost(ModelTier.TIER1_CHEAP),
                reason="Group message → Odya",
            )
        
        score = self.keyword_match(message)
        return RoutingResult(
            can_handle=score >= 0.5,
            confidence=score,
            domain=self.DOMAIN,
            tier=ModelTier.TIER1_CHEAP,
            estimated_cost_usd=self.estimate_cost(ModelTier.TIER1_CHEAP),
            reason=f"Group-related query (score: {score:.2f})",
        )
    
    # ── Group name → group_id map (from WHATSAPP_GROUPS.md) ─────────────────
    GROUP_NAME_MAP = {
        "אלון":     "120363418497534459@g.us",
        "כיתה":     "120363418497534459@g.us",
        "ב3":       "120363418497534459@g.us",
        "ב׳":       "120363418497534459@g.us",
        "האלופה":   "120363418497534459@g.us",
        "שני":      "120363425514726135@g.us",
        "משפחה":    "120363425514726135@g.us",
        "מתן":      "120363425249923804@g.us",
    }

    GROUP_ID_TO_NAME = {
        "120363418497534459@g.us": "כיתה ב׳-3 האלופה",
        "120363425514726135@g.us": "Yoni <> Shani <> Dvora",
        "120363425249923804@g.us": "קבוצה עם מתן",
    }

    def _identify_group(self, message: str) -> Optional[str]:
        """Map group name mentioned in message to group_id."""
        msg = message.lower()
        for keyword, gid in self.GROUP_NAME_MAP.items():
            if keyword in msg:
                return gid
        return None

    def execute(self, message: str, context: Dict, attachments: List[str] = None) -> FinalPayload:
        """PR2: returns FinalPayload.
        Retrieval-first: if domain=group_retrieval, fetch messages before any denial.
        """
        self._start_timer()

        # ── Group retrieval path (DM asking about a group) ────────────────────
        # domain may be at root of context OR nested inside routing.classification
        routing = context.get("routing", {})
        domain = (
            context.get("domain")
            or routing.get("classification", {}).get("domain", "")
        )
        if domain == "group_retrieval":
            return self._execute_group_retrieval(message, context)

        tier = self._assess_tier(message, context)
        role = context.get("role", "active")
        group_id = context.get("group_id", "unknown")

        # Build actual response decision text
        should_respond, reason = self._decide_response(message, context)
        if not should_respond:
            return FinalPayload(
                status="no_reply",
                agent=self.AGENT_NAME,
                final_text="",
                should_send=False,
                requires_approval=False,
                metadata={
                    "model_used":   "none",
                    "model_reason": reason,
                    "output_mode":  "no_reply",
                    "group_id":     group_id,
                    "role":         role,
                    "duration_ms":  self._elapsed_ms(),
                },
            )

        final_text = self._build_group_response(message, context, tier)
        return FinalPayload(
            status="needs_approval",
            agent=self.AGENT_NAME,
            final_text=final_text,
            should_send=False,          # group responses always need approval
            requires_approval=True,
            metadata={
                "model_used":   TIER_TO_MODEL.get(tier, "anthropic/claude-sonnet-4-20250514")
                                if False else "anthropic/claude-sonnet-4-20250514",
                "model_reason": f"group/{role} — {tier.value}",
                "output_mode":  "draft_for_approval",
                "group_id":     group_id,
                "role":         role,
                "duration_ms":  self._elapsed_ms(),
            },
        )


    def _parse_time_range(self, message: str) -> int:
        """
        Extract requested lookback days from message text.
        Returns integer days. Default: 1.
        Preserves exact user request — never substitutes silently.
        """
        import re
        msg = message.lower()

        # Explicit number + unit
        m = re.search(r'(\d+)\s*(יום|ימים|days?)', msg)
        if m:
            return int(m.group(1))

        # Common phrases
        if any(x in msg for x in ['היום', 'today', 'הבוקר', 'this morning']):
            return 1
        if any(x in msg for x in ['אתמול', 'yesterday']):
            return 2   # today + yesterday
        if any(x in msg for x in ['יומיים', 'two days', '2 days']):
            return 2
        if any(x in msg for x in ['שבוע', 'week', 'שבוע שעבר']):
            return 7
        if any(x in msg for x in ['חודש', 'month']):
            return 30

        return 1  # default: today only

    def _execute_group_retrieval(self, message: str, context: Dict) -> FinalPayload:
        """
        Retrieval-first path for DM queries about a group.
        Tries to fetch cached messages. Returns what was found — never silent denial.
        """
        import subprocess
        group_id   = self._identify_group(message)
        group_name = self.GROUP_ID_TO_NAME.get(group_id, "הקבוצה") if group_id else "הקבוצה"

        if not group_id:
            return FinalPayload(
                status="ok",
                agent=self.AGENT_NAME,
                final_text=(
                    "לא הצלחתי לזהות על איזו קבוצה מדובר.\n"
                    "קבוצות מוכרות: כיתה ב׳-3 (אלון), משפחה (שני), מתן."
                ),
                should_send=True,
                requires_approval=False,
                metadata={"model_used": "none", "model_reason": "group not identified",
                          "output_mode": "direct_send"},
            )

        # Parse requested time range from message
        requested_days = self._parse_time_range(message)

        # Try to fetch messages via group_messages.py
        try:
            ws = str(WORKSPACE)
            result = subprocess.run(
                ["python3", f"{ws}/scripts/group_messages.py", group_id, "--days", str(requested_days)],
                capture_output=True, text=True, timeout=10, cwd=ws
            )
            raw = result.stdout.strip()
        except Exception as e:
            raw = f"ERROR: {e}"

        if requested_days == 1:
            range_label = "יום"
        elif requested_days == 2:
            range_label = "יומיים"
        elif requested_days == 7:
            range_label = "שבוע"
        elif requested_days == 30:
            range_label = "חודש"
        else:
            range_label = f"{requested_days} ימים"

        if not raw or raw == "NO_MESSAGES_FOUND":
            # Check GROUP_MEMORY.md for cached summary
            mem_file = WORKSPACE / "state" / "GROUP_MEMORY.md"
            cached = ""
            if mem_file.exists():
                mem_content = mem_file.read_text(encoding="utf-8")
                for line in mem_content.split("\n"):
                    if group_name in line or group_id in line:
                        cached = f"יש מידע חלקי ב-GROUP_MEMORY.md אך אין הודעות שמורות ב{range_label} האחרונים."
                        break

            final_text = (
                f"אין הודעות שמורות מ{group_name} ב{range_label} האחרונים."
                + (f"\n{cached}" if cached else "")
            )
        else:
            # Got messages — format as summary
            lines = [l for l in raw.split("\n") if l.strip()][:20]
            hw_lines = [l for l in lines if any(w in l.lower() for w in
                        ["שיעורי בית", "שיעורים", "לחינוך", "להביא", "מחר", "לקרוא", "לכתוב"])]

            if hw_lines:
                final_text = f"שיעורי בית מ-{group_name}:\n" + "\n".join(f"• {l}" for l in hw_lines)
            else:
                final_text = (
                    f"הודעות אחרונות מ-{group_name} ({len(lines)} הודעות):\n"
                    + "\n".join(f"• {l}" for l in lines[:8])
                    + "\n\nלא זיהיתי שיעורי בית ספציפיים."
                )

        messages_found = len([l for l in raw.split("\n") if l.strip()]) if raw and raw != "NO_MESSAGES_FOUND" else 0
        return FinalPayload(
            status="ok",
            agent=self.AGENT_NAME,
            final_text=final_text,
            should_send=True,
            requires_approval=False,
            metadata={
                "model_used":            "none",
                "model_reason":          f"group_retrieval/{group_name} — tier1",
                "output_mode":           "direct_send",
                # Traceability
                "group_id":              group_id,
                "group_name":            group_name,
                "requested_time_range":  f"{requested_days}d",
                "applied_time_range":    f"{requested_days}d",
                "messages_found":        messages_found,
                "source":                "group_messages.py",
            },
        )

    def _decide_response(self, message: str, context: Dict):
        """Decide whether to respond at all in the group."""
        msg = message.lower()
        role = context.get("role", "active")

        if role == "observer":
            return False, "observer mode — silent"

        mentions_dvorah = any(w in msg for w in ["דבורה", "דבי", "dvorah"])
        is_question = "?" in message
        is_direct_task = any(w in msg for w in ["תשלחי", "תבדקי", "תעשי"])

        if mentions_dvorah or is_question or is_direct_task:
            return True, "direct mention / question / task"
        return False, "no trigger — group noise"

    def _build_group_response(self, message: str, context: Dict,
                               tier: ModelTier) -> str:
        role = context.get("role", "active")
        group_id = context.get("group_id", "")
        prefix = f"[טיוטה ← אודיה 📱 | {group_id}]\n"
        if "?" in message:
            return prefix + f"תגובה לשאלה: {message}\n(ממתין לעיבוד מודל)"
        return prefix + f"הודעה שהתקבלה בקבוצה — ממתין להחלטת תגובה.\n{message}"
    
    def _assess_tier(self, message: str, context: Dict) -> ModelTier:
        """Assess which tier is needed based on message + context."""
        role = context.get("role", "active")
        
        # Observer → always Tier 1 (just to confirm silence)
        if role == "observer":
            return ModelTier.TIER1_CHEAP
        
        # Representative mode → Tier 3 (speaking for Yoni)
        if role == "representative":
            return ModelTier.TIER3_PREMIUM
        
        # Direct mention of דבורה + complex question → Tier 2
        if re.search(r'(דבורה|דבי)', message) and '?' in message:
            return ModelTier.TIER2_MID
        
        # Default: Tier 1
        return ModelTier.TIER1_CHEAP


# Backward compatibility: maintain existing interface
def prepare_group_response(group_id: str, new_message: dict) -> dict:
    """Backward-compatible wrapper for existing orchestrator calls."""
    agent = OdyaAgent()
    context = {
        "source": "group",
        "group_id": group_id,
        "role": new_message.get("role", "active"),
    }
    result = agent.process(
        new_message.get("text", ""),
        context,
    )
    return result.to_dict()


def test_odya():
    odya = OdyaAgent()
    print(f"Agent: {odya}")
    
    tests = [
        ("שלום לכולם", {"source": "group", "role": "observer"}),
        ("דבורה, מתי הפגישה?", {"source": "group", "role": "active"}),
        ("יוני, אתה מגיע?", {"source": "group", "role": "representative"}),
    ]
    
    for msg, ctx in tests:
        result = odya.can_handle(msg, ctx)
        print(f"\n'{msg}' (role: {ctx.get('role')})")
        print(f"  Can handle: {result.can_handle} (conf: {result.confidence:.2f})")
        print(f"  Tier: {result.tier.value}")


if __name__ == "__main__":
    test_odya()
