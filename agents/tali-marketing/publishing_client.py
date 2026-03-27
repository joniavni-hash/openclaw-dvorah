#!/usr/bin/env python3
"""Publishing Client — handles draft creation and Postiz integration."""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

WORKSPACE = Path(os.environ.get("DVORAH_WORKSPACE", Path.home() / ".openclaw" / "workspace"))


class PublishingClient:
    DRAFTS_ROOT = WORKSPACE / "villa-lithos" / "publishing" / "drafts"
    POSTIZ_CONFIGURED = bool(os.environ.get("POSTIZ_API_KEY"))

    def build_payload(self, platform: str, caption: str, hashtags: str,
                      asset_refs: list, scheduled_time: Optional[str] = None) -> dict:
        return {
            "id": f"draft_{uuid.uuid4().hex[:8]}",
            "platform": platform,
            "caption": caption,
            "hashtags": hashtags,
            "asset_refs": asset_refs,
            "scheduled_time": scheduled_time,
            "created_at": datetime.now().isoformat(),
            "status": "draft",
        }

    def save_draft(self, payload: dict) -> str:
        self.DRAFTS_ROOT.mkdir(parents=True, exist_ok=True)
        draft_id = payload.get("id", f"draft_{uuid.uuid4().hex[:8]}")
        filename = f"{draft_id}.json"
        filepath = self.DRAFTS_ROOT / filename
        filepath.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return filename

    def submit_to_postiz(self, payload: dict) -> dict:
        if not self.POSTIZ_CONFIGURED:
            filename = self.save_draft(payload)
            return {"status": "local_draft", "draft_id": filename, "error": None}

        # Future: actual Postiz API call
        try:
            filename = self.save_draft(payload)
            return {"status": "local_draft", "draft_id": filename, "error": None}
        except Exception as e:
            return {"status": "error", "draft_id": None, "error": str(e)}
