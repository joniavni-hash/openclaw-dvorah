#!/usr/bin/env python3
"""
Recreate Tali Week 1 queue through the fixed media-binding pipeline.

Purpose:
- rebuild the 6 Week 1 posts with media_attached=True
- avoid legacy copy-only artifacts created before commit 98b0afe
- print a compact report for manual verification in Postiz

Usage:
  python3 scripts/tali_recreate_week1_queue.py [--dry-run]

Notes:
- This script creates clean replacements, it does NOT delete legacy posts in Postiz.
- After a successful run, legacy copy-only drafts/schedules should be cancelled manually
  unless a delete/cancel flow is added later.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
TALI_DIR = ROOT / "agents" / "tali-marketing"
sys.path.insert(0, str(TALI_DIR))

from media_resolver import MediaResolver  # type: ignore
from publishing_client import PublishingClient  # type: ignore

CTA = "www.villalithosgreece.com/welcome"
HASHTAGS = ["#VillaLithos", "#GreekEscape", "#LuxuryVilla"]

WEEK1_POSTS: List[Dict[str, Any]] = [
    {
        "platform": "instagram",
        "pillar": "visual_escape",
        "scheduled_time": "2026-03-28 19:00",
        "caption": "השקיעה עושה כאן את כל העבודה. אם אתם מחפשים בריחה שנשארת בראש, זה המקום.",
    },
    {
        "platform": "tiktok",
        "pillar": "dreaming_aspiration",
        "scheduled_time": "2026-03-29 20:00",
        "caption": "המקום הזה מרגיש לא אמיתי. חופשה אחת טובה השנה, אולי זאת בדיוק היא.",
    },
    {
        "platform": "pinterest",
        "pillar": "stay_experience",
        "scheduled_time": "2026-03-30 11:00",
        "caption": "A bedroom view that makes the whole stay feel slower, calmer, better.",
    },
    {
        "platform": "facebook",
        "pillar": "booking_intent",
        "scheduled_time": "2026-03-31 12:00",
        "caption": "אם בא לכם סוף שבוע שקט עם נוף, בריכה ותחושת חופשה אמיתית, בדקו זמינות עכשיו.",
    },
    {
        "platform": "tiktok",
        "pillar": "dreaming_aspiration",
        "scheduled_time": "2026-04-01 20:00",
        "caption": "POV: הטיול הקבוצתי שלכם עולה פחות ממה שחשבתם, ונראה הרבה יותר טוב.",
        "preferred_asset_id": "1img8688",  # IMG_8688.JPG — avoid duplicate with day 2
    },
    {
        "platform": "pinterest",
        "pillar": "visual_escape",
        "scheduled_time": "2026-04-02 11:00",
        "caption": "Pool, light, quiet, and a view that sells the trip before the words do.",
    },
]


def recreate_week1(dry_run: bool = False) -> Dict[str, Any]:
    resolver = MediaResolver()
    publisher = PublishingClient()

    created: List[Dict[str, Any]] = []
    queue_payloads: List[Dict[str, Any]] = []

    for post in WEEK1_POSTS:
        artifact = resolver.resolve_and_bind(
            platform=post["platform"],
            pillar=post["pillar"],
            caption=post["caption"],
            cta=CTA,
            hashtags=HASHTAGS,
            scheduled_time=post["scheduled_time"],
            preferred_asset_id=post.get("preferred_asset_id"),
        )

        if not artifact.publishable:
            created.append(
                {
                    "platform": post["platform"],
                    "scheduled_time": post["scheduled_time"],
                    "status": artifact.status,
                    "publishable": False,
                    "media_attached": False,
                    "attached_filename": None,
                    "error": artifact.error,
                }
            )
            continue

        payload = publisher.build_payload(
            platform=post["platform"],
            caption=post["caption"],
            hashtags=" ".join(HASHTAGS),
            asset_refs=[artifact.attached_filename] if artifact.attached_filename else [],
            selected_asset=artifact.selected_asset,
            media_attached=True,
            scheduled_time=post["scheduled_time"],
            cta=CTA,
            approval_required=False,
            autonomous_mode=True,
        )
        queue_payloads.append(payload)

        contract = (
            {
                "draft_status": "dry_run",
                "postiz_id": None,
                "platform": post["platform"],
                "media_attached": True,
                "attached_filename": artifact.attached_filename,
                "asset_source": artifact.asset_source,
                "publishable": True,
            }
            if dry_run
            else publisher.schedule(payload)
        )

        created.append(
            {
                "platform": post["platform"],
                "pillar": post["pillar"],
                "scheduled_time": post["scheduled_time"],
                "status": contract["draft_status"],
                "postiz_id": contract["postiz_id"],
                "publishable": contract["publishable"],
                "media_attached": contract["media_attached"],
                "attached_filename": contract["attached_filename"],
            }
        )

    queue_health = resolver.validate_week_queue(queue_payloads)
    return {"created": created, "queue_health": queue_health, "dry_run": dry_run}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = recreate_week1(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
