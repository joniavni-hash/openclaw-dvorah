#!/usr/bin/env python3
"""
Smart Router — PR1: Cost + Output Enforcement

Changes from PR1:
- legal domain: tier2 by default (NOT tier3/Opus)
- group messages: tier1 always, NO_REPLY fast-path before any model call
- NO_REPLY classification exits before expensive routing
- Opus escalation only via explicit justification
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from context_guard import safe_read_file, context_status


# ── NO_REPLY fast-path patterns ───────────────────────────────────────────────
# If a group message matches these, classify as NO_REPLY immediately.
# No model call, no agent call, cost = $0.
NO_REPLY_PATTERNS = [
    r"^\s*👍|❤️|😂|🙏|✅|🔥|😊",          # emoji-only
    r"^[\U0001F300-\U0001FFFF\s]+$",          # all emoji
    r"^\s*ok\s*$|^\s*כן\s*$|^\s*אוקי\s*$",   # single-word ack
    r"^\s*\+1\s*$",
    r"^.{1,4}$",                               # very short (≤4 chars)
]


def is_no_reply_candidate(message: str, channel: str = None,
                           group_id: str = None) -> bool:
    """
    Returns True if message is trivially not worth responding to.
    Called BEFORE any model or agent routing to avoid wasteful cost.
    """
    if not (channel == "whatsapp" and group_id):
        return False   # Only applies to group messages

    msg = message.strip()
    for pattern in NO_REPLY_PATTERNS:
        if re.match(pattern, msg, re.IGNORECASE | re.UNICODE):
            return True
    return False


class Router:
    def __init__(self, workspace_path: str = None):
        self.workspace = Path(workspace_path or os.environ.get(
            "DVORAH_WORKSPACE", Path.home() / ".openclaw" / "workspace"))
        self.registry = IntegrationRegistry(str(self.workspace))

        try:
            from core.integration_health import IntegrationHealthMonitor
            self.health_monitor = IntegrationHealthMonitor(str(self.workspace))
        except ImportError:
            self.health_monitor = None

        self.patterns = {

            # PR3: group_retrieval — DM asking *about* a group (not a group message itself)
            "group_retrieval": [
                r"קבוצה.{0,20}(של|ב|מ)",
                r"שיעורי.{0,10}בית",
                r"מה.{0,15}(כתבו|היה|פספסתי|הלך).{0,15}קבוצה",
                r"תסכמי.{0,15}קבוצה",
                r"(כיתה|גן).{0,10}(של|ב)",
                r"מה.{0,10}(קורה|היה).{0,10}(אלון|ניב|ילדים)",
                r"(יש|היה|מה).{0,15}חדש.{0,15}קבוצה",
                r"חדש.{0,10}בקבוצה",
            ],
            "fitness": [
                r"אכלתי|ארוחה|meal|ate",
                r"שקילה|משקל|weight|שקלתי",
                r"קלוריות|קק\"ל|calories|kcal",
                r"דיאטה|diet|תזונה|nutrition",
            ],
            "whatsapp_group": [
                r"group_message",
                r"שלום.*קבוצה|hello.*group",
            ],
            "research": [
                r"תחקרי|חקרי|research|investigate",
                r"בדקי|check|מצאי|find|חפשי",
                r"מה.*עם|what.*about|השוק|market",
                r"איך.*עובד|how.*works|ניתוח|analysis",
            ],
            "marketing": [
                r"פוסט|post|תוכן|content",
                r"טיקטוק|tiktok|instagram|social",
                r"שיווק|marketing|פרסום|advertising",
                r"וילה|villa|lithos|ליתוס",
            ],
            "cost_usage": [
                r"כמה בזבזת|כמה עלו הטוקנים|כמה עלה אנתרופיק",
                r"עלות.*היום|היום.*עלות|כמה.*טוקנ",
                r"token.?cost|usage.*today",
            ],
            "cto": [
                r"מצב.*מערכת|system.*status|system.*health",
                r"openclaw|גרסה.*מערכת|version.*check|גרסה|gateway",
                r"עדכני.*openclaw|עדכון.*מערכת|update.*system",
                r"שגיאות.*מערכת|errors.*system|תקלות",
                r"שיפור.*מערכת|שיפור.*תיקונים|שיפור.*מתיקונים|self.*improve|regression",
                r"health.*check|בריאות.*מערכת|בדיקת.*תקינות",
                r"תיקונים|corrections|דפוסי.*שגיאות|מתיקונים",
            ],

            "scheduling": [
                r"\bמתי\b|\bwhen\b|תזכיר|remind",
                r"פגישה|meeting|appointment",
                r"יומן|calendar|schedule",
            ],
        }

    # ── Model tier selection ──────────────────────────────────────────────────
    # PR1 rule: Opus (tier3) is NEVER selected here.
    # Legal uses tier2 by default.  Escalation to tier3 must go through
    # agent_executor with an explicit justification.
    # ── Domain context files ─────────────────────────────────────────────
    # Maps each domain to state files that provide dynamic per-request context.
    # These are loaded AFTER the static essentials (IDENTITY, SOUL, USER) and
    # appear later in the prompt — so the static prefix stays cached.
    DOMAIN_CONTEXT_FILES: Dict[str, List[str]] = {
        "whatsapp_group":  ["state/KNOWN_GROUPS.md", "state/GROUP_MEMBERS.md", "state/GROUP_MEMORY.md"],
        "group_retrieval": ["state/KNOWN_GROUPS.md", "state/GROUP_MEMBERS.md", "state/GROUP_MEMORY.md"],
        "fitness":         ["state/fitness_tracker.md"],

        "marketing":       ["state/OPEN_TASKS.md", "state/VILLA_LITHOS_PROFILE.md"],
        "research":        ["state/OPEN_TASKS.md"],
        "cto":             ["state/health_check.json", "state/error_digest_latest.json", "state/OPEN_TASKS.md"],
        "scheduling":      ["state/OPEN_TASKS.md"],
        "general":         ["state/OPEN_TASKS.md"],
        "cost_usage":      [],
    }

    DOMAIN_TIERS: Dict[str, str] = {
        "whatsapp_group":   "tier1",   # always cheap
        "cost_usage":       "tier1",
        "group_retrieval":  "tier1",   # retrieval is cheap
        "fitness":          "tier1",
        "research":         "tier2",
        "marketing":        "tier2",
        "cto":              "tier1",
        "scheduling":       "tier1",
        "general":          "tier2",
    }

    def classify_message(self, message: str, channel: str = None,
                         group_id: str = None) -> Dict:
        if channel == "whatsapp" and group_id:
            # ALL group messages go through odya — never treat as DM.
            # Exec approvals and internal commands must NEVER appear in groups.
            # Dvorah mention detection is handled inside odya/group_agent_prompt,
            # not at the routing layer.
            return {
                "domain": "whatsapp_group",
                "confidence": 0.9,
                "agent": "odya",
                "reason": f"WhatsApp group message (channel={channel}, group={group_id})",
            }

        message_lower = message.lower()
        scores: Dict[str, float] = {}

        for domain, patterns in self.patterns.items():
            score = sum(1 for p in patterns
                        if re.search(p, message_lower, re.IGNORECASE))
            if score > 0:
                scores[domain] = score / len(patterns)

        if scores:
            best = max(scores, key=scores.get)
            confidence = min(scores[best] * 2, 1.0)
            agent_map = {

                "fitness":          "dana",
                "whatsapp_group":   "odya",
                "group_retrieval":  "odya",   # DM asking about a group → odya retrieves
                "research":         "tzofit",
                "scheduling":       "gabi",
                "cto":              "gabi",
                "marketing":        "tali",
                "cost_usage":       "cost_reporter",
            }
            return {
                "domain": best,
                "confidence": confidence,
                "agent": agent_map.get(best, "direct"),
                "reason": f"Pattern match: {best} (score: {scores[best]:.2f})",
            }

        return {
            "domain": "general",
            "confidence": 0.3,
            "agent": "direct",
            "reason": "No specific pattern matched — general routing",
        }

    def load_context(self, domain: str, message: str,
                     channel: str = None, group_id: str = None) -> Dict:
        context = {
            "files_loaded": [],
            "integrations_activated": [],
            "context_size": 0,
            "truncated": False,
        }

        essentials = [
            "IDENTITY.md", "SOUL.md", "USER.md",
            "CAPABILITY_INDEX.md",
            "MEMORY_INDEX.md",
            "memory/ACTIVE_CONTEXT.md",
        ]
        for f in essentials:
            content = safe_read_file(f)
            if content and not content.startswith("[ERROR"):
                context["files_loaded"].append(f)

        for f in self.DOMAIN_CONTEXT_FILES.get(domain, []):
            content = safe_read_file(f, max_lines=100)
            if content and not content.startswith("[ERROR"):
                context["files_loaded"].append(f)
                if "[TRUNCATED" in content:
                    context["truncated"] = True

        status = context_status()
        context["context_size"] = status["chars"]

        if status["status"] == "warning":
            context["warning"] = "Approaching context limit"
        elif status["status"] == "critical":
            context["error"] = "Context limit exceeded"

        return context

    def route_message(self, message: str, channel: str = None,
                      group_id: str = None) -> Dict:
        """
        Main routing function.

        PR1: NO_REPLY fast-path runs FIRST.
        If matched → returns no_reply decision with tier=none (cost=$0).
        """
        # ── PR1: NO_REPLY fast-path ───────────────────────────────────────────
        if is_no_reply_candidate(message, channel, group_id):
            return {
                "classification": {
                    "domain": "whatsapp_group",
                    "confidence": 1.0,
                    "agent": "no_reply",
                    "reason": "NO_REPLY fast-path: trivial group message, cost=$0",
                },
                "context": {"files_loaded": [], "context_size": 0},
                "model": "none",                       # no model call
                "routing_decision": {
                    "action": "no_reply",
                    "agent": "no_reply",
                    "domain": "whatsapp_group",
                },
                "metadata": {
                    "channel": channel,
                    "group_id": group_id,
                    "message_length": len(message),
                    "timestamp": __import__("datetime").datetime.now().isoformat(),
                    "pr1_enforcement": "no_reply_fast_path",
                },
            }

        # ── Normal routing ────────────────────────────────────────────────────
        classification = self.classify_message(message, channel, group_id)
        context = self.load_context(classification["domain"], message, channel, group_id)
        # Router only recommends tier — model_selector enforces final decision
        recommended_tier = self.DOMAIN_TIERS.get(classification["domain"], "tier2")

        return {
            "classification": classification,
            "context": context,
            # ADVISORY ONLY — model_selector (core/model_selector.py) makes the final decision
            "model":            recommended_tier,
            "recommended_tier": recommended_tier,
            "routing_decision": {
                "action": "route_to_agent" if classification["agent"] != "direct" else "handle_direct",
                "agent": classification["agent"],
                "domain": classification["domain"],
            },
            "metadata": {
                "channel": channel,
                "group_id": group_id,
                "message_length": len(message),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            },
        }


# ── IntegrationRegistry (unchanged) ──────────────────────────────────────────
class IntegrationRegistry:
    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path)
        registry_file = self.workspace / "core" / "integration_registry.json"
        try:
            with open(registry_file, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except Exception:
            self.config = {"integrations": {}, "rules": {}}

    def get_required_files(self, domain: str) -> List[str]:
        return self.config.get("integrations", {}).get(domain, {}).get("required_files", [])

    def get_capabilities(self, domain: str) -> List[str]:
        return self.config.get("integrations", {}).get(domain, {}).get("capabilities", [])


# ── Global singleton ──────────────────────────────────────────────────────────
router = Router()


def route_message(message: str, channel: str = None, group_id: str = None) -> Dict:
    return router.route_message(message, channel, group_id)
