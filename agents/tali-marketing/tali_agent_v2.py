#!/usr/bin/env python3
"""
🏖️ Tali v2 — reference implementation

This file is intentionally additive so it can be reviewed and adopted safely.
It is designed to replace the current placeholder execute path in tali_agent.py.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "_shared"))
from domain_agent_base import DomainAgent, FinalPayload, RoutingResult, ModelTier, WORKSPACE

LARRY_SYSTEM = WORKSPACE / "villa-lithos-tiktok" / "larry-system"
MARKETING_ROOT = WORKSPACE / "workspace" / "villa-lithos"


class TaliAgent(DomainAgent):
    AGENT_NAME = "טלי"
    AGENT_EMOJI = "🏖️"
    DOMAIN = "marketing"

    KEYWORDS = [
        "villa", "וילה", "lithos", "ליתוס", "tiktok", "טיקטוק",
        "instagram", "אינסטגרם", "facebook", "פייסבוק", "pinterest", "פינטרסט",
        "postiz", "פוסט", "post", "hook", "הוק", "caption", "כיתוב",
        "carousel", "קרוסלה", "reel", "ריל", "marketing", "שיווק",
        "content", "תוכן", "analytics", "ביצועים", "views", "צפיות",
        "engagement", "larry", "לארי", "campaign", "קמפיין",
    ]

    TASK_TYPES = {
        "status_check": {"tier": "tier1", "keywords": ["status", "מצב", "מה הסטטוס"]},
        "caption_gen": {"tier": "tier1", "keywords": ["caption", "כיתוב", "טקסט לפוסט"]},
        "hook_variation": {"tier": "tier1", "keywords": ["hook", "הוק", "variation", "וריאציה"]},
        "visual_brief": {"tier": "tier1", "keywords": ["brief", "בריף", "קרוסלה", "carousel", "thumbnail", "שוטים"]},
        "schedule_post": {"tier": "tier1", "keywords": ["schedule", "תזמן", "לפרסם", "publish"]},
        "performance_check": {"tier": "tier2", "keywords": ["analytics", "ביצועים", "צפיות", "performance"]},
        "ab_test": {"tier": "tier2", "keywords": ["a/b", "test", "מבחן", "compare"]},
        "content_strategy": {"tier": "tier2", "keywords": ["strategy", "אסטרטגיה", "תוכנית תוכן"]},
        "campaign_plan": {"tier": "tier3", "keywords": ["campaign", "קמפיין", "תוכנית שיווק"]},
        "audience_research": {"tier": "tier3", "keywords": ["audience", "קהל", "research"]},
    }

    def can_handle(self, message: str, context: Dict, attachments: List[str] = None) -> RoutingResult:
        score = self.keyword_match(message)
        if re.search(r'(villa\s*lithos|וילה\s*ליתוס)', message, re.IGNORECASE):
            score = max(score, 0.95)
        if re.search(r'(tiktok|instagram|facebook|pinterest|postiz|פוסט)', message, re.IGNORECASE):
            score = max(score, 0.7)

        task_type = self._classify_task(message)
        tier = self._get_tier(task_type)
        return RoutingResult(
            can_handle=score >= 0.3,
            confidence=score,
            domain=self.DOMAIN,
            tier=tier,
            estimated_cost_usd=self.estimate_cost(tier),
            reason=f"Marketing task: {task_type} → {tier.value}",
        )

    def execute(self, message: str, context: dict, attachments=None):
        task_type = self._classify_task(message)
        platform = self._extract_platform(message)
        hook_data = self._load_hook_data()
        config = self._load_config()
        approval_required = task_type in {"schedule_post", "campaign_plan", "content_strategy"}
        model_used = self._resolve_model(context)

        final_text, output_mode = self._build_response(task_type, message, platform, hook_data, config)

        return FinalPayload(
            status="needs_approval" if approval_required else "ok",
            agent=self.AGENT_NAME,
            final_text=final_text,
            should_send=not approval_required,
            requires_approval=approval_required,
            metadata={
                "model_used": model_used,
                "model_reason": f"marketing/{task_type}",
                "output_mode": "draft_for_approval" if approval_required else "direct_send",
                "task_type": task_type,
                "platform": platform,
                "output_contract": output_mode,
                "assets_root": str(MARKETING_ROOT / "assets"),
                "publishing_hub": "postiz",
                "analytics_available": bool(hook_data),
            },
        )

    def _build_response(self, task_type: str, message: str, platform: str, hook_data: Optional[dict], config: Optional[dict]) -> Tuple[str, str]:
        if task_type == "caption_gen":
            return self._caption_response(message, platform), "content_ready"
        if task_type == "hook_variation":
            return self._hooks_response(message, platform), "content_ready"
        if task_type == "visual_brief":
            return self._visual_brief_response(message, platform), "asset_brief_ready"
        if task_type == "performance_check":
            return self._performance_response(platform, hook_data), "performance_analysis_ready"
        if task_type == "content_strategy":
            return self._weekly_plan_response(platform), "calendar_ready"
        if task_type == "schedule_post":
            return self._publish_draft_response(message, platform), "publish_draft_ready"
        if task_type == "campaign_plan":
            return self._campaign_plan_response(platform), "calendar_ready"
        if task_type == "audience_research":
            return self._audience_research_response(platform), "performance_analysis_ready"
        return self._status_response(platform, hook_data, config), "content_ready"

    def _caption_response(self, message: str, platform: str) -> str:
        return (
            f"כיתוב מוכן ל-{platform}:\n"
            f"וילה ליתוס, המקום שבו השקיעה עושה את כל העבודה 🌅\n"
            f"אם אתם מחפשים חופשה שקטה עם נוף שנשאר בראש, זה המקום.\n\n"
            f"CTA: שלחו הודעה לפרטים וזמינות.\n"
            f"האשטגים: #VillaLithos #{platform.replace(' ', '')} #GreekEscape"
        )

    def _hooks_response(self, message: str, platform: str) -> str:
        hooks = [
            "המקום הזה מרגיש לא אמיתי",
            "אם אתם צריכים חופשה אחת טובה השנה, זו כנראה היא",
            "3 שניות פנימה ואתם כבר רוצים להזמין",
            "הנוף הזה עושה 80% מהשיווק לבד",
            "לא עוד וילה יפה, אלא וילה שאנשים זוכרים",
        ]
        return "הוקים מומלצים:\n- " + "\n- ".join(hooks)

    def _visual_brief_response(self, message: str, platform: str) -> str:
        return (
            f"בריף ויזואלי ל-{platform}:\n"
            f"• פתיח: שוט רחב של הנוף / הבריכה\n"
            f"• אמצע: 3 פריימים קצרים של חלל, שולחן, שקיעה\n"
            f"• סיום: CTA על המסך - 'בדקו זמינות'\n"
            f"• Thumbnail text: 'הנוף שיגרום לכם להזמין'"
        )

    def _performance_response(self, platform: str, hook_data: Optional[dict]) -> str:
        if not hook_data:
            return f"אין עדיין נתוני ביצועים מסודרים ל-{platform}.\nהמלצה: להתחיל לעקוב אחרי hooks, views ו-saves."
        top_hint = hook_data.get("top_hook") or "ויזואל פתיחה חזק + שקיעה"
        return (
            f"סיכום ביצועים ל-{platform}:\n"
            f"• Hook מוביל: {top_hint}\n"
            f"• מה להמשיך: פתיח קצר + נוף + CTA רך\n"
            f"• ניסוי הבא: 3 וריאציות הוק על אותו ויזואל"
        )

    def _weekly_plan_response(self, platform: str) -> str:
        return (
            f"תכנית תוכן שבועית ל-{platform}:\n"
            f"1. Reel: שקיעה + hook רגשי\n"
            f"2. Carousel: 5 סיבות לבחור בוילה\n"
            f"3. UGC-style clip: בוקר/קפה/בריכה\n"
            f"4. Post: המלצת סוף שבוע + CTA\n"
            f"5. Story/Pin: availability push"
        )

    def _publish_draft_response(self, message: str, platform: str) -> str:
        return (
            f"טיוטת פרסום מוכנה ל-{platform}:\n"
            f"• Caption: מוכן\n"
            f"• Asset refs: נדרש לבחור וידאו/תמונה\n"
            f"• זמן מומלץ: 19:00\n"
            f"• Hub: Postiz\n"
            f"מוכן לאישור לפני תזמון."
        )

    def _campaign_plan_response(self, platform: str) -> str:
        return (
            f"טיוטת קמפיין ל-{platform}:\n"
            f"• Goal: יותר פניות ישירות\n"
            f"• Angle: חופשת בוטיק עם נוף\n"
            f"• Content buckets: שקיעה / חללים / חוויית אירוח\n"
            f"• CTA: בדיקת זמינות / שליחת הודעה"
        )

    def _audience_research_response(self, platform: str) -> str:
        return (
            f"מחקר קהל ראשוני ל-{platform}:\n"
            f"• קהל סביר: זוגות, חופשות קצרות, מחפשי וילות פרימיום\n"
            f"• זוויות שעובדות: רוגע, פרטיות, נוף, escape\n"
            f"• בדיקה הבאה: איזה angle מביא יותר save/share"
        )

    def _status_response(self, platform: str, hook_data: Optional[dict], config: Optional[dict]) -> str:
        return (
            f"סטטוס טלי: מוכנה לעבוד על {platform}.\n"
            f"• Hook data: {'זמין' if hook_data else 'לא זמין'}\n"
            f"• Config: {'זמין' if config else 'לא זמין'}\n"
            f"• Publishing hub: Postiz"
        )

    def _classify_task(self, message: str) -> str:
        msg = message.lower()
        for task_type, config in self.TASK_TYPES.items():
            if any(kw in msg for kw in config["keywords"]):
                return task_type
        return "status_check"

    def _get_tier(self, task_type: str) -> ModelTier:
        config = self.TASK_TYPES.get(task_type, {})
        tier_str = config.get("tier", "tier1")
        return {
            "tier1": ModelTier.TIER1_CHEAP,
            "tier2": ModelTier.TIER2_MID,
            "tier3": ModelTier.TIER3_PREMIUM,
        }.get(tier_str, ModelTier.TIER1_CHEAP)

    def _extract_platform(self, message: str) -> str:
        msg = message.lower()
        if "pinterest" in msg or "פינטרסט" in msg:
            return "Pinterest"
        if "facebook" in msg or "פייסבוק" in msg:
            return "Facebook"
        if "instagram" in msg or "אינסטגרם" in msg:
            return "Instagram"
        if "tiktok" in msg or "טיקטוק" in msg:
            return "TikTok"
        return "Instagram"

    def _resolve_model(self, context: Dict) -> str:
        decision = context.get("model_decision") or {}
        if isinstance(decision, dict) and decision.get("model"):
            return decision["model"]
        return "anthropic/claude-sonnet-4-20250514"

    def _load_hook_data(self) -> Optional[dict]:
        try:
            return json.loads((LARRY_SYSTEM / "hooks" / "hook-performance.json").read_text(encoding="utf-8"))
        except Exception:
            return None

    def _load_config(self) -> Optional[dict]:
        try:
            return json.loads((LARRY_SYSTEM / "config" / "villa-lithos.json").read_text(encoding="utf-8"))
        except Exception:
            return None
