#!/usr/bin/env python3
"""Publishing Client — handles draft creation and Postiz integration.

Publishing invariant (enforced at save/schedule boundary):
  - Platforms requiring media: instagram, tiktok, pinterest, facebook
  - If media_attached != True for those platforms → BLOCK scheduling
  - Only draft_blocked_missing_media or needs_media_review allowed without media
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

WORKSPACE = Path(os.environ.get("DVORAH_WORKSPACE", Path.home() / ".openclaw" / "workspace"))

# Auto-load secrets/.env if POSTIZ_API_KEY not already in env
_env_file = WORKSPACE / "secrets" / ".env"
if _env_file.exists() and not os.environ.get("POSTIZ_API_KEY"):
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

POSTIZ_BASE_URL = os.environ.get("POSTIZ_BASE_URL", "https://api.postiz.com/public/v1")

# Platforms that require media — cannot be scheduled without it
MEDIA_REQUIRED_PLATFORMS = {"instagram", "tiktok", "pinterest", "facebook"}


class PublishingClient:
    DRAFTS_ROOT = WORKSPACE / "villa-lithos" / "publishing" / "drafts"

    @property
    def POSTIZ_CONFIGURED(self):
        return bool(os.environ.get("POSTIZ_API_KEY"))

    def build_payload(self, platform: str, caption: str, hashtags: str,
                      asset_refs: list, scheduled_time: Optional[str] = None,
                      cta: Optional[str] = None, approval_required: bool = True,
                      autonomous_mode: bool = False,
                      selected_asset: Optional[Dict] = None,
                      media_attached: bool = False) -> dict:
        """Build post payload. media_attached must be True for required platforms to be schedulable."""
        return {
            "id": f"draft_{uuid.uuid4().hex[:8]}",
            "platform": platform,
            "copy": caption,
            "hashtags": hashtags,
            "cta": cta or "",
            "asset_refs": asset_refs,
            "selected_asset": selected_asset or {},
            "media_attached": media_attached,
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

    def schedule(self, payload: dict) -> dict:
        """
        Schedule a post. Enforces media invariant before scheduling.
        Returns postiz_save_contract dict.
        """
        platform = payload.get("platform", "").lower()
        media_attached = payload.get("media_attached", False)

        # INVARIANT: block scheduling without media for required platforms
        if platform in MEDIA_REQUIRED_PLATFORMS and not media_attached:
            blocked = {**payload, "status": "draft_blocked_missing_media",
                       "publishable": False}
            self.save_draft(blocked)
            return {
                "draft_status": "draft_blocked_missing_media",
                "postiz_id": None,
                "platform": platform,
                "media_attached": False,
                "attached_filename": None,
                "asset_source": None,
                "publishable": False,
                "error": "Media required for this platform — attach media before scheduling",
            }

        # Media present or not required — proceed
        result = self.submit_to_postiz(payload)
        postiz_id = result.get("postiz_id") or result.get("draft_id")
        selected = payload.get("selected_asset", {})

        contract = {
            "draft_status": "scheduled" if result.get("status") != "local_draft" else "local_draft",
            "postiz_id": postiz_id,
            "platform": platform,
            "media_attached": media_attached,
            "attached_filename": selected.get("filename") or payload.get("asset_refs", [None])[0],
            "asset_source": selected.get("source", "google_drive"),
            "publishable": True,
        }
        return contract

    def get_draft_status(self, draft_id: str) -> dict:
        filepath = self.DRAFTS_ROOT / draft_id
        if not filepath.exists():
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
                    drafts.append({
                        "filename": f.name,
                        "id": data.get("id"),
                        "status": data.get("status"),
                        "platform": data.get("platform"),
                        "media_attached": data.get("media_attached", False),
                        "created_at": data.get("created_at"),
                    })
            except Exception:
                continue
        return drafts

    def submit_to_postiz(self, payload: dict) -> dict:
        payload["external_action_attempted"] = True
        if not self.POSTIZ_CONFIGURED:
            filename = self.save_draft(payload)
            return {"status": "local_draft", "draft_id": filename,
                    "message": "Postiz not configured — saved locally"}

        try:
            import requests
            api_key = os.environ["POSTIZ_API_KEY"]
            headers = {"Authorization": api_key}

            # 1. Upload media if local_path available
            media_ids = []
            sel = payload.get("selected_asset", {}) or {}
            local_path = sel.get("local_path")
            if local_path:
                lp = Path(local_path)
                if lp.exists() and lp.stat().st_size > 17:  # skip placeholders
                    mime = sel.get("mime_type", "image/jpeg")
                    with open(lp, "rb") as f:
                        up = requests.post(
                            f"{POSTIZ_BASE_URL}/upload",
                            headers=headers,
                            files={"file": (lp.name, f, mime)},
                            timeout=60,
                        )
                    if up.status_code in (200, 201):
                        media_ids = [up.json().get("id") or up.json().get("path", "")]
                    else:
                        filename = self.save_draft(payload)
                        return {"status": "local_draft_upload_failed", "draft_id": filename,
                                "error": f"upload {up.status_code}: {up.text[:200]}"}

            # 2. Get integrations to find correct integration ID
            integ_resp = requests.get(f"{POSTIZ_BASE_URL}/integrations",
                                      headers=headers, timeout=10)
            integrations = integ_resp.json() if integ_resp.status_code == 200 else []
            platform = payload.get("platform", "").lower()
            integration_id = None
            for integ in (integrations if isinstance(integrations, list) else []):
                if integ.get("identifier", "").lower() == platform and not integ.get("disabled"):
                    integration_id = integ.get("id")
                    break

            if not integration_id:
                filename = self.save_draft(payload)
                return {"status": "local_draft_no_integration", "draft_id": filename,
                        "error": f"No active Postiz integration for {platform}"}

            # 3. Schedule post
            scheduled_time = payload.get("scheduled_time")
            post_body = {
                "integrationId": integration_id,
                "content": payload.get("copy") or payload.get("caption", ""),
                "date": scheduled_time,
                "settings": {},
            }
            if media_ids:
                post_body["media"] = [{"id": mid} for mid in media_ids if mid]

            post_resp = requests.post(
                f"{POSTIZ_BASE_URL}/posts",
                headers={**headers, "Content-Type": "application/json"},
                json=post_body,
                timeout=30,
            )

            if post_resp.status_code in (200, 201):
                result = post_resp.json()
                postiz_post_id = result.get("id") or result.get("postId")
                payload["postiz_post_id"] = postiz_post_id
                payload["status"] = "scheduled"
                filename = self.save_draft(payload)
                return {"status": "scheduled", "draft_id": filename,
                        "postiz_id": postiz_post_id, "integration_id": integration_id}
            else:
                filename = self.save_draft(payload)
                return {"status": f"postiz_error_{post_resp.status_code}",
                        "draft_id": filename,
                        "error": post_resp.text[:300]}

        except Exception as e:
            filename = self.save_draft(payload)
            return {"status": "local_draft", "draft_id": filename, "error": str(e)}
