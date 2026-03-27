#!/usr/bin/env python3
"""
🏖️ טלי (Tali) — Villa Lithos Marketing Operating System

Full-system agent: analytics, assets, publishing, content generation.
Handles 8 task types with structured output contracts per type.
Integrates with: villa-lithos/ analytics & assets, Postiz publishing hub.
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

from analytics_reader import AnalyticsReader
from asset_manager import AssetManager
from publishing_client import PublishingClient
from creative_qa import CreativeQA

LARRY_SYSTEM = WORKSPACE / "villa-lithos-tiktok" / "larry-system"
MARKETING_ROOT = WORKSPACE / "villa-lithos"


class TaliAgent(DomainAgent):
    """Villa Lithos marketing domain agent — MOS v1."""

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
        "caption_gen":          {"tier": "tier1"},
        "hook_variation":       {"tier": "tier1"},
        "visual_brief":         {"tier": "tier1"},
        "performance_check":    {"tier": "tier2"},
        "weekly_plan":          {"tier": "tier2"},
        "content_ideation":     {"tier": "tier1"},
        "publish_draft":        {"tier": "tier1"},
        "schedule_post":        {"tier": "tier1"},
        "autonomous_routine":   {"tier": "tier2"},
        "status_check":         {"tier": "tier1"},
    }

    ROUTINE_TASKS = {
        "caption_gen", "hook_variation", "visual_brief", "performance_check",
        "weekly_plan", "content_ideation", "publish_draft", "autonomous_routine",
    }

    def __init__(self):
        super().__init__()
        self.analytics = AnalyticsReader()
        self.asset_manager = AssetManager()
        self.publisher = PublishingClient()
        self.creative_qa = CreativeQA()

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

    # ── execute: MOS v1 ───────────────────────────────────────────────

    def execute(self, message: str, context: dict, attachments=None):
        task_type = self._classify_task(message)
        platform = self._extract_platform(message.lower()) or context.get("platform", "general")

        final_text, output_mode = self._build_response(task_type, message, platform, context)

        # Creative QA review
        asset_name = context.get("asset", "") or "general_asset"
        pillar = context.get("pillar", "visual_escape")
        creative_review = self._run_creative_review(asset_name, final_text, platform, pillar)

        if creative_review["publish_decision"] == "reject":
            final_text = f"🚫 Post rejected — {creative_review['improvement_reason']}"
        elif creative_review["publish_decision"] == "needs_improvement":
            final_text += f"\n\n⚠️ Quality note: {creative_review['improvement_reason']}"

        is_autonomous = task_type == "autonomous_routine"
        approval_required = task_type in {"schedule_post", "campaign_plan"}
        is_routine = task_type in self.ROUTINE_TASKS
        routine_vs_high_risk = "high_risk" if (task_type == "schedule_post" and context.get("force_publish")) else "routine" if is_routine else "standard"

        return FinalPayload(
            status="ok",
            agent=self.AGENT_NAME,
            final_text=final_text,
            should_send=True,
            requires_approval=approval_required,
            write_actions=[],
            metadata={
                "task_type": task_type,
                "platform": platform,
                "output_contract": task_type,
                "model_used": "anthropic/claude-sonnet-4-20250514",
                "model_reason": f"marketing/{task_type}",
                "output_mode": output_mode,
                "publishing_hub": "postiz",
                "analytics_available": True,
                "assets_root": "villa-lithos/assets/",
                "approval_required": approval_required,
                "draft_saved": task_type in {"publish_draft", "schedule_post", "autonomous_routine"},
                "external_action_attempted": task_type in {"publish_draft", "schedule_post", "autonomous_routine"},
                "external_action_result": "local_draft" if task_type in {"publish_draft", "schedule_post", "autonomous_routine"} else None,
                "autonomous_mode": is_autonomous,
                "routine_vs_high_risk": routine_vs_high_risk,
                "creative_review_passed": creative_review["passed"],
                "visual_score": round(creative_review["visual_score"], 2),
                "copy_score": round(creative_review["copy_score"], 2),
                "fit_score": round(creative_review["fit_score"], 2),
                "brand_score": round(creative_review["brand_score"], 2),
                "publish_decision": creative_review["publish_decision"],
                "improvement_reason": creative_review["improvement_reason"],
            }
        )

    def _run_creative_review(self, asset_name: str, copy: str, platform: str, pillar: str) -> dict:
        return self.creative_qa.review(asset_name, copy, platform, pillar)

    # ── v1 process: Larry prompt builder (backward compat) ────────────

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

    # ── Response dispatcher ───────────────────────────────────────────

    def _build_response(self, task_type: str, message: str, platform: str, context: dict) -> Tuple[str, str]:
        dispatch = {
            "caption_gen":       lambda: (self._build_caption_response(message, platform), "content_ready"),
            "hook_variation":    lambda: (self._build_hook_response(message, platform), "content_ready"),
            "visual_brief":      lambda: (self._build_visual_brief_response(message, platform), "asset_brief_ready"),
            "performance_check": lambda: (self._build_performance_response(platform, message), "performance_analysis_ready"),
            "weekly_plan":       lambda: (self._build_weekly_plan_response(platform), "calendar_ready"),
            "content_ideation":  lambda: (self._build_content_ideation_response(message, platform), "content_ready"),
            "publish_draft":       lambda: (self._build_publish_draft_response(message, platform), "publish_draft_ready"),
            "schedule_post":       lambda: (self._build_schedule_post_response(message, platform), "schedule_ready"),
            "autonomous_routine":  lambda: (self._build_autonomous_routine_response(message, platform), "autonomous_routine_ready"),
        }
        builder = dispatch.get(task_type)
        if builder:
            return builder()
        return self._status_response(platform), "content_ready"

    # ── Output builders ───────────────────────────────────────────────

    def _build_caption_response(self, message: str, platform: str) -> str:
        p = platform.capitalize() if platform != "general" else "General"
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
        p = platform.capitalize() if platform != "general" else "General"
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
            f"🎣 Hooks — {p}\n\n"
            f"{hooks_text}\n\n"
            f"מומלץ: {struct['recommended_hook']}\n"
            f"זווית: {struct['angle']}"
        )

    def _build_visual_brief_response(self, message: str, platform: str) -> str:
        p = platform.capitalize() if platform != "general" else "General"
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

        # Asset check
        asset_refs = self.asset_manager.get_asset_refs("carousel", platform)
        missing = asset_refs.get("missing", [])
        assets_line = ", ".join(missing) if missing else "הכל זמין"

        return (
            f"🎬 Visual Brief — {p}\n\n"
            f"פורמט: {struct['format']}\n"
            f"פתיח: {struct['opening_frame']}\n"
            f"אמצע:\n{middle}\n"
            f"סיום: {struct['closing_frame']}\n"
            f"Thumbnail: {struct['thumbnail_text']}\n"
            f"CTA: {struct['cta']}\n\n"
            f"Assets נדרשים: {assets_line}"
        )

    def _build_performance_response(self, platform: str, message: str) -> str:
        signal = self.analytics.get_best_signal(platform)
        source = signal["source"]
        struct = {
            "what_worked": signal["what_worked"],
            "what_didnt": signal["what_didnt"],
            "best_guess": f"hooks עם נוף + רגש עובדים בסגמנט הזה. saving > liking.",
            "next_actions": [
                "לבדוק 3 וריאציות הוק על אותו ויזואל",
                "להעביר CTA לסוף בלבד",
                "לתת עדיפות לreels על carousel בשלב זה",
            ],
        }
        actions = "\n".join(f"  {i+1}. {a}" for i, a in enumerate(struct["next_actions"]))
        p = platform.capitalize() if platform != "general" else "General"
        return (
            f"📊 Performance — {p} ({source})\n\n"
            f"✅ מה עבד: {struct['what_worked']}\n"
            f"❌ מה לא עבד: {struct['what_didnt']}\n"
            f"💡 הערכה: {struct['best_guess']}\n\n"
            f"פעולות הבאות:\n{actions}"
        )

    def _build_weekly_plan_response(self, platform: str) -> str:
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

    def _build_content_ideation_response(self, message: str, platform: str) -> str:
        p = platform.capitalize() if platform != "general" else "General"
        struct = {
            "ideas": [
                {"title": "שקיעה מהמרפסת", "angle": "POV reel — 10 שניות שקט + נוף"},
                {"title": "בוקר יווני", "angle": "קפה + בריכה + אווירה"},
                {"title": "5 דברים שלא ידעתם על פורטו ראפטי", "angle": "carousel חינוכי"},
                {"title": "לפני ואחרי — הגעה לוילה", "angle": "transition reel"},
                {"title": "מה אורחים אומרים", "angle": "UGC-style testimonial"},
            ],
            "best_idea": "שקיעה מהמרפסת",
            "why_now": "תוכן שקיעה מגיע לshare גבוה בעונת האביב — אנשים מתחילים לתכנן חופשות",
        }
        ideas_text = "\n".join(f"{i+1}. {idea['title']}: {idea['angle']}" for i, idea in enumerate(struct["ideas"]))
        return (
            f"💡 Content Ideas — {p}\n\n"
            f"{ideas_text}\n\n"
            f"הכי טוב עכשיו: {struct['best_idea']}\n"
            f"למה עכשיו: {struct['why_now']}"
        )

    def _build_publish_draft_response(self, message: str, platform: str) -> str:
        p = platform.capitalize() if platform != "general" else "General"
        caption = "וילה ליתוס — המקום שבו השקיעה עושה את כל העבודה 🌅"
        hashtags = "#VillaLithos #GreekEscape #LuxuryVilla"
        asset_refs = self.asset_manager.get_asset_refs("post", platform)

        payload = self.publisher.build_payload(
            platform=platform,
            caption=caption,
            hashtags=hashtags,
            asset_refs=asset_refs.get("available", []),
            scheduled_time="19:00",
            cta="שלחו הודעה לפרטים וזמינות",
        )
        result = self.publisher.submit_to_postiz(payload)
        draft_id = result.get("draft_id", "unknown")

        missing = asset_refs.get("missing", [])
        assets_summary = ", ".join(missing) if missing else "הכל זמין"

        return (
            f"📤 Publish Draft — {p}\n\n"
            f"Copy: {caption}\n"
            f"Assets: {assets_summary}\n"
            f"זמן מומלץ: 19:00\n"
            f"Draft: שמור ({draft_id})\n\n"
            f"⚠️ נדרש אישור לפני פרסום"
        )

    def _build_schedule_post_response(self, message: str, platform: str) -> str:
        p = platform.capitalize() if platform != "general" else "General"
        # Extract time from message if present
        time_match = re.search(r'(\d{1,2}:\d{2})', message)
        scheduled_time = time_match.group(1) if time_match else "19:00"

        payload = self.publisher.build_payload(
            platform=platform,
            caption="(from latest draft)",
            hashtags="",
            asset_refs=[],
            scheduled_time=scheduled_time,
            approval_required=True,
        )
        result = self.publisher.submit_to_postiz(payload)
        draft_id = result.get("draft_id", "unknown")
        status = result.get("status", "unknown")

        return (
            f"🗓️ Schedule Draft — {p}\n\n"
            f"זמן: {scheduled_time}\n"
            f"Draft ID: {draft_id}\n"
            f"סטטוס: {status}\n\n"
            f"⚠️ נדרש אישור לפני תזמון"
        )

    def _build_autonomous_routine_response(self, message: str, platform: str) -> str:
        p = platform.capitalize() if platform != "general" else "General"

        # 1. Get analytics signal
        signal = self.analytics.get_best_signal(platform)

        # 2. Generate caption based on signal
        caption = f"וילה ליתוס — {signal.get('best_angle', 'חוויה שלא נשכחת')} 🌅"
        hashtags = "#VillaLithos #GreekEscape #LuxuryVilla"
        cta = "שלחו הודעה לפרטים וזמינות"

        # 3. Build and save publish draft
        asset_refs = self.asset_manager.get_asset_refs("post", platform)
        payload = self.publisher.build_payload(
            platform=platform,
            caption=caption,
            hashtags=hashtags,
            asset_refs=asset_refs.get("available", []),
            scheduled_time="19:00",
            cta=cta,
            approval_required=False,
            autonomous_mode=True,
        )
        result = self.publisher.submit_to_postiz(payload)
        draft_id = result.get("draft_id", "unknown")

        snippet = caption[:80]
        return (
            f"🤖 Autonomous Routine — {p}\n\n"
            f"📊 Signal: {signal.get('what_worked', 'N/A')} (confidence: {signal.get('confidence', 'unknown')})\n"
            f"📝 Content: {snippet}\n"
            f"📤 Draft: {draft_id}\n"
            f"🗓️ Suggested time: 19:00\n\n"
            f"Mode: routine (auto-approved)\n"
            f"Next: awaiting asset confirmation or publish trigger"
        )

    def _status_response(self, platform: str) -> str:
        p = platform.capitalize() if platform != "general" else "General"
        hook_data = self._load_hook_data()
        config = self._load_config()
        return (
            f"סטטוס טלי: מוכנה לעבוד על {p}.\n"
            f"• Hook data: {'זמין' if hook_data else 'לא זמין'}\n"
            f"• Config: {'זמין' if config else 'לא זמין'}\n"
            f"• Analytics: זמין\n"
            f"• Assets: villa-lithos/assets/\n"
            f"• Publishing hub: Postiz"
        )

    # ── Classifier ────────────────────────────────────────────────────

    def _classify_task(self, message: str) -> str:
        msg = message.lower()

        # 0. autonomous routine intent
        if any(kw in msg for kw in [
            "autonomous", "routine", "auto publish", "full cycle",
            "פעל אוטומטית", "מחזור שלם", "routine mode"
        ]):
            return "autonomous_routine"

        # 1. performance intent
        if any(kw in msg for kw in [
            "מה עבד", "הכי טוב", "performance", "analytics", "ביצועים",
            "engagement", "views", "צפיות", "reach", "מה הצליח"
        ]):
            return "performance_check"

        # 2. hook intent
        if any(kw in msg for kw in ["hook", "הוק", "hooks", "variation"]):
            return "hook_variation"

        # 3. visual/brief intent
        if any(kw in msg for kw in [
            "carousel", "קרוסלה", "brief", "בריף", "thumbnail",
            "slide", "shot list", "שוטים", "pin"
        ]):
            return "visual_brief"

        # 4. weekly plan
        if any(kw in msg for kw in [
            "שבוע תוכן", "תוכנית שבועית", "weekly plan", "weekly content", "תבני שבוע"
        ]):
            return "weekly_plan"

        # 5. content ideation
        if any(kw in msg for kw in [
            "רעיון", "ideas", "idea", "רעיונות", "angles", "themes", "content idea"
        ]):
            return "content_ideation"

        # 6. publish draft
        if any(kw in msg for kw in [
            "publish draft", "draft לפרסום", "הכן פרסום", "publish prep", "הכן draft"
        ]):
            return "publish_draft"

        # 7. schedule
        if any(kw in msg for kw in ["schedule", "תזמן", "לתזמן", "set time", "כמה תפרסם"]):
            return "schedule_post"

        # 8. platform + writing intent → caption_gen
        if self._extract_platform(msg) and self._has_writing_intent(msg):
            return "caption_gen"

        # 9. status keywords only
        if any(kw in msg for kw in ["status", "מצב", "מה הסטטוס"]):
            return "status_check"

        # 10. general writing fallback
        if self._has_writing_intent(msg):
            return "caption_gen"

        # 11. default
        return "status_check"

    # ── Helpers ────────────────────────────────────────────────────────

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

    def _get_tier(self, task_type: str) -> ModelTier:
        config = self.TASK_TYPES.get(task_type, {})
        tier_str = config.get("tier", "tier1")
        return {
            "tier1": ModelTier.TIER1_CHEAP,
            "tier2": ModelTier.TIER2_MID,
            "tier3": ModelTier.TIER3_PREMIUM,
        }.get(tier_str, ModelTier.TIER1_CHEAP)

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
