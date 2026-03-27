#!/usr/bin/env python3
"""
🏋️ דנה (Dana) — Fitness Domain Agent

Handles: diet tracking, weight monitoring, calorie calculation, exercise planning.
Integrates with: state/fitness_tracker.md, HEARTBEAT.md schedules.

Multi-tier routing:
- Tier 1 (70-85%): meal logging, calorie lookup, weight recording, simple Q&A
- Tier 2 (10-25%): weekly analysis, plan adjustments, trend detection
- Tier 3 (5-10%): comprehensive nutrition planning, complex dietary analysis
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add shared module
sys.path.insert(0, str(Path(__file__).parent.parent / "_shared"))
from domain_agent_base import (
    DomainAgent, AgentOutput, FinalPayload, RoutingResult, ModelTier, WORKSPACE
)

TRACKER_PATH = WORKSPACE / "state" / "fitness_tracker.md"


class DanaAgent(DomainAgent):
    """Fitness and nutrition domain agent."""
    
    AGENT_NAME = "דנה"
    AGENT_EMOJI = "🏋️"
    DOMAIN = "fitness"
    KEYWORDS = [
        "דיאטה", "משקל", "קלוריות", "קק\"ל", "אימון", "diet", "weight",
        "workout", "שקילה", "שקלתי", "אכלתי", "חלבון", "protein",
        "ארוחה", "ארוחת", "בוקר", "צהריים", "ערב", "חטיף",
        "BMR", "TDEE", "כושר", "הליכה", "ריצה", "תרגיל",
        "גרם", "סה\"כ", "תקציב", "יעד", "68",
    ]
    
    # Fitness-specific complexity thresholds
    TIER2_THRESHOLD = 40
    TIER3_THRESHOLD = 70
    
    # Task types for routing
    TASK_TYPES = {
        "meal_log": {"tier": "tier1", "keywords": ["אכלתי", "ארוחה", "ארוחת"]},
        "weight_log": {"tier": "tier1", "keywords": ["שקלתי", "שקילה", "משקל"]},
        "calorie_query": {"tier": "tier1", "keywords": ["כמה קלוריות", "קק\"ל"]},
        "daily_summary": {"tier": "tier1", "keywords": ["סה\"כ היום", "סיכום יומי"]},
        "weekly_analysis": {"tier": "tier2", "keywords": ["סיכום שבועי", "מגמה", "trend"]},
        "plan_adjustment": {"tier": "tier2", "keywords": ["לשנות תוכנית", "להתאים", "adjust"]},
        "nutrition_plan": {"tier": "tier3", "keywords": ["תוכנית תזונה", "דיאטה חדשה"]},
        "exercise_plan": {"tier": "tier2", "keywords": ["תוכנית אימונים", "אימון"]},
    }
    
    def can_handle(self, message: str, context: Dict, attachments: List[str] = None) -> RoutingResult:
        """Check if this is a fitness-related request."""
        score = self.keyword_match(message)
        
        # Boost for self-reporting patterns
        if re.search(r'(שקלתי|אכלתי|התאמנתי|הלכתי|רצתי)\s', message):
            score = max(score, 0.9)
        
        # Boost for meal descriptions
        if re.search(r'(ביצים?|עוף|סלט|אורז|לחם|חלב|יוגורט|קוטג)', message):
            score = max(score, 0.7)
        
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
    
    def execute(self, message: str, context: Dict,
                attachments: List[str] = None) -> FinalPayload:
        """PR2: returns FinalPayload with real final_text."""
        self._start_timer()
        task_type   = self._classify_task(message)
        tier        = self._get_tier_for_task(task_type)
        tracker_data = self._load_tracker()
        final_text  = self._build_final_text(task_type, message, tracker_data)
        write_acts  = self._build_write_actions(task_type, message)

        return FinalPayload(
            status="ok",
            agent=self.AGENT_NAME,
            final_text=final_text,
            should_send=True,
            requires_approval=False,
            write_actions=write_acts,
            metadata={
                "model_used":   "anthropic/claude-sonnet-4-20250514",
                "model_reason": f"fitness/{task_type} — {tier.value}",
                "output_mode":  "direct_send",
                "task_type":    task_type,
                "duration_ms":  self._elapsed_ms(),
            },
        )

    def _build_final_text(self, task_type: str, message: str,
                          tracker_data: Optional[str]) -> str:
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        if task_type == "weight_log":
            # extract number if present
            m = re.search(r'(\d+[\.,]?\d*)', message)
            kg = m.group(1).replace(',', '.') if m else "?"
            return f"✅ שקילה נרשמה: {kg} ק\"ג ({ts})"
        if task_type in ("meal_log", "calorie_query"):
            return (
                f"✅ ארוחה נרשמה ({ts})\n"
                f"{message}\n"
                "(קלוריות וחלבון — ממתין לחישוב מודל)"
            )
        if task_type == "daily_summary":
            return "📊 סיכום יומי — ממתין לנתוני מעקב."
        if task_type == "weekly_analysis":
            return "📈 ניתוח שבועי — ממתין לנתוני מעקב."
        return f"✅ {self.AGENT_NAME}: {message} ({ts})"

    def _build_write_actions(self, task_type: str, message: str) -> list:
        from datetime import datetime
        if task_type in ("meal_log", "weight_log"):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            return [{
                "type":    "append_file",
                "path":    "state/fitness_tracker.md",
                "content": f"\n## {ts}\n{message}\n",
            }]
        return []

    def process(self, message: str, context: Dict, attachments: List[str] = None) -> AgentOutput:
        """Legacy — not used in PR2 pipeline."""
        self._start_timer()
        task_type = self._classify_task(message)
        tier = self._get_tier_for_task(task_type)
        tracker_data = self._load_tracker()
        prompt = self._build_prompt(task_type, message, tracker_data, context)
        return AgentOutput(
            decision="complete",
            confidence=0.85,
            domain=self.DOMAIN,
            agent_name=self.AGENT_NAME,
            model_tier=tier.value,
            cost_usd=self.estimate_cost(tier),
            summary=f"Fitness task processed: {task_type}",
            details=prompt,
            draft={
                "type": task_type,
                "prompt": prompt,
                "tracker_loaded": tracker_data is not None,
                "tier": tier.value,
            },
            tools_used=["read"],
            duration_ms=self._elapsed_ms(),
            qa_result="pass",
        )
    
    def _classify_task(self, message: str) -> str:
        """Classify the fitness task type."""
        msg = message.lower()
        for task_type, config in self.TASK_TYPES.items():
            if any(kw in msg for kw in config["keywords"]):
                return task_type
        
        # Fallback classification
        if re.search(r'(שקלתי|שקילה)', msg):
            return "weight_log"
        if re.search(r'(אכלתי|ארוחה)', msg):
            return "meal_log"
        if re.search(r'(כמה|קלוריות)', msg):
            return "calorie_query"
        
        return "calorie_query"  # default
    
    def _get_tier_for_task(self, task_type: str) -> ModelTier:
        """Get the model tier for a task type."""
        config = self.TASK_TYPES.get(task_type, {})
        tier_str = config.get("tier", "tier1")
        return {
            "tier1": ModelTier.TIER1_CHEAP,
            "tier2": ModelTier.TIER2_MID,
            "tier3": ModelTier.TIER3_PREMIUM,
        }.get(tier_str, ModelTier.TIER1_CHEAP)
    
    def _load_tracker(self) -> Optional[str]:
        """Load the fitness tracker file."""
        try:
            return TRACKER_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
    
    def _build_prompt(self, task_type: str, message: str, tracker_data: Optional[str], context: Dict) -> str:
        """Build the prompt for the fitness task."""
        base = f"""You are דנה (Dana), a fitness tracking assistant working under Dvorah.
Task: {task_type}
User message: {message}

Current tracker data:
{tracker_data or 'No tracker data available.'}

Guidelines:
- Budget: 1,550 kcal/day, 130g protein
- Target weight: 68 kg
- BMR: ~1,575 | TDEE: ~1,900
- Be precise with calorie and protein estimates
- Use Israeli food database knowledge
- Format output for easy tracking
"""
        
        task_prompts = {
            "meal_log": """
Calculate calories and protein for the reported meal.
Return: food items, kcal estimate, protein estimate, running daily total.
Format as table row matching fitness_tracker.md format.""",
            
            "weight_log": """
Record the weight. Calculate change from last weigh-in and from start.
Provide brief trend analysis.""",
            
            "calorie_query": """
Look up or estimate calories and protein for the food items mentioned.
Be specific with portion sizes.""",
            
            "daily_summary": """
Sum up today's intake from logged meals.
Compare to budget (1,550 kcal / 130g protein).
Flag if over/under.""",
            
            "weekly_analysis": """
Analyze this week's data:
- Average daily calories and protein
- Weight trend
- Adherence to budget
- Recommendations for next week""",
            
            "plan_adjustment": """
Based on current progress and tracking data, recommend adjustments.
Consider: weight trend, calorie adherence, protein targets, activity level.""",
            
            "nutrition_plan": """
Create a comprehensive nutrition plan considering:
- Current stats and goals
- Food preferences (from tracking history)
- Protein distribution across meals
- Practical meal suggestions""",
            
            "exercise_plan": """
Design an exercise plan considering:
- Current activity level (walking 1-2x/week)
- Weight loss goal
- Time availability
- Progressive overload""",
        }
        
        return base + task_prompts.get(task_type, "")


def test_dana():
    """Test Dana agent."""
    dana = DanaAgent()
    print(f"Agent: {dana}")
    
    tests = [
        "אכלתי חזה עוף 200 גרם עם אורז",
        "שקלתי 71.8",
        "כמה קלוריות יש בביצה קשה?",
        "מה מזג האוויר?",
        "סיכום שבועי של הדיאטה",
    ]
    
    for msg in tests:
        result = dana.can_handle(msg, {"sender": "yoni"})
        print(f"\n'{msg}'")
        print(f"  Can handle: {result.can_handle} (conf: {result.confidence:.2f})")
        print(f"  Tier: {result.tier.value}, Cost: ${result.estimated_cost_usd:.4f}")


if __name__ == "__main__":
    test_dana()
