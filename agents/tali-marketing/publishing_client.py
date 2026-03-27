#!/usr/bin/env python3
"""Publishing Client — handles draft creation and Postiz integration."""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

WORKSPACE = Path(os.environ.get("DVORAH_WORKSPACE", Path.home() / ".openclaw" / "workspace"))


class PublishingClient:
    DRAFTS_ROOT = WORKSPACE / "villa-lithos" / "publishing" / "drafts"
    POSTIZ_CONFIGURED = bool(os.environ.get("POSTIZ_API_KEY"))

    def build_payload(self, platform: str, caption: str, hashtags: str,
                      asset_refs: list, scheduled_time: Optional[str] = None,
                      cta: Optional[str] = None, approval_required: bool = True,
                      autonomous_mode: bool = False) -> dict:
        return {
            "id": f"draft_{uuid.uuid4().hex[:8]}",
            "platform": platform,
            "copy": caption,
            "hashtags": hashtags,
            "cta": cta or "",
            "asset_refs": asset_refs,
            "scheduled_time": scheduled_time,
            "created_at": datetime.now().isoformat(),
            "status": "draft",
            "approval_required": approval_required,
            "external_action_attempted": False,
            "autonomous_mode": autonomous_mode,
        }

    def save_draft(self, payload: dict) -> str:
        self.DRAFTS_ROOT.mkdir(parents=True, exist_ok=True)
        draft_id = payload.get("id", f"draft_{uuid.uuid4().hex[:8]}")
        filename = f"{draft_id}.json"
        filepath = self.DRAFTS_ROOT / filename
        filepath.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return filename

    def get_draft_status(self, draft_id: str) -> dict:
        filepath = self.DRAFTS_ROOT / draft_id
        if not filepath.exists():
            # Try with .json extension
            filepath = self.DRAFTS_ROOT / f"{draft_id}.json"
        if not filepath.exists():
            return {"status": "not_found", "draft_id": draft_id}
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return {"status": data.get("status", "unknown"), "draft_id": draft_id, "payload": data}
        except Exception as e:
            return {"status": "error", "draft_id": draft_id, "error": str(e)}

    def list_drafts(self, status_filter: Optional[str] = None) -> list:
        if not self.DRAFTS_ROOT.exists():
            return []
        drafts = []
        for f in self.DRAFTS_ROOT.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if status_filter is None or data.get("status") == status_filter:
                    drafts.append({"filename": f.name, "id": data.get("id"), "status": data.get("status"),
                                   "platform": data.get("platform"), "created_at": data.get("created_at")})
            except Exception:
                continue
        return drafts

    def submit_to_postiz(self, payload: dict) -> dict:
        payload["external_action_attempted"] = True
        if not self.POSTIZ_CONFIGURED:
            filename = self.save_draft(payload)
            return {"status": "local_draft", "draft_id": filename, "message": "Postiz not configured"}

        # Future: actual Postiz API call
        try:
            filename = self.save_draft(payload)
            return {"status": "local_draft", "draft_id": filename, "message": "Postiz not configured"}
        except Exception as e:
            return {"status": "error", "draft_id": None, "error": str(e)}
