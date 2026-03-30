#!/usr/bin/env python3
"""
Model Router — Smart model selection for legal tasks.
Decides which tier (1/2/3) handles each stage of a legal pipeline.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ModelTier(Enum):
    TIER1_CHEAP = "tier1"      # claude-sonnet-4-6
    TIER2_MID = "tier2"        # claude-sonnet-4-6 (enhanced prompting + CoT)
    TIER3_PREMIUM = "tier3"    # claude-sonnet-4-6 (default) or Opus via env var


# Actual model identifiers for API calls
# Note: actual model used for Tier 3 is controlled by OPENCLAW_TIER3_MODEL env var
# in model_client.py. These are for cost estimation only.
TIER_TO_MODEL = {
    ModelTier.TIER1_CHEAP: "anthropic/claude-sonnet-4-6",
    ModelTier.TIER2_MID: "anthropic/claude-sonnet-4-6",
    ModelTier.TIER3_PREMIUM: "anthropic/claude-sonnet-4-6",
}

# Cost per 1M tokens (input, output) in USD — all Sonnet now
TIER_COSTS = {
    ModelTier.TIER1_CHEAP: (3.0, 15.0),
    ModelTier.TIER2_MID: (3.0, 15.0),
    ModelTier.TIER3_PREMIUM: (3.0, 15.0),
}


@dataclass
class RoutingDecision:
    """Result of the model routing decision."""
    tier: ModelTier
    model: str
    reason: str
    confidence: float  # 0-1: how confident we are this tier is sufficient
    complexity_score: int  # 0-100
    risk_level: str  # low/medium/high/critical
    escalation_triggers: List[str] = field(default_factory=list)  # What could cause escalation
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "tier": self.tier.value,
            "model": self.model,
            "reason": self.reason,
            "confidence": self.confidence,
            "complexity_score": self.complexity_score,
            "risk_level": self.risk_level,
            "escalation_triggers": self.escalation_triggers,
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 4),
        }


class ModelRouter:
    """
    Routes legal tasks to the appropriate model tier based on:
    - Task complexity
    - Input length
    - Risk level
    - Document type
    - Ambiguity detection
    - Explicit user preferences
    """

    # Complexity indicators that push toward higher tiers
    HIGH_COMPLEXITY_INDICATORS = [
        r'multi.?party', r'מרובי צדדים',
        r'cross.?border', r'בינלאומי', r'חוצה גבולות',
        r'regulatory', r'רגולטורי', r'רגולציה',
        r'litigation', r'תביעה', r'ליטיגציה',
        r'm&a', r'מיזוג', r'רכישה', r'acquisition',
        r'securities', r'ניירות ערך',
        r'arbitration', r'בוררות',
        r'class.?action', r'ייצוגית',
        r'antitrust', r'הגבלים עסקיים',
        r'gdpr|data.?protection|הגנת מידע',
    ]

    AMBIGUITY_MARKERS = [
        r'reasonable\s+efforts?', r'מאמץ סביר',
        r'in\s+due\s+course', r'בזמן המתאים',
        r'best\s+endeavo[u]?rs?', r'מיטב המאמצים',
        r'material\s+adverse', r'שינוי מהותי',
        r'to\s+the\s+extent\s+permitted', r'במידה המותרת',
        r'at\s+its\s+sole\s+discretion', r'לפי שיקול דעתו הבלעדי',
        r'as\s+soon\s+as\s+practicable', r'בהקדם האפשרי',
        r'substantially\s+all', r'מרבית',
    ]

    CRITICAL_RISK_INDICATORS = [
        r'unlimited\s+liability', r'חבות בלתי מוגבלת',
        r'personal\s+guarantee', r'ערבות אישית',
        r'irrevocable', r'בלתי חוזר',
        r'punitive\s+damages', r'נזקים עונשיים',
        r'without\s+limitation', r'ללא הגבלה',
        r'indemnif', r'שיפוי',
        r'non.?compete', r'אי.?תחרות',
        r'waiv(e|er)', r'ויתור',
    ]

    # Document length thresholds (approx word count)
    SHORT_DOC = 2000       # ~3 pages
    MEDIUM_DOC = 8000      # ~12 pages
    LONG_DOC = 20000       # ~30 pages
    VERY_LONG_DOC = 50000  # ~75 pages

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self._high_complexity_re = [re.compile(p, re.IGNORECASE) for p in self.HIGH_COMPLEXITY_INDICATORS]
        self._ambiguity_re = [re.compile(p, re.IGNORECASE) for p in self.AMBIGUITY_MARKERS]
        self._critical_risk_re = [re.compile(p, re.IGNORECASE) for p in self.CRITICAL_RISK_INDICATORS]

    def route(
        self,
        task_type: str,
        message: str,
        document_text: Optional[str] = None,
        context: Optional[Dict] = None,
        force_tier: Optional[str] = None,
    ) -> RoutingDecision:
        """
        Main routing function. Analyzes the task and returns a tier decision.
        
        Args:
            task_type: One of the 7 legal workflow types
            message: User's request message
            document_text: Full text of attached document (if any)
            context: Additional context (sender, urgency, etc.)
            force_tier: Override tier (e.g., user said "use Opus")
        
        Returns:
            RoutingDecision with chosen tier, reasoning, and cost estimate
        """
        context = context or {}
        
        # Handle explicit tier override
        if force_tier:
            tier = self._parse_forced_tier(force_tier)
            return self._build_decision(
                tier=tier,
                reason=f"Explicitly requested: {force_tier}",
                confidence=1.0,
                complexity_score=0,
                risk_level="unknown",
                document_text=document_text,
                task_type=task_type,
            )

        # Step 1: Score complexity
        complexity_score = self._score_complexity(task_type, message, document_text, context)
        
        # Step 2: Assess risk level
        risk_level, risk_factors = self._assess_risk(message, document_text)
        
        # Step 3: Detect ambiguity
        ambiguity_count = self._count_ambiguity(message, document_text)
        
        # Step 4: Check document length
        doc_length = len(document_text.split()) if document_text else 0
        
        # Step 5: Route based on all signals
        tier, reason, confidence, escalation_triggers = self._decide_tier(
            task_type=task_type,
            complexity_score=complexity_score,
            risk_level=risk_level,
            risk_factors=risk_factors,
            ambiguity_count=ambiguity_count,
            doc_length=doc_length,
            context=context,
        )

        return self._build_decision(
            tier=tier,
            reason=reason,
            confidence=confidence,
            complexity_score=complexity_score,
            risk_level=risk_level,
            document_text=document_text,
            task_type=task_type,
            escalation_triggers=escalation_triggers,
        )

    def _score_complexity(
        self, task_type: str, message: str, document_text: Optional[str], context: Dict
    ) -> int:
        """Score task complexity from 0-100."""
        score = 0
        combined = f"{message} {document_text or ''}"

        # Base score by task type
        task_base_scores = {
            "clause_extraction": 15,
            "legal_summary": 20,
            "contract_review": 35,
            "risk_analysis": 40,
            "compare_versions": 35,
            "draft_response": 45,
            "negotiation_prep": 50,
        }
        score += task_base_scores.get(task_type, 30)

        # Complexity indicators
        for pattern in self._high_complexity_re:
            if pattern.search(combined):
                score += 8

        # Document length factor
        if document_text:
            word_count = len(document_text.split())
            if word_count > self.VERY_LONG_DOC:
                score += 20
            elif word_count > self.LONG_DOC:
                score += 12
            elif word_count > self.MEDIUM_DOC:
                score += 5

        # Ambiguity factor
        ambiguity_count = self._count_ambiguity(message, document_text)
        score += min(ambiguity_count * 5, 20)

        # Context factors
        if context.get("urgent") or "דחוף" in message:
            score += 5  # Urgency doesn't change complexity much, but flags attention
        if context.get("high_value"):
            score += 10

        return min(score, 100)

    def _assess_risk(self, message: str, document_text: Optional[str]) -> Tuple[str, List[str]]:
        """Assess risk level and identify risk factors."""
        combined = f"{message} {document_text or ''}"
        risk_factors = []

        for pattern in self._critical_risk_re:
            match = pattern.search(combined)
            if match:
                risk_factors.append(match.group())

        if len(risk_factors) >= 3:
            return "critical", risk_factors
        elif len(risk_factors) >= 2:
            return "high", risk_factors
        elif len(risk_factors) >= 1:
            return "medium", risk_factors
        return "low", risk_factors

    def _count_ambiguity(self, message: str, document_text: Optional[str]) -> int:
        """Count ambiguous terms in the text."""
        combined = f"{message} {document_text or ''}"
        count = 0
        for pattern in self._ambiguity_re:
            count += len(pattern.findall(combined))
        return count

    def _decide_tier(
        self,
        task_type: str,
        complexity_score: int,
        risk_level: str,
        risk_factors: List[str],
        ambiguity_count: int,
        doc_length: int,
        context: Dict,
    ) -> Tuple[ModelTier, str, float, List[str]]:
        """
        Core routing logic. Returns (tier, reason, confidence, escalation_triggers).
        """
        escalation_triggers = []
        reasons = []

        # === TIER 3 (Premium) GATES ===
        # These conditions trigger Tier 3 (Sonnet with enhanced prompting).
        # Thresholds raised to reduce unnecessary escalation.
        # Previously Tier 3 was Opus ($15/$75 per 1M), now Sonnet ($3/$15).
        premium_required = False

        if risk_level == "critical" and complexity_score >= 60:
            premium_required = True
            reasons.append(f"Critical risk + high complexity ({complexity_score}): {', '.join(risk_factors[:3])}")

        if complexity_score >= 85:
            premium_required = True
            reasons.append(f"Very high complexity score: {complexity_score}")

        if doc_length > self.VERY_LONG_DOC and task_type in ("contract_review", "risk_analysis") and risk_level in ("high", "critical"):
            premium_required = True
            reasons.append(f"Very long document ({doc_length} words) with high-risk complex analysis")

        if task_type == "draft_response" and risk_level == "critical":
            premium_required = True
            reasons.append("Sensitive drafting with critical risk")

        if premium_required:
            return (
                ModelTier.TIER3_PREMIUM,
                "; ".join(reasons),
                0.95,
                [],
            )

        # === TIER 2 (Mid) CONDITIONS ===
        tier2_needed = False

        if complexity_score >= 55:
            tier2_needed = True
            reasons.append(f"Moderate complexity: {complexity_score}")

        if risk_level in ("high", "medium") and task_type in ("risk_analysis", "contract_review", "negotiation_prep"):
            tier2_needed = True
            reasons.append(f"Risk level {risk_level} for {task_type}")

        if ambiguity_count >= 3:
            tier2_needed = True
            reasons.append(f"Multiple ambiguous terms ({ambiguity_count})")
            escalation_triggers.append("ambiguity_may_require_opus")

        if task_type in ("draft_response", "negotiation_prep") and complexity_score >= 35:
            tier2_needed = True
            reasons.append(f"Creative/strategic task ({task_type}) needs deeper reasoning")

        if doc_length > self.LONG_DOC:
            tier2_needed = True
            reasons.append(f"Long document ({doc_length} words)")
            escalation_triggers.append("doc_length_may_require_opus")

        if tier2_needed:
            # Confidence is lower if there are escalation triggers
            confidence = 0.80 if not escalation_triggers else 0.65
            return (
                ModelTier.TIER2_MID,
                "; ".join(reasons) if reasons else "Standard mid-tier task",
                confidence,
                escalation_triggers,
            )

        # === TIER 1 (Cheap) — Default ===
        # Add escalation triggers for edge cases
        if risk_level == "medium":
            escalation_triggers.append("medium_risk_may_need_tier2")
        if ambiguity_count >= 1:
            escalation_triggers.append("some_ambiguity_detected")

        reason = self._tier1_reason(task_type, complexity_score)
        confidence = 0.90 if not escalation_triggers else 0.75

        return (
            ModelTier.TIER1_CHEAP,
            reason,
            confidence,
            escalation_triggers,
        )

    def _tier1_reason(self, task_type: str, complexity_score: int) -> str:
        """Generate reason for Tier 1 routing."""
        task_reasons = {
            "clause_extraction": "Straightforward extraction task — checklist-based",
            "legal_summary": "Summary/structuring task — well-suited for cheap model",
            "contract_review": f"Standard contract review (complexity {complexity_score})",
            "risk_analysis": f"Basic risk scan (complexity {complexity_score})",
            "compare_versions": "Structural comparison — diff-based approach",
            "draft_response": f"Simple draft (complexity {complexity_score})",
            "negotiation_prep": f"Basic negotiation points (complexity {complexity_score})",
        }
        return task_reasons.get(task_type, f"Standard task (complexity {complexity_score})")

    def _parse_forced_tier(self, force_tier: str) -> ModelTier:
        """Parse a forced tier string."""
        force_lower = force_tier.lower()
        if "opus" in force_lower or "3" in force_lower or "premium" in force_lower:
            return ModelTier.TIER3_PREMIUM
        elif "mid" in force_lower or "2" in force_lower:
            return ModelTier.TIER2_MID
        return ModelTier.TIER1_CHEAP

    def _build_decision(
        self,
        tier: ModelTier,
        reason: str,
        confidence: float,
        complexity_score: int,
        risk_level: str,
        document_text: Optional[str],
        task_type: str,
        escalation_triggers: List[str] = None,
    ) -> RoutingDecision:
        """Build a RoutingDecision with cost estimates."""
        # Estimate tokens
        doc_tokens = len(document_text.split()) * 1.3 if document_text else 500
        prompt_overhead = 2000  # System prompt + formatting
        input_tokens = int(doc_tokens + prompt_overhead)

        output_estimates = {
            "clause_extraction": 1500,
            "legal_summary": 2000,
            "contract_review": 4000,
            "risk_analysis": 3000,
            "compare_versions": 3500,
            "draft_response": 5000,
            "negotiation_prep": 6000,
        }
        output_tokens = output_estimates.get(task_type, 3000)

        # Calculate cost
        input_cost_per_token, output_cost_per_token = TIER_COSTS[tier]
        cost = (input_tokens * input_cost_per_token + output_tokens * output_cost_per_token) / 1_000_000

        return RoutingDecision(
            tier=tier,
            model=TIER_TO_MODEL[tier],
            reason=reason,
            confidence=confidence,
            complexity_score=complexity_score,
            risk_level=risk_level,
            escalation_triggers=escalation_triggers or [],
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens,
            estimated_cost_usd=cost,
        )

    def should_escalate(self, tier1_output: Dict) -> Tuple[bool, Optional[ModelTier], str]:
        """
        After Tier 1 or Tier 2 runs, check if we need to escalate.
        Called by the pipeline engine after each stage.
        
        Args:
            tier1_output: The output from the current tier, including:
                - confidence: float
                - flagged_issues: list of issues detected
                - ambiguity_detected: bool
                - risk_escalation: bool
        
        Returns:
            (should_escalate, target_tier, reason)
        """
        confidence = tier1_output.get("confidence", 1.0)
        flagged = tier1_output.get("flagged_issues", [])
        ambiguity = tier1_output.get("ambiguity_detected", False)
        risk_escalation = tier1_output.get("risk_escalation", False)

        if risk_escalation and confidence < 0.4:
            return True, ModelTier.TIER3_PREMIUM, "Risk escalation flagged by lower tier with low confidence"

        if confidence < 0.3:
            return True, ModelTier.TIER3_PREMIUM, f"Very low confidence ({confidence}) from lower tier"

        if confidence < 0.7 and len(flagged) >= 2:
            return True, ModelTier.TIER2_MID, f"Moderate confidence with {len(flagged)} flagged issues"

        if ambiguity and len(flagged) >= 3:
            return True, ModelTier.TIER2_MID, "Significant ambiguity with multiple issues"

        return False, None, "No escalation needed"


def test_router():
    """Test the model router with sample inputs."""
    router = ModelRouter()

    test_cases = [
        {
            "name": "Simple clause extraction",
            "task_type": "clause_extraction",
            "message": "תמצאי סעיפי תשלום",
            "document_text": "This is a short contract. Payment terms: net 30 days.",
        },
        {
            "name": "Complex multi-party contract",
            "task_type": "contract_review",
            "message": "תסכמי את החוזה הבינלאומי",
            "document_text": "This cross-border multi-party agreement involves unlimited liability, "
                           "personal guarantee requirements, irrevocable commitments, and punitive damages "
                           "provisions. " * 100,
        },
        {
            "name": "Standard risk analysis",
            "task_type": "risk_analysis",
            "message": "מה הסיכונים בהסכם?",
            "document_text": "Standard service agreement with reasonable efforts clause and indemnification. " * 50,
        },
        {
            "name": "Forced Opus",
            "task_type": "contract_review",
            "message": "use Opus for this",
            "document_text": "Short contract.",
        },
    ]

    for tc in test_cases:
        decision = router.route(
            task_type=tc["task_type"],
            message=tc["message"],
            document_text=tc.get("document_text"),
            force_tier="opus" if "Opus" in tc["message"] else None,
        )
        print(f"\n=== {tc['name']} ===")
        print(f"  Tier: {decision.tier.value}")
        print(f"  Model: {decision.model}")
        print(f"  Reason: {decision.reason}")
        print(f"  Confidence: {decision.confidence:.2f}")
        print(f"  Complexity: {decision.complexity_score}")
        print(f"  Risk: {decision.risk_level}")
        print(f"  Est. Cost: ${decision.estimated_cost_usd:.4f}")
        if decision.escalation_triggers:
            print(f"  Escalation triggers: {decision.escalation_triggers}")


if __name__ == "__main__":
    test_router()
