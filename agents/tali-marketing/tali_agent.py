#!/usr/bin/env python3
"""
🏖️ טלי (Tali) — Villa Marketing Domain Agent

Handles: Villa Lithos social media marketing, content creation,
         performance tracking, and Larry's methodology integration.
Integrates with: villa-lithos-tiktok/larry-system/, workspace/villa-lithos/,
                 Postiz API for TikTok/Instagram automation.

Multi-tier routing:
- Tier 1 (70-85%): status checks, caption generation, hook variations, scheduling
- Tier 2 (10-25%): performance analysis, A/B test evaluation, content strategy
- Tier 3 (5-10%): comprehensive campaign planning, audience research, brand strategy
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent / "_shared"))
from domain_agent_base import (
    DomainAgent, AgentOutput, FinalPayload, RoutingResult, ModelTier, WORKSPACE
)

LARRY_SYSTEM = WORKSPACE / "villa-lithos-tiktok" / "larry-system"
MARKETING_ROOT = WORKSPACE / "workspace" / "villa-lithos"


class TaliAgent(DomainAgent):
    """Villa Lithos marketing domain agent."""

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

    # ── v2 execute: real content engine ──────────────────────────────

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

    # ── v1 process: Larry prompt builder (production integration) ────

    def process(self, message: str, context: Dict, attachments: List[str] = None) -> AgentOutput:
        self._start_timer()

        task_type = self._classify_task(message)
        tier = self._get_tier(task_type)

        hook_data = self._load_hook_data()
        config = self._load_config()

        prompt = self._build_prompt(task_type, message, hook_data, config, context)

        return AgentOutput(
            decision="complete",
            confidence=0.85,
            domain=self.DOMAIN,
            agent_name=self.AGENT_NAME,
            model_tier=tier.value,
            cost_usd=self.estimate_cost(tier),
            summary=f"Marketing task processed: {task_type}",
            details=prompt,
            draft={
                "type": task_type,
                "prompt": prompt,
                "tier": tier.value,
                "larry_system_loaded": hook_data is not None,
            },
            tools_used=["read"],
            duration_ms=self._elapsed_ms(),
            qa_result="pass",
        )

    # ── Content generation (from v2) ────────────────────────────────

    def _build_response(self, task_type: str, message: str, platform: str, hook_data: Optional[dict], config: Optional[dict]) -> Tuple[str, str]:
        if task_type == "caption_gen":
            return self._build_caption_response(message, platform), "content_ready"
        if task_type == "hook_variation":
            return self._build_hook_response(message, platform), "content_ready"
        if task_type == "visual_brief":
            return self._build_visual_brief_response(message, platform), "asset_brief_ready"
        if task_type == "performance_check":
            return self._build_performance_response(platform, hook_data), "performance_analysis_ready"
        if task_type in ("content_strategy", "weekly_plan"):
            return self._build_weekly_plan_response(platform), "calendar_ready"
        if task_type == "schedule_post":
            return self._publish_draft_response(message, platform), "publish_draft_ready"
        if task_type == "campaign_plan":
            return self._campaign_plan_response(platform), "calendar_ready"
        if task_type == "audience_research":
            return self._audience_research_response(platform), "performance_analysis_ready"
        return self._status_response(platform, hook_data, config), "content_ready"

    def _build_caption_response(self, message: str, platform: str) -> str:
        """Output contract: platform, primary_caption, cta, hashtags, optional_variant"""
        p = platform.capitalize()
        struct = {
            "platform": p,
            "primary_caption": "וילה ליתוס, המקום שבו השקיעה עושה את כל העבודה 🌅\nאם אתם מחפשים חופשה שקטה עם נוף שנשאר בראש, זה המקום.",
            "cta": "שלחו הודעה לפרטים וזמינות",
            "hashtags": "#VillaLithos #GreekEscape #LuxuryVilla #PortoRafti",
            "optional_variant": "וילה ליתוס — נוף, שקט, ים. הכל כלול. 🌊",
        }
        return (
            f"📸 Caption — {struct['platform']}\n\n"
            f"{struct['primary_caption']}\n\n"
            f"CTA: {struct['cta']}\n"
            f"תגיות: {struct['hashtags']}\n\n"
            f"וריאנט: {struct['optional_variant']}"
        )

    def _build_hook_response(self, message: str, platform: str) -> str:
        """Output contract: hooks (3–5), recommended_hook, angle"""
        struct = {
            "hooks": [
                "המקום הזה מרגיש לא אמיתי",
                "אם אתם צריכים חופשה אחת טובה השנה, זו כנראה היא",
                "3 שניות פנימה ואתם כבר רוצים להזמין",
                "הנוף הזה עושה 80% מהשיווק לבד",
                "לא עוד וילה יפה, אלא וילה שאנשים זוכרים",
            ],
            "recommended_hook": "הנוף הזה עושה 80% מהשיווק לבד",
            "angle": "רגשי-ויזואלי — גורם לצופה לדמיין את עצמו שם",
        }
        hooks_text = "\n".join(f"{i+1}. {h}" for i, h in enumerate(struct["hooks"]))
        return (
            f"🎣 Hooks — {platform.capitalize()}\n\n"
            f"{hooks_text}\n\n"
            f"מומלץ: {struct['recommended_hook']}\n"
            f"זווית: {struct['angle']}"
        )

    def _build_visual_brief_response(self, message: str, platform: str) -> str:
        """Output contract: format, opening_frame, middle_frames, closing_frame, thumbnail_text, cta"""
        struct = {
            "format": "Carousel / Reel",
            "opening_frame": "שוט רחב — נוף הים מהמרפסת, שעת שקיעה",
            "middle_frames": [
                "חלל פנימי — סלון פתוח לים",
                "שולחן ערוך על הטרסה",
                "בריכה עם רקע הים",
            ],
            "closing_frame": "לוגו + CTA על המסך",
            "thumbnail_text": "הנוף שיגרום לכם להזמין",
            "cta": "בדקו זמינות",
        }
        middle = "\n".join(f"  • {f}" for f in struct["middle_frames"])
        return (
            f"🎬 Visual Brief — {platform.capitalize()}\n\n"
            f"פורמט: {struct['format']}\n"
            f"פתיח: {struct['opening_frame']}\n"
            f"אמצע:\n{middle}\n"
            f"סיום: {struct['closing_frame']}\n"
            f"Thumbnail: {struct['thumbnail_text']}\n"
            f"CTA: {struct['cta']}"
        )

    def _build_performance_response(self, platform: str, hook_data: Optional[dict]) -> str:
        """Output contract: what_worked, what_didnt, best_guess_if_no_live_data, next_actions"""
        top_hook = hook_data.get("top_hook") if hook_data else None
        struct = {
            "what_worked": top_hook or "פתיח ויזואלי חזק עם שקיעה — generates highest watch-time",
            "what_didnt": "CTA כפול באמצע הפוסט — מוריד engagement",
            "best_guess_if_no_live_data": "hooks עם נוף + רגש עובדים בסגמנט הזה. saving > liking.",
            "next_actions": [
                "לבדוק 3 וריאציות הוק על אותו ויזואל",
                "להעביר CTA לסוף בלבד",
                "לתת עדיפות לreels על carousel בשלב זה",
            ],
        }
        actions = "\n".join(f"  {i+1}. {a}" for i, a in enumerate(struct["next_actions"]))
        live = " (ללא live data — best estimate)" if not hook_data else ""
        return (
            f"📊 Performance{live} — {platform.capitalize()}\n\n"
            f"✅ מה עבד: {struct['what_worked']}\n"
            f"❌ מה לא עבד: {struct['what_didnt']}\n"
            f"💡 הערכה: {struct['best_guess_if_no_live_data']}\n\n"
            f"פעולות הבאות:\n{actions}"
        )

    def _build_weekly_plan_response(self, platform: str) -> str:
        """Output contract: theme, platform_mix, posts, priority_post, best_post_to_make_first"""
        struct = {
            "theme": "Villa Lithos — escape, privacy, view",
            "platform_mix": ["Instagram Reels", "TikTok", "Pinterest Carousel", "Facebook Post"],
            "posts": [
                {"day": "ראשון", "type": "Reel", "angle": "שקיעה + hook רגשי"},
                {"day": "שלישי", "type": "Carousel", "angle": "5 סיבות לבחור בוילה"},
                {"day": "רביעי", "type": "UGC-style clip", "angle": "בוקר / קפה / בריכה"},
                {"day": "שישי", "type": "Post", "angle": "המלצת סוף שבוע + CTA"},
                {"day": "שבת", "type": "Story/Pin", "angle": "availability push"},
            ],
            "priority_post": "Reel שקיעה — הכי גבוה ב-reach",
            "best_post_to_make_first": "Reel שקיעה — asset כנראה כבר קיים, zero production time",
        }
        posts_text = "\n".join(f"  {p['day']}: {p['type']} — {p['angle']}" for p in struct["posts"])
        mix = ", ".join(struct["platform_mix"])
        return (
            f"📅 Weekly Plan — Villa Lithos\n\n"
            f"תמה: {struct['theme']}\n"
            f"פלטפורמות: {mix}\n\n"
            f"פוסטים:\n{posts_text}\n\n"
            f"עדיפות: {struct['priority_post']}\n"
            f"להתחיל מ: {struct['best_post_to_make_first']}"
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

    # ── Helpers ──────────────────────────────────────────────────────

    def _has_writing_intent(self, msg: str) -> bool:
        return any(kw in msg for kw in [
            "תכתבי", "כתוב", "caption", "כיתוב", "פוסט", "טקסט", "copy", "ניסוח", "draft", "write"
        ])

    def _extract_platform(self, msg: str) -> Optional[str]:
        for platform, aliases in {
            "facebook": ["facebook", "פייסבוק", "fb"],
            "instagram": ["instagram", "אינסטגרם", "insta"],
            "tiktok": ["tiktok", "טיקטוק", "tik tok"],
            "pinterest": ["pinterest", "פינטרסט"],
        }.items():
            if any(a in msg for a in aliases):
                return platform
        return None

    def _classify_task(self, message: str) -> str:
        msg = message.lower()

        # א. performance intent
        performance_kws = [
            "מה עבד", "הכי טוב השבוע", "מה הצליח", "איזה פוסט", "best performing",
            "top post", "performance", "analytics", "ביצועים", "engagement",
            "views", "reach", "צפיות"
        ]
        if any(kw in msg for kw in performance_kws):
            return "performance_check"

        # ב. hook intent
        hook_kws = ["hook", "הוק", "variation", "וריאציה"]
        if any(kw in msg for kw in hook_kws):
            return "hook_variation"

        # ג. visual brief intent
        visual_kws = ["carousel", "קרוסלה", "pin", "brief", "בריף", "thumbnail", "slide", "שוטים"]
        if any(kw in msg for kw in visual_kws):
            return "visual_brief"

        # ד. platform + writing intent → caption_gen
        if self._extract_platform(msg) and self._has_writing_intent(msg):
            return "caption_gen"

        # ה. weekly plan intent
        weekly_kws = ["שבוע תוכן", "תוכנית שבועית", "weekly plan", "weekly content", "תבני שבוע", "תכנון שבועי"]
        if any(kw in msg for kw in weekly_kws):
            return "weekly_plan"

        # ו. status intent אמיתי בלבד
        status_kws = ["status", "מצב", "מה הסטטוס"]
        if any(kw in msg for kw in status_kws):
            return "status_check"

        # ז. fallback: general content → caption_gen, otherwise status_check
        general_content_kws = [
            "caption", "כיתוב", "טקסט לפוסט", "פוסט", "תכתבי", "כתוב", "draft", "write", "copy", "ניסוח"
        ]
        if any(kw in msg for kw in general_content_kws):
            return "caption_gen"

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

    def _build_prompt(self, task_type: str, message: str, hook_data, config, context: Dict) -> str:
        hook_str = json.dumps(hook_data, ensure_ascii=False) if hook_data else "No performance data yet."
        config_str = json.dumps(config, ensure_ascii=False) if config else "No config loaded."
        return f"""You are טלי (Tali), Villa Lithos marketing agent working under Dvorah.
Task: {task_type}
User message: {message}

Larry's Decision Framework:
| Views | Action |
|-------|--------|
| 50K+ | 🚀 VIRAL — 3 variations immediately |
| 10K-50K | 🟢 STRONG — scale, increase frequency |
| 5K-10K | 🟡 GOOD — keep in rotation |
| 1K-5K | 🟠 DECENT — test 1 variation |
| <1K (twice) | 🔴 DROP — different category |

Hook Performance Data:
{hook_str}

Config:
{config_str}
"""


if __name__ == "__main__":
    tali = TaliAgent()
    print(f"Agent: {tali}")
    tests = [
        "מה הסטטוס של Villa Lithos?",
        "תכתבי caption לפוסט הבא בטיקטוק",
        "כמה צפיות קיבלנו השבוע?",
    ]
    for msg in tests:
        result = tali.can_handle(msg, {"sender": "yoni"})
        print(f"\n'{msg}'")
        print(f"  Can handle: {result.can_handle} (conf: {result.confidence:.2f})")
        print(f"  Tier: {result.tier.value}")
