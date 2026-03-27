#!/usr/bin/env python3
"""Asset Manager — manages Villa Lithos marketing assets."""

import os
from pathlib import Path
from typing import Dict, List

WORKSPACE = Path(os.environ.get("DVORAH_WORKSPACE", Path.home() / ".openclaw" / "workspace"))


class AssetManager:
    ASSETS_ROOT = WORKSPACE / "villa-lithos" / "assets"

    TASK_ASSET_NEEDS = {
        "reel": ["pool_sunset_reel.mp4", "villa_exterior.mp4"],
        "carousel": ["slide_1.jpg", "slide_2.jpg", "slide_3.jpg"],
        "post": ["villa_hero.jpg"],
        "pin": ["pin_vertical.jpg"],
        "story": ["story_bg.jpg"],
        "video": ["pool_sunset_reel.mp4"],
    }

    def list_assets(self, category: str) -> list:
        target = self.ASSETS_ROOT / category
        if not target.exists():
            return []
        return [f.name for f in target.iterdir() if f.is_file()]

    def get_asset_refs(self, task_type: str, platform: str) -> dict:
        needed = self.TASK_ASSET_NEEDS.get(task_type, ["villa_hero.jpg"])
        all_existing = []
        for cat in ["raw", "edited", "thumbnails", "carousels", "pinterest", "brand"]:
            all_existing.extend(self.list_assets(cat))

        available = [a for a in needed if a in all_existing]
        missing = [a for a in needed if a not in all_existing]
        suggested = needed[:1] if missing else []

        return {
            "available": available,
            "missing": missing,
            "suggested": suggested,
        }
