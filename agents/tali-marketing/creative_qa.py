#!/usr/bin/env python3
"""Creative QA — brand scoring, visual/copy/fit gates, pre-schedule review for Villa Lithos."""

import re
from typing import Dict


class CreativeQA:
    """Quality gate for Villa Lithos marketing content before publishing."""

    BRAND_TONE = ["elevated", "calm", "beautiful", "aspirational", "premium", "clean"]
    BRAND_AVOID = ["loud", "cheesy", "generic", "salesy", "low-end"]

    VISUAL_PREFER = ["sunset", "pool", "sea", "view", "interior", "breakfast", "table", "atmosphere", "light", "mood"]
    VISUAL_AVOID = ["clutter", "flat", "random", "low-quality", "weak"]

    COPY_PREFER_PATTERNS = ["short", "evocative", "sensory", "desire"]
    COPY_AVOID_PATTERNS = ["!", "amazing", "don't miss", "best deal", "cheapest", "book now!", "limited time"]

    PLATFORM_PRIORITY = {
        "instagram": "aesthetic_impact",
        "tiktok": "hook_strength",
        "facebook": "clarity_trust",
        "pinterest": "saveability",
    }

    def score_visual(self, asset_name: str, platform: str) -> float:
        if not asset_name or asset_name.strip() == "":
            return 0.2
        name = asset_name.lower()
        if "test" in name or "placeholder" in name:
            return 0.2

        # Real photos (IMG_ prefix) get a curated-photo base
        score = 0.65 if ("img_" in name or "img " in name) else 0.5

        for kw in self.VISUAL_PREFER:
            if kw in name:
                score += 0.15

        for kw in self.VISUAL_AVOID:
            if kw in name:
                score -= 0.2

        if platform == "pinterest" and (name.startswith("pin3_") or "thumbnail" in name):
            score += 0.1

        # sunset/pool/view → 0.85+
        if any(kw in name for kw in ["sunset", "pool", "view"]):
            score = max(score, 0.85)

        # bedroom/kitchen/dining → 0.75 for stay_experience context
        if any(kw in name for kw in ["bedroom", "kitchen", "dining"]):
            score = max(score, 0.75)

        return max(0.0, min(1.0, score))

    def score_copy(self, copy: str, platform: str) -> float:
        if not copy:
            return 0.0
        score = 0.6
        length = len(copy)

        if 50 <= length <= 200:
            score += 0.1
        elif length > 400:
            score -= 0.15
        elif length < 20:
            score -= 0.2

        copy_lower = copy.lower()
        for pattern in self.COPY_AVOID_PATTERNS:
            if pattern.lower() in copy_lower:
                score -= 0.15

        if "villalithosgreece.com" in copy_lower:
            score += 0.1

        # Emoji count
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000026FF]+",
            flags=re.UNICODE,
        )
        emoji_count = len(emoji_pattern.findall(copy))
        if emoji_count > 3:
            score -= 0.1

        # Hashtag count
        hashtag_count = copy.count("#")
        if hashtag_count > 5:
            score -= 0.1

        # Platform-specific
        lines = copy.strip().split("\n")
        first_line = lines[0] if lines else ""

        if platform == "tiktok":
            if len(first_line) < 60:
                score += 0.1
            if not any(kw in copy_lower for kw in ["pov", "wait", "this", "👀", "🤯"]):
                score -= 0.1
        elif platform == "instagram":
            if length < 150:
                score += 0.1
        elif platform == "pinterest":
            if any(kw in copy_lower for kw in ["escape", "dream", "luxury", "view"]):
                score += 0.1
        elif platform == "facebook":
            if any(kw in copy_lower for kw in ["booking", "availability", "זמינות"]):
                score += 0.1

        return max(0.0, min(1.0, score))

    def score_fit(self, asset_name: str, copy: str, platform: str, pillar: str) -> float:
        score = 0.6
        name = asset_name.lower() if asset_name else ""
        copy_lower = copy.lower() if copy else ""
        combined = name + " " + copy_lower

        if pillar == "visual_escape" and any(kw in combined for kw in ["sunset", "pool", "sea"]):
            score += 0.2
        if pillar == "booking_intent" and any(kw in copy_lower for kw in ["availability", "dates", "book"]):
            score += 0.2
        if pillar == "dreaming_aspiration" and any(kw in copy_lower for kw in ["feels", "imagine", "pov", "unreal"]):
            score += 0.2
        if pillar == "stay_experience" and any(kw in combined for kw in ["bedroom", "morning", "breakfast", "interior"]):
            score += 0.2

        # Pinterest mismatch: no vertical asset hint
        if platform == "pinterest" and not any(kw in name for kw in ["pin", "vertical", "portrait"]):
            score -= 0.1

        return max(0.0, min(1.0, score))

    def score_brand(self, copy: str, asset_name: str) -> float:
        score = 0.7
        copy_lower = copy.lower() if copy else ""
        name = asset_name.lower() if asset_name else ""

        for word in self.BRAND_AVOID:
            if word in copy_lower:
                score -= 0.2

        if "villa lithos" in copy_lower or "וילה ליתוס" in copy_lower:
            score += 0.05

        if "villalithosgreece.com" in copy_lower:
            score += 0.1

        if copy and copy.count("!") > 2:
            score -= 0.1

        # ALL CAPS words
        if copy:
            caps_words = [w for w in copy.split() if w.isupper() and len(w) > 1]
            if caps_words:
                score -= 0.15

        if "test" in name or "placeholder" in name:
            score -= 0.3

        return max(0.0, min(1.0, score))

    def review(self, asset_name: str, copy: str, platform: str, pillar: str) -> Dict:
        visual = self.score_visual(asset_name, platform)
        copy_score = self.score_copy(copy, platform)
        fit = self.score_fit(asset_name, copy, platform, pillar)
        brand = self.score_brand(copy, asset_name)

        overall = visual * 0.3 + copy_score * 0.3 + fit * 0.2 + brand * 0.2

        # Decision logic — hard reject gate for very low visual
        if visual < 0.30:
            decision = "reject"
            passed = False
            reason = f"Below threshold — lowest: visual ({visual:.2f})"
        elif overall >= 0.70 and visual >= 0.60 and copy_score >= 0.60:
            decision = "publish"
            passed = True
            reason = ""
        elif overall >= 0.50 or visual >= 0.55 or copy_score >= 0.55:
            decision = "needs_improvement"
            passed = False
            scores = {"visual": visual, "copy": copy_score, "fit": fit, "brand": brand}
            lowest = min(scores, key=scores.get)
            reason = f"Lowest dimension: {lowest} ({scores[lowest]:.2f})"
        else:
            decision = "reject"
            passed = False
            scores = {"visual": visual, "copy": copy_score, "fit": fit, "brand": brand}
            lowest = min(scores, key=scores.get)
            reason = f"Below threshold — lowest: {lowest} ({scores[lowest]:.2f})"

        return {
            "visual_score": visual,
            "copy_score": copy_score,
            "fit_score": fit,
            "brand_score": brand,
            "overall_score": overall,
            "publish_decision": decision,
            "passed": passed,
            "improvement_reason": reason,
            "platform": platform,
            "pillar": pillar,
        }
