#!/usr/bin/env python3
"""
Health Bridge — Dana v2 health data ingestion layer.

Manages fitness_health_log.json: daily health records from
Apple Health, Shortcuts, or manual input.
"""

import json
import re
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "_shared"))
from domain_agent_base import WORKSPACE

HEALTH_LOG_PATH = WORKSPACE / "state" / "fitness_health_log.json"

EMPTY_DAY = {
    "date": None,
    "steps": 0,
    "active_calories": 0,
    "workouts_count": 0,
    "workout_minutes": 0,
    "distance_km": 0.0,
    "standing_hours": 0,
    "sleep_hours": 0.0,
    "resting_hr": None,
    "hrv": None,
    "weight": None,
    "source": "manual",
    "updated_at": None,
}


class HealthBridge:

    def _read_log(self) -> list:
        try:
            data = json.loads(HEALTH_LOG_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write_log(self, records: list):
        HEALTH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        HEALTH_LOG_PATH.write_text(
            json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def load_log(self, days: int = 14) -> list:
        records = self._read_log()
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        filtered = [r for r in records if r.get("date", "") >= cutoff]
        return sorted(filtered, key=lambda r: r.get("date", ""), reverse=True)

    def upsert_day(self, record: dict) -> dict:
        records = self._read_log()
        record.setdefault("source", "manual")
        record["updated_at"] = datetime.now().isoformat()
        idx = next(
            (i for i, r in enumerate(records) if r.get("date") == record.get("date")),
            None,
        )
        if idx is not None:
            existing = records[idx]
            for k, v in record.items():
                if v is not None and v != 0 and v != 0.0:
                    existing[k] = v
            existing["updated_at"] = record["updated_at"]
            records[idx] = existing
            result = existing
        else:
            base = dict(EMPTY_DAY)
            base.update(record)
            records.append(base)
            result = base
        records.sort(key=lambda r: r.get("date", ""))
        self._write_log(records)
        return result

    def get_today(self) -> dict:
        today_str = date.today().isoformat()
        for r in self._read_log():
            if r.get("date") == today_str:
                return r
        return {}

    def get_last_n_days(self, n: int) -> list:
        records = self._read_log()
        records.sort(key=lambda r: r.get("date", ""), reverse=True)
        return records[:n]

    def parse_from_message(self, message: str) -> dict:
        result = {"date": date.today().isoformat()}
        msg = message.lower()

        # Steps: "11,000 צעדים" / "11000 steps" / "11000 צעדים"
        m = re.search(r'([\d,\.]+)\s*(?:צעדים|steps|צעד)', msg)
        if m:
            result["steps"] = int(m.group(1).replace(",", "").replace(".", ""))

        # Sleep: "ישנתי X שעות" / "X שעות שינה" / "sleep X hours"
        m = re.search(r'(?:ישנתי|שינה|sleep)\s*([\d\.]+)', msg)
        if not m:
            m = re.search(r'([\d\.]+)\s*(?:שעות שינה|hours?\s*(?:of\s*)?sleep)', msg)
        if m:
            result["sleep_hours"] = float(m.group(1))

        # Workouts: "התאמנתי" / "רצתי" / "הלכתי"
        if re.search(r'(התאמנתי|רצתי|הלכתי\s+\d)', msg):
            result["workouts_count"] = 1
            dur = re.search(r'(\d+)\s*(?:דק|דקות|minutes|min)', msg)
            result["workout_minutes"] = int(dur.group(1)) if dur else 30

        # Weight: "שקלתי X"
        m = re.search(r'(?:שקלתי|משקל)\s*([\d\.]+)', msg)
        if m:
            result["weight"] = float(m.group(1))

        # Distance: "X ק"מ" / "X km"
        m = re.search(r'([\d\.]+)\s*(?:ק"מ|קילומטר|km)', msg)
        if m:
            result["distance_km"] = float(m.group(1))

        return result

    def compute_readiness(self, message: str = "") -> dict:
        last3 = self.get_last_n_days(3)
        msg = message.lower()

        # Extract sleep from message
        sleep_today = None
        m = re.search(r'(?:ישנתי|שינה|sleep)\s*([\d\.]+)', msg)
        if not m:
            m = re.search(r'([\d\.]+)\s*(?:שעות שינה|hours)', msg)
        if m:
            sleep_today = float(m.group(1))

        # Check today's log for sleep if not in message
        if sleep_today is None:
            today_log = self.get_today()
            if today_log.get("sleep_hours"):
                sleep_today = today_log["sleep_hours"]

        # Average sleep from last 3 days if still unknown
        if sleep_today is None:
            sleeps = [r["sleep_hours"] for r in last3 if r.get("sleep_hours")]
            sleep_today = sum(sleeps) / len(sleeps) if sleeps else 7.0

        # Fatigue signals from message
        fatigue_signals = ["גמור", "עייף", "אין לי כוח", "כאב", "כואב", "סורנס", "מותש"]
        has_fatigue = any(s in msg for s in fatigue_signals)

        # Recent workout count (last 3 days)
        recent_workouts = sum(r.get("workouts_count", 0) for r in last3)

        # Decision logic
        if sleep_today < 6 or has_fatigue:
            state = "recovery_day"
            should_train = has_fatigue is False and sleep_today >= 5
            intensity = "low" if should_train else "rest"
            duration = 20 if should_train else 0
            fallback = "הליכה קלה 15 דקות או מתיחות"
            nutrition = "עדיפות לפחמימות איטיות + שינה מוקדמת"
            reasoning = (
                f"שינה נמוכה ({sleep_today}h)"
                if sleep_today < 6
                else "סימני עייפות/כאב מהמסר"
            )
        elif recent_workouts >= 2:
            if sleep_today >= 7:
                state = "push_day"
                should_train = True
                intensity = "high"
                duration = 45
                fallback = "אימון כוח 30 דקות אם אין זמן"
                nutrition = "חלבון גבוה לפני ואחרי אימון"
                reasoning = f"שינה טובה ({sleep_today}h) + מומנטום ({recent_workouts} אימונים ב-3 ימים)"
            else:
                state = "maintain_day"
                should_train = True
                intensity = "medium"
                duration = 30
                fallback = "הליכה מהירה 20 דקות"
                nutrition = "לשמור על חלבון 130g, לא לחרוג בקלוריות"
                reasoning = f"שינה בינונית ({sleep_today}h) + {recent_workouts} אימונים לאחרונה"
        elif recent_workouts == 0 and sleep_today >= 7:
            state = "push_day"
            should_train = True
            intensity = "high"
            duration = 45
            fallback = "לפחות הליכה מהירה 30 דקות"
            nutrition = "חלבון גבוה + לא לדלג על ארוחות"
            reasoning = f"0 אימונים ב-3 ימים + שינה טובה ({sleep_today}h) — חייבים לזוז"
        else:
            state = "maintain_day"
            should_train = True
            intensity = "medium"
            duration = 30
            fallback = "הליכה 20 דקות + מתיחות"
            nutrition = "לשמור על חלבון 130g"
            reasoning = f"מצב סטנדרטי — {recent_workouts} אימון/ים, שינה {sleep_today}h"

        return {
            "readiness_state": state,
            "should_train_today": should_train,
            "recommended_intensity": intensity,
            "recommended_duration": duration,
            "fallback_option": fallback,
            "nutrition_priority_today": nutrition,
            "reasoning": reasoning,
        }
