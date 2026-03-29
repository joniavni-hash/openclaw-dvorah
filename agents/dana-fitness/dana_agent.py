#!/usr/bin/env python3
"""
🏋️ Dana v2 — Body OS reference implementation

Additive implementation so it can be reviewed and adopted safely.
Designed to replace the current placeholder execute path in dana_agent.py.

NOTIFICATION ROUTING (OPS/NOTIFICATION_ROUTING_FIX.md):
  - All Dana reminders MUST route to WhatsApp only
  - Forbidden channels: telegram, email, openai_task_email
  - Never create scheduled email tasks for reminders
"""

# Dana notification routing constants
DANA_PREFERRED_CHANNEL = "whatsapp"
DANA_FORBIDDEN_CHANNELS = ["telegram", "email", "openai_task_email"]
DANA_ALLOWED_CHANNELS = ["whatsapp"]

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent / "_shared"))
sys.path.insert(0, str(Path(__file__).parent))
from domain_agent_base import (
    DomainAgent, FinalPayload, RoutingResult, ModelTier, WORKSPACE
)
from health_bridge import HealthBridge

TRACKER_PATH = WORKSPACE / "state" / "fitness_tracker.md"
PROTEIN_GOAL = 130
CALORIE_GOAL = 1550
TARGET_WEIGHT = 68.0


class DanaAgent(DomainAgent):
    AGENT_NAME = "דנה"
    AGENT_EMOJI = "🏋️"
    DOMAIN = "fitness"

    KEYWORDS = [
        "דיאטה", "משקל", "קלוריות", "קק\"ל", "אימון", "diet", "weight",
        "workout", "שקילה", "שקלתי", "אכלתי", "חלבון", "protein",
        "ארוחה", "ארוחת", "בוקר", "צהריים", "ערב", "חטיף",
        "bmr", "tdee", "כושר", "הליכה", "ריצה", "תרגיל", "התאמנתי",
        "גרם", "סה\"כ", "יעד", "סיכום", "שבועי", "היום", "20 דקות",
        # v2 keywords
        "צעדים", "steps", "ישנתי", "שינה", "גמור", "עייף", "readiness",
        "סיכום יום", "daily close", "adherence", "recovery",
    ]

    TASK_TYPES = {
        # v2 task types — checked first
        "daily_close": {"tier": "tier1", "keywords": ["סיכום יום", "בואי נסגור את היום", "לסגור את היום", "daily close"]},
        "readiness_decision": {"tier": "tier2", "keywords": ["שווה להתאמן", "כוח להתאמן", "ישנתי", "גמור", "עייף", "recovery", "readiness"]},
        "health_sync": {"tier": "tier1", "keywords": ["צעדים", "steps", "health sync", "apple"]},
        "weekly_review_v2": {"tier": "tier2", "keywords": ["מה מצב השבוע", "review שבועי", "שבוע שלי", "adherence", "weekly coaching"]},
        # v1 task types
        "meal_log": {"tier": "tier1", "keywords": ["אכלתי", "ארוחה", "ארוחת"]},
        "weight_log": {"tier": "tier1", "keywords": ["שקלתי", "שקילה", "משקל"]},
        "workout_log": {"tier": "tier1", "keywords": ["התאמנתי", "רצתי", "הלכתי", "אימון שעשיתי"]},
        "calorie_query": {"tier": "tier1", "keywords": ["כמה קלוריות", "כמה חלבון", "קק\"ל"]},
        "daily_status": {"tier": "tier1", "keywords": ["איפה אני עומד היום", "מה נשאר לי", "סטטוס יומי"]},
        "daily_summary": {"tier": "tier1", "keywords": ["סכמי לי את היום", "סיכום יומי", "איך היום הלך"]},
        "weekly_review": {"tier": "tier2", "keywords": ["סיכום שבועי", "סיכום שבוע", "למה אני תקוע"]},
        "workout_decision": {"tier": "tier2", "keywords": ["להתאמן עכשיו", "יש לי רק", "20 דקות", "אין לי כוח"]},
        "plan_adjustment": {"tier": "tier2", "keywords": ["לשנות תוכנית", "להתאים", "adjust"]},
        "nutrition_plan": {"tier": "tier3", "keywords": ["תוכנית תזונה", "דיאטה חדשה"]},
    }

    def __init__(self):
        super().__init__()
        self.health_bridge = HealthBridge()

    FOOD_DB = {
        "ביצה": {"kcal": 78, "protein": 6, "type": "unit"},
        "ביצים": {"kcal": 78, "protein": 6, "type": "unit"},
        "חזה עוף": {"kcal": 165, "protein": 31, "type": "100g"},
        "עוף": {"kcal": 165, "protein": 31, "type": "100g"},
        "אורז": {"kcal": 130, "protein": 2.7, "type": "100g"},
        "סלט": {"kcal": 35, "protein": 1.5, "type": "default"},
        "טחינה": {"kcal": 90, "protein": 3, "type": "tbsp"},
        "שמן זית": {"kcal": 120, "protein": 0, "type": "tbsp"},
        "יוגורט": {"kcal": 90, "protein": 9, "type": "cup"},
        "קוטג": {"kcal": 110, "protein": 14, "type": "cup"},
        "לחם": {"kcal": 80, "protein": 3, "type": "slice"},
        "אגוז": {"kcal": 26, "protein": 0.6, "type": "unit"},
        "אגוזי מלך": {"kcal": 26, "protein": 0.6, "type": "unit"},
        "בננה": {"kcal": 105, "protein": 1.3, "type": "unit"},
        "טונה": {"kcal": 120, "protein": 26, "type": "can"},
        "יוגורט חלבון": {"kcal": 120, "protein": 20, "type": "cup"},
        "פרגית": {"kcal": 210, "protein": 26, "type": "100g"},
        "פיצה": {"kcal": 285, "protein": 12, "type": "slice"},
        "גבינה": {"kcal": 100, "protein": 7, "type": "slice"},
        "חלב": {"kcal": 100, "protein": 8, "type": "cup"},
        "תפוח": {"kcal": 95, "protein": 0.5, "type": "unit"},
    }

    def can_handle(self, message: str, context: Dict, attachments: List[str] = None) -> RoutingResult:
        score = self.keyword_match(message)
        if re.search(r'(שקלתי|אכלתי|התאמנתי|הלכתי|רצתי)\s', message):
            score = max(score, 0.92)
        if re.search(r'(ביצים?|עוף|סלט|אורז|לחם|יוגורט|קוטג|פיצה|חלבון)', message):
            score = max(score, 0.75)
        task_type = self._classify_task(message)
        tier = self._get_tier_for_task(task_type)
        return RoutingResult(
            can_handle=score >= 0.3,
            confidence=score,
            domain=self.DOMAIN,
            tier=tier,
            estimated_cost_usd=self.estimate_cost(tier),
            reason=f"Fitness task: {task_type} → {tier.value}",
        )

    def execute(self, message: str, context: Dict, attachments: List[str] = None) -> FinalPayload:
        self._start_timer()
        task_type = self._classify_task(message)
        tier = self._get_tier_for_task(task_type)
        tracker_data = self._load_tracker()
        entries = self._parse_tracker_entries(tracker_data)

        # v2: auto-ingest health signals for health_sync
        if task_type == "health_sync":
            parsed = self.health_bridge.parse_from_message(message)
            if parsed.get("date"):
                self.health_bridge.upsert_day(parsed)

        final_text, output_contract = self._build_response(task_type, message, entries)
        write_acts = self._build_write_actions(task_type, message)
        model_used = self._resolve_model(context)

        return FinalPayload(
            status="ok",
            agent=self.AGENT_NAME,
            final_text=final_text,
            should_send=True,
            requires_approval=False,
            write_actions=write_acts,
            metadata={
                "model_used": model_used,
                "model_reason": f"fitness/{task_type} — {tier.value}",
                "output_mode": "direct_send",
                "output_contract": output_contract,
                "task_type": task_type,
                "tracker_loaded": tracker_data is not None,
                "duration_ms": self._elapsed_ms(),
            },
        )

    def _build_response(self, task_type: str, message: str, entries: List[Dict]) -> Tuple[str, str]:
        # v2 task types
        if task_type == "daily_close":
            return self._build_daily_close(message, entries), "daily_close"
        if task_type == "readiness_decision":
            return self._build_readiness(message, entries), "readiness_decision"
        if task_type == "health_sync":
            return self._build_health_sync(message, entries), "health_sync"
        if task_type == "weekly_review_v2":
            return self._build_weekly_review_v2(entries), "weekly_review_v2"
        # v1 task types
        if task_type in ("meal_log", "calorie_query"):
            return self._build_meal_response(message), "meal_analysis"
        if task_type == "weight_log":
            return self._build_weight_response(message, entries), "weight_log"
        if task_type == "workout_log":
            return self._build_workout_log_response(message), "workout_log"
        if task_type == "daily_status":
            return self._build_daily_status_response(entries), "daily_status"
        if task_type == "daily_summary":
            return self._build_daily_summary_response(entries), "daily_summary"
        if task_type == "weekly_review":
            return self._build_weekly_review_response(entries), "weekly_review"
        if task_type == "workout_decision":
            return self._build_workout_decision_response(message, entries), "workout_decision"
        if task_type == "nutrition_plan":
            return self._build_nutrition_plan_response(entries), "nutrition_plan"
        return self._build_daily_status_response(entries), "daily_status"

    # ── v2 builders ──────────────────────────────────────────────────────────

    def _build_daily_close(self, message: str, entries: List[Dict]) -> str:
        state = self._compute_daily_state(entries)
        health_today = self.health_bridge.get_today()
        steps = health_today.get("steps", "?")
        workout = "כן" if health_today.get("workouts_count", 0) > 0 or state["training_status"] == "בוצע" else "לא"
        return (
            f"🌙 סיכום יום\n\n"
            f"חלבון: {state['protein_status']}g / {PROTEIN_GOAL}g\n"
            f"קלוריות: {state['calorie_status']} / {CALORIE_GOAL}\n"
            f"אימון: {workout}\n"
            f"צעדים: {steps}\n\n"
            f"✅ מה הלך טוב: {state['what_went_well']}\n"
            f"⚠️ מה פגע: {state['what_hurt_progress']}\n"
            f"📌 מחר: {state['tomorrow_focus']}\n"
            f"💡 הצעד הטוב ביותר עכשיו: {state['best_next_action']}"
        )

    def _build_readiness(self, message: str, entries: List[Dict]) -> str:
        r = self.health_bridge.compute_readiness(message)
        state_he = {"push_day": "push_day — יום לדחוף", "maintain_day": "maintain_day — שמירה", "recovery_day": "recovery_day — שחזור"}
        train_he = "כן" if r["should_train_today"] else "לא"
        if r["recommended_intensity"] == "low" and r["should_train_today"]:
            train_he = "כן-אבל-קל"
        intensity_he = {"high": "גבוהה", "medium": "בינונית", "low": "נמוכה", "rest": "מנוחה"}.get(r["recommended_intensity"], r["recommended_intensity"])
        return (
            f"🔋 Readiness Check\n\n"
            f"מצב: {state_he.get(r['readiness_state'], r['readiness_state'])}\n"
            f"להתאמן היום: {train_he}\n"
            f"עצימות מומלצת: {intensity_he}\n"
            f"משך: {r['recommended_duration']} דקות\n"
            f"Fallback: {r['fallback_option']}\n"
            f"מיקוד תזונה היום: {r['nutrition_priority_today']}\n\n"
            f"💬 {r['reasoning']}"
        )

    def _build_health_sync(self, message: str, entries: List[Dict]) -> str:
        parsed = self.health_bridge.parse_from_message(message)
        d = parsed.get("date", "?")
        lines = [f"📡 Health Sync\n\nנרשם ל-{d}:"]
        if parsed.get("steps"):
            lines.append(f"- צעדים: {parsed['steps']}")
        if parsed.get("sleep_hours"):
            lines.append(f"- שינה: {parsed['sleep_hours']} שעות")
        if parsed.get("workouts_count"):
            lines.append(f"- אימון: {parsed.get('workout_minutes', 30)} דקות")
        if parsed.get("weight"):
            lines.append(f"- משקל: {parsed['weight']} ק\"ג")
        if parsed.get("distance_km"):
            lines.append(f"- מרחק: {parsed['distance_km']} ק\"מ")
        lines.append("\n✅ סטטוס עודכן")
        return "\n".join(lines)

    def _build_weekly_review_v2(self, entries: List[Dict]) -> str:
        days = self.health_bridge.get_last_n_days(7)

        # Weight trend
        weights = [d["weight"] for d in reversed(days) if d.get("weight")]
        if len(weights) >= 2:
            delta = round(weights[-1] - weights[0], 1)
            weight_text = f"{weights[0]} → {weights[-1]} ({delta:+} ק\"ג)"
        elif len(weights) == 1:
            weight_text = f"{weights[0]} ק\"ג (שקילה אחת)"
        else:
            weight_text = "אין שקילות השבוע"

        # Workout consistency
        total_workouts = sum(d.get("workouts_count", 0) for d in days)
        workout_score = min(1.0, total_workouts / 3.0)

        # Steps consistency (days with 8000+)
        days_8k = sum(1 for d in days if d.get("steps", 0) >= 8000)
        steps_score = days_8k / max(len(days), 1)

        # Protein consistency from tracker entries
        cutoff = datetime.now() - timedelta(days=7)
        week_entries = [e for e in entries if e['dt'] >= cutoff]
        meal_entries = [e for e in week_entries if e.get('meal')]
        daily_protein: Dict[str, float] = {}
        for e in meal_entries:
            d_key = e['dt'].date().isoformat()
            daily_protein[d_key] = daily_protein.get(d_key, 0) + e['meal'].get('estimated_protein', 0)
        good_protein_days = sum(1 for v in daily_protein.values() if v >= 100)
        protein_score = good_protein_days / 7.0
        avg_protein = int(sum(daily_protein.values()) / max(1, len(daily_protein))) if daily_protein else 0

        # Adherence
        adherence = round((workout_score + steps_score + protein_score) / 3 * 100)

        # Strongest / weakest
        scores = {"אימונים": workout_score, "צעדים": steps_score, "חלבון": protein_score}
        strongest = max(scores, key=scores.get)
        weakest = min(scores, key=scores.get)

        # One change
        changes = {
            "אימונים": "להכניס 2-3 אימוני fallback קצרים לשבוע",
            "צעדים": "לצאת להליכה של 20 דקות כל יום אחרי צהריים",
            "חלבון": "לפתוח כל יום עם ארוחת חלבון ברורה (30g+)",
        }
        one_change = changes.get(weakest, "לשמור על עקביות")

        return (
            f"📈 Weekly Review v2\n\n"
            f"⚖️ משקל: {weight_text}\n"
            f"🏃 אימונים: {total_workouts}/7 (score: {workout_score:.2f})\n"
            f"👣 צעדים: {days_8k} ימים עם 8k+ (score: {steps_score:.2f})\n"
            f"🥩 חלבון: ~{avg_protein}g ממוצע (score: {protein_score:.2f})\n"
            f"📊 Adherence: {adherence}%\n\n"
            f"💪 הרגל חזק: {strongest}\n"
            f"🔴 הדלף הגדול: {weakest}\n"
            f"🎯 שינוי אחד לשבוע הבא: {one_change}"
        )

    # ── v1 builders ──────────────────────────────────────────────────────────

    def _build_meal_response(self, message: str) -> str:
        struct = self._estimate_meal(message)
        items_text = "\n".join(f"- {item['name']}: ~{item['kcal']} קק\"ל, ~{item['protein']}g חלבון" for item in struct["items"])
        return (
            f"🍽️ ניתוח ארוחה\n\n"
            f"רכיבים:\n{items_text or '- לא זיהיתי רכיבים ברורים'}\n\n"
            f"חלבון מוערך: ~{struct['estimated_protein']}g\n"
            f"קלוריות מוערכות: ~{struct['estimated_calories']} קק\"ל\n"
            f"פסק דין: {struct['verdict']}\n"
            f"מה חסר: {struct['what_missing']}\n"
            f"מהלך הבא: {struct['next_best_move']}"
        )

    def _build_weight_response(self, message: str, entries: List[Dict]) -> str:
        m = re.search(r'(\d+[\.,]?\d*)', message)
        kg = float(m.group(1).replace(',', '.')) if m else None
        previous_weights = [e['weight'] for e in entries if e.get('weight') is not None]
        prev = previous_weights[-1] if previous_weights else None
        delta = round(kg - prev, 1) if kg is not None and prev is not None else None
        to_goal = round(kg - TARGET_WEIGHT, 1) if kg is not None else None
        delta_text = f"{delta:+} ק\"ג מהשקילה הקודמת" if delta is not None else "אין שקילה קודמת להשוואה"
        goal_text = f"{to_goal:+} ק\"ג מהיעד" if to_goal is not None else "יעד לא זמין"
        return (
            f"⚖️ שקילה נרשמה\n\n"
            f"משקל: {kg if kg is not None else '?'} ק\"ג\n"
            f"מגמה: {delta_text}\n"
            f"יעד: {goal_text}\n"
            f"הצעד הבא: ממשיכים לעקוב, לא משנים יום על בסיס שקילה אחת."
        )

    def _build_workout_log_response(self, message: str) -> str:
        return (
            f"🏋️ אימון נרשם\n\n"
            f"מה נרשם: {message}\n"
            f"פסק דין: טוב לשמירה על עקביות\n"
            f"הצעד הבא: להוסיף ארוחה עם חלבון טוב אם עוד לא נכנסה היום."
        )

    def _build_daily_status_response(self, entries: List[Dict]) -> str:
        state = self._compute_daily_state(entries)
        return (
            f"📍 סטטוס יומי\n\n"
            f"אימון: {state['training_status']}\n"
            f"חלבון: ~{state['protein_status']}g / {PROTEIN_GOAL}g\n"
            f"קלוריות: ~{state['calorie_status']} / {CALORIE_GOAL}\n"
            f"ציון יום: {state['day_score']}/10\n"
            f"מה נשאר להיום: {state['what_left_today']}\n"
            f"הצעד הבא: {state['best_next_action']}"
        )

    def _build_daily_summary_response(self, entries: List[Dict]) -> str:
        state = self._compute_daily_state(entries)
        return (
            f"🌙 סיכום יום\n\n"
            f"מה הלך טוב: {state['what_went_well']}\n"
            f"מה פגע: {state['what_hurt_progress']}\n"
            f"ציון: {state['day_score']}/10\n"
            f"מיקוד למחר: {state['tomorrow_focus']}"
        )

    def _build_weekly_review_response(self, entries: List[Dict]) -> str:
        review = self._compute_weekly_review(entries)
        return (
            f"📈 Weekly Body Review\n\n"
            f"מגמת משקל: {review['weight_trend']}\n"
            f"עקביות: {review['adherence']}\n"
            f"חלבון: {review['protein_consistency']}\n"
            f"אימונים: {review['workout_consistency']}\n"
            f"הבעיה המרכזית: {review['biggest_issue']}\n"
            f"השינוי הבא: {review['best_next_change']}"
        )

    def _build_workout_decision_response(self, message: str, entries: List[Dict]) -> str:
        decision = self._compute_workout_decision(message, entries)
        return (
            f"🏃 החלטת אימון\n\n"
            f"להתאמן היום: {decision['train_today']}\n"
            f"אימון מומלץ: {decision['recommended_session']}\n"
            f"משך: {decision['duration']}\n"
            f"עצימות: {decision['intensity']}\n"
            f"Fallback: {decision['fallback_option']}"
        )

    def _build_nutrition_plan_response(self, entries: List[Dict]) -> str:
        review = self._compute_weekly_review(entries)
        return (
            f"🥗 כיוון תזונתי\n\n"
            f"יעד יומי: {CALORIE_GOAL} קק\"ל / {PROTEIN_GOAL}g חלבון\n"
            f"מה הכי חשוב כרגע: {review['biggest_issue']}\n"
            f"פוקוס יומי: 3 ארוחות עם חלבון ברור + לא להשאיר את כל החלבון לערב\n"
            f"מהלך ראשון: {review['best_next_change']}"
        )

    def _build_write_actions(self, task_type: str, message: str) -> list:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        if task_type in ("meal_log", "weight_log", "workout_log"):
            return [{
                "type": "append_file",
                "path": "state/fitness_tracker.md",
                "content": f"\n## {ts}\n{message}\n",
            }]
        return []

    def _classify_task(self, message: str) -> str:
        msg = message.lower()
        for task_type, config in self.TASK_TYPES.items():
            if any(kw in msg for kw in config["keywords"]):
                return task_type
        if re.search(r'(שקלתי|שקילה)', msg):
            return "weight_log"
        if re.search(r'(אכלתי|ארוחה)', msg):
            return "meal_log"
        if re.search(r'(התאמנתי|רצתי|הלכתי)', msg):
            return "workout_log"
        if re.search(r'(שווה להתאמן|20 דקות|אין לי כוח)', msg):
            return "workout_decision"
        if re.search(r'(סיכום שבועי|תקוע)', msg):
            return "weekly_review"
        if re.search(r'(סכמי לי את היום|סיכום יומי)', msg):
            return "daily_summary"
        if re.search(r'(איפה אני עומד היום|מה נשאר לי)', msg):
            return "daily_status"
        return "calorie_query"

    def _get_tier_for_task(self, task_type: str) -> ModelTier:
        config = self.TASK_TYPES.get(task_type, {})
        tier_str = config.get("tier", "tier1")
        return {
            "tier1": ModelTier.TIER1_CHEAP,
            "tier2": ModelTier.TIER2_MID,
            "tier3": ModelTier.TIER3_PREMIUM,
        }.get(tier_str, ModelTier.TIER1_CHEAP)

    def _load_tracker(self) -> Optional[str]:
        try:
            return TRACKER_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    def _parse_tracker_entries(self, tracker_data: Optional[str]) -> List[Dict]:
        if not tracker_data:
            return []
        entries: List[Dict] = []
        pattern = re.compile(r'^##\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*$')
        current_dt = None
        current_lines: List[str] = []
        for line in tracker_data.splitlines():
            m = pattern.match(line.strip())
            if m:
                if current_dt is not None and current_lines:
                    entries.append(self._make_entry(current_dt, " ".join(current_lines).strip()))
                current_dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
                current_lines = []
            elif current_dt is not None and line.strip():
                current_lines.append(line.strip())
        if current_dt is not None and current_lines:
            entries.append(self._make_entry(current_dt, " ".join(current_lines).strip()))
        return entries

    def _make_entry(self, dt: datetime, text: str) -> Dict:
        weight_match = re.search(r'(?:שקלתי|משקל)\s*(\d+[\.,]?\d*)', text)
        weight = float(weight_match.group(1).replace(',', '.')) if weight_match else None
        meal = self._estimate_meal(text) if ('אכלתי' in text or 'ארוחה' in text) else None
        workout = bool(re.search(r'(התאמנתי|רצתי|הלכתי|אימון)', text))
        return {"dt": dt, "text": text, "weight": weight, "meal": meal, "workout": workout}

    def _estimate_meal(self, message: str) -> Dict:
        msg = message.lower()
        items = []
        total_kcal = 0
        total_protein = 0.0
        for name, data in self.FOOD_DB.items():
            if name in msg:
                qty = self._infer_quantity(msg, name, data["type"])
                kcal = round(data["kcal"] * qty)
                protein = round(data["protein"] * qty, 1)
                items.append({"name": name, "qty": qty, "kcal": kcal, "protein": protein})
                total_kcal += kcal
                total_protein += protein
        verdict = "ארוחה טובה" if total_protein >= 25 else "ארוחה חלשה יחסית בחלבון"
        if total_kcal > 700:
            verdict = "ארוחה כבדה"
        what_missing = "חלבון" if total_protein < 25 else "איזון בהמשך היום"
        next_best_move = (
            "בארוחה הבאה להכניס חלבון נקי של 25-40g" if total_protein < 25 else "להמשיך יום נקי, לא לבזבז קלוריות על נשנושים"
        )
        return {
            "items": items,
            "estimated_calories": int(total_kcal),
            "estimated_protein": int(round(total_protein)),
            "verdict": verdict,
            "what_missing": what_missing,
            "next_best_move": next_best_move,
        }

    def _infer_quantity(self, msg: str, name: str, unit_type: str) -> float:
        if unit_type == "100g":
            patterns = [rf'{re.escape(name)}\s*(\d+)\s*גרם', rf'(\d+)\s*גרם\s*{re.escape(name)}']
            for p in patterns:
                m = re.search(p, msg)
                if m:
                    return max(0.5, float(m.group(1)) / 100.0)
            return 1.5
        if unit_type == "unit":
            if 'ביצ' in name:
                m = re.search(r'(\d+)\s*ביצ', msg)
                return float(m.group(1)) if m else 1.0
            m = re.search(r'(\d+)\s*' + re.escape(name), msg)
            return float(m.group(1)) if m else 1.0
        if unit_type == "tbsp":
            m = re.search(r'(\d+)\s*כפ', msg)
            return float(m.group(1)) if m and name in msg else 1.0
        if unit_type == "slice":
            m = re.search(r'(\d+)\s*פרוס', msg)
            return float(m.group(1)) if m else 1.0
        return 1.0

    def _compute_daily_state(self, entries: List[Dict]) -> Dict:
        today = datetime.now().date()
        today_entries = [e for e in entries if e['dt'].date() == today]
        protein = sum((e.get('meal') or {}).get('estimated_protein', 0) for e in today_entries)
        calories = sum((e.get('meal') or {}).get('estimated_calories', 0) for e in today_entries)
        trained = any(e.get('workout') for e in today_entries)
        protein_ratio = min(1.0, protein / PROTEIN_GOAL) if PROTEIN_GOAL else 0
        calorie_ratio = min(1.0, calories / CALORIE_GOAL) if CALORIE_GOAL else 0
        day_score = int(round((protein_ratio * 6) + (2 if trained else 0) + (2 if calorie_ratio <= 1.0 else 0)))
        what_left = []
        if protein < PROTEIN_GOAL:
            what_left.append(f"עוד ~{max(0, PROTEIN_GOAL - protein)}g חלבון")
        if not trained:
            what_left.append("להכניס תנועה / אימון קצר")
        if not what_left:
            what_left.append("רק לסגור את היום נקי")
        what_went_well = "היום במסלול" if protein >= 80 or trained else "יש עוד עבודה על היום"
        what_hurt = "חלבון נמוך מדי" if protein < 80 else ("לא נכנסה תנועה" if not trained else "מעט מדי structured meals")
        tomorrow_focus = "לפתוח את היום עם חלבון ברור" if protein < PROTEIN_GOAL else "לשמר את אותו קו גם מחר"
        best_next_action = "ארוחה עם 25-40g חלבון" if protein < PROTEIN_GOAL else ("אימון קצר של 20-30 דק'" if not trained else "לא לחרב את הערב")
        return {
            "training_status": "בוצע" if trained else "לא בוצע עדיין",
            "protein_status": int(protein),
            "calorie_status": int(calories),
            "day_score": max(1, min(10, day_score)),
            "what_left_today": ", ".join(what_left),
            "best_next_action": best_next_action,
            "what_went_well": what_went_well,
            "what_hurt_progress": what_hurt,
            "tomorrow_focus": tomorrow_focus,
        }

    def _compute_weekly_review(self, entries: List[Dict]) -> Dict:
        cutoff = datetime.now() - timedelta(days=7)
        week_entries = [e for e in entries if e['dt'] >= cutoff]
        meal_entries = [e for e in week_entries if e.get('meal')]
        workout_entries = [e for e in week_entries if e.get('workout')]
        avg_protein = 0
        if meal_entries:
            daily = {}
            for e in meal_entries:
                daily.setdefault(e['dt'].date(), 0)
                daily[e['dt'].date()] += e['meal'].get('estimated_protein', 0)
            avg_protein = sum(daily.values()) / max(1, len(daily))
        weights = [e['weight'] for e in week_entries if e.get('weight') is not None]
        if len(weights) >= 2:
            diff = round(weights[-1] - weights[0], 1)
            weight_trend = f"{weights[0]} → {weights[-1]} ק\"ג ({diff:+})"
        elif len(weights) == 1:
            weight_trend = f"שקילה אחת בלבד השבוע: {weights[0]} ק\"ג"
        else:
            weight_trend = "אין מספיק שקילות השבוע"
        adherence = f"{len(meal_entries)} ארוחות מתועדות, {len(workout_entries)} אימונים/פעילויות"
        protein_consistency = f"~{int(avg_protein)}g חלבון בממוצע ליום"
        workout_consistency = f"{len(workout_entries)} אימונים/פעילויות ב-7 ימים"
        biggest_issue = "עקביות חלבון" if avg_protein < 100 else ("מעט מדי תנועה" if len(workout_entries) < 2 else "להדק שגרה, לא להתרופף")
        best_next_change = ("לסגור כל יום לפחות עם 2 עוגני חלבון ברורים" if avg_protein < 100 else "לקבע 2-3 אימוני fallback קצרים בשבוע")
        return {
            "weight_trend": weight_trend,
            "adherence": adherence,
            "protein_consistency": protein_consistency,
            "workout_consistency": workout_consistency,
            "biggest_issue": biggest_issue,
            "best_next_change": best_next_change,
        }

    def _compute_workout_decision(self, message: str, entries: List[Dict]) -> Dict:
        msg = message.lower()
        tired = any(x in msg for x in ["אין לי כוח", "עייף", "עייפ", "מותש"])
        short = re.search(r'(\d+)\s*דק', msg)
        minutes = int(short.group(1)) if short else None
        today = datetime.now().date()
        trained_today = any(e.get('workout') and e['dt'].date() == today for e in entries)
        if trained_today:
            return {"train_today": "לא חייב", "recommended_session": "כבר יש תנועה היום", "duration": "0-20 דקות", "intensity": "קל", "fallback_option": "הליכה קצרה / מוביליטי"}
        if tired:
            return {"train_today": "כן, אבל קל", "recommended_session": "אימון קצר / הליכה מהירה", "duration": f"{minutes or 20} דקות", "intensity": "נמוכה-בינונית", "fallback_option": "10 דקות הליכה + 10 דקות גוף"}
        if minutes and minutes <= 25:
            return {"train_today": "כן", "recommended_session": "אימון fallback יעיל", "duration": f"{minutes} דקות", "intensity": "בינונית", "fallback_option": "20 דקות הליכה מהירה אם אין כוח"}
        return {"train_today": "כן", "recommended_session": "אימון כוח קצר או הליכה מהירה", "duration": "30-45 דקות", "intensity": "בינונית", "fallback_option": "20 דקות אם היום צפוף"}

    def _resolve_model(self, context: Dict) -> str:
        decision = context.get("model_decision") or {}
        if isinstance(decision, dict) and decision.get("model"):
            return decision["model"]
        return "anthropic/claude-sonnet-4-20250514"
