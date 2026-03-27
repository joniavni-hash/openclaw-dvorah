#!/usr/bin/env python3
"""
Tali Readiness Checker — real connectivity detection, not env var checks.

Priority for each connector:
1. Try actual live check (API call / CLI command)
2. Fall back to config-based detection
3. Report accurate status: connected / degraded / not_available
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

WORKSPACE = Path(os.environ.get("DVORAH_WORKSPACE", Path.home() / ".openclaw" / "workspace"))

POSTIZ_BASE_URL = "https://api.postiz.com/public/v1"
GDRIVE_FOLDER_ID = "1x2qEmoYopOtlhXWQfunQ5H7a_hy2oisI"
GDRIVE_ACCOUNT = "joni.avni@gmail.com"

# Known Postiz integration IDs from config
POSTIZ_INTEGRATION_IDS = {
    "instagram": "cmn4rshvr0e4xpb0yx8rwkgrb",
    "facebook": "cmn4rv4i60e8opb0y2yncyc7i",
    "tiktok": "cmn4rugfx0e56pb0yn0tyvil3",
    "pinterest": "cmn4rwivz0e8wpb0yvfykswih",
}


def _load_postiz_key() -> Optional[str]:
    """Try to load Postiz API key from multiple sources."""
    # 1. Env var
    key = os.environ.get("POSTIZ_API_KEY", "").strip()
    if key and key != "YOUR_POSTIZ_API_KEY_HERE":
        return key

    # 2. secrets/.env
    env_file = WORKSPACE / "secrets" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("POSTIZ_API_KEY="):
                val = line.split("=", 1)[1].strip()
                if val and val != "YOUR_POSTIZ_API_KEY_HERE":
                    return val

    # 3. known config files
    config_files = [
        WORKSPACE / "integrations" / "social" / "villa_lithos_tiktok_config.json",
        WORKSPACE / "villa-lithos-tiktok" / "larry-system" / "config" / "villa-lithos.json",
    ]
    for cf in config_files:
        if cf.exists():
            try:
                data = json.loads(cf.read_text())
                key = data.get("postiz", {}).get("apiKey", "")
                if key and key != "YOUR_POSTIZ_API_KEY_HERE":
                    return key
            except Exception:
                continue

    return None


def check_postiz() -> Dict:
    """
    Check Postiz connectivity via actual API call.
    Returns: {status, connected, usable, how_verified, integration_ids, message}
    """
    api_key = _load_postiz_key()

    if not api_key:
        return {
            "status": "not_available",
            "connected": False,
            "usable": False,
            "how_verified": "no_api_key_found",
            "message": "Postiz API key not configured. Get from: Postiz → Settings → Developers → Public API",
            "integration_ids": POSTIZ_INTEGRATION_IDS,
        }

    # Try actual API call
    try:
        import requests
        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        resp = requests.get(f"{POSTIZ_BASE_URL}/integrations", headers=headers, timeout=8)

        if resp.status_code == 200:
            integrations = resp.json()
            platforms_found = [i.get("identifier") for i in integrations if i.get("identifier")]
            return {
                "status": "connected",
                "connected": True,
                "usable": True,
                "how_verified": "live_api_call",
                "platforms": platforms_found,
                "total_integrations": len(integrations),
                "message": f"Postiz connected — {len(integrations)} integrations active",
            }
        elif resp.status_code == 401:
            return {
                "status": "degraded",
                "connected": False,
                "usable": False,
                "how_verified": "live_api_call",
                "message": f"Postiz API key invalid (401). Key found but rejected.",
            }
        else:
            return {
                "status": "degraded",
                "connected": False,
                "usable": False,
                "how_verified": "live_api_call",
                "message": f"Postiz API returned {resp.status_code}",
            }
    except ImportError:
        # requests not available — degrade gracefully
        return {
            "status": "degraded",
            "connected": bool(api_key),
            "usable": False,
            "how_verified": "key_found_no_requests_lib",
            "message": "API key found but cannot verify — requests library unavailable",
            "integration_ids": POSTIZ_INTEGRATION_IDS,
        }
    except Exception as e:
        return {
            "status": "degraded",
            "connected": bool(api_key),
            "usable": False,
            "how_verified": "api_call_failed",
            "message": f"Key found but API unreachable: {e}",
        }


def check_google_drive() -> Dict:
    """
    Check Google Drive via gog CLI (real OAuth, not env var).
    Returns: {status, connected, usable, how_verified, asset_count, assets}
    """
    # Try gog CLI with GOG_KEYRING_PASSWORD=""
    try:
        env = os.environ.copy()
        env["GOG_KEYRING_PASSWORD"] = ""
        result = subprocess.run(
            ["gog", "drive", "ls", "--parent", GDRIVE_FOLDER_ID, "--account", GDRIVE_ACCOUNT],
            capture_output=True, text=True, timeout=15, env=env
        )

        if result.returncode == 0 and result.stdout.strip():
            lines = [l for l in result.stdout.strip().splitlines()
                     if l.strip() and not l.startswith("#") and not l.startswith("ID")]
            assets = []
            for line in lines:
                parts = line.split(None, 4)
                if len(parts) >= 2:
                    assets.append({"id": parts[0], "name": parts[1] if len(parts) > 1 else "?"})

            return {
                "status": "connected",
                "connected": True,
                "usable": True,
                "how_verified": "gog_cli_live",
                "asset_count": len(assets),
                "folder_id": GDRIVE_FOLDER_ID,
                "account": GDRIVE_ACCOUNT,
                "assets": assets[:5],  # sample
                "message": f"Google Drive connected — {len(assets)} assets in villa folder",
            }
        else:
            err = result.stderr.strip()
            return {
                "status": "degraded",
                "connected": False,
                "usable": False,
                "how_verified": "gog_cli_failed",
                "message": f"gog CLI failed: {err[:200]}",
            }
    except FileNotFoundError:
        return {
            "status": "not_available",
            "connected": False,
            "usable": False,
            "how_verified": "gog_not_installed",
            "message": "gog CLI not found. Install or re-auth: gog auth add joni.avni@gmail.com --services drive",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "degraded",
            "connected": False,
            "usable": False,
            "how_verified": "gog_cli_timeout",
            "message": "gog CLI timed out",
        }
    except Exception as e:
        return {
            "status": "degraded",
            "connected": False,
            "usable": False,
            "how_verified": "error",
            "message": str(e),
        }


def check_analytics() -> Dict:
    """Check analytics files availability."""
    analytics_dir = WORKSPACE / "villa-lithos" / "analytics"
    files = {
        "hook-performance.json": False,
        "instagram_posts.json": False,
        "facebook_posts.json": False,
        "tiktok_posts.json": False,
        "pinterest_posts.json": False,
        "weekly_summary.md": False,
    }
    found = []
    for fname in files:
        path = analytics_dir / fname
        if path.exists() and path.stat().st_size > 10:
            files[fname] = True
            found.append(fname)

    if len(found) >= 4:
        status = "connected"
        msg = f"{len(found)}/6 analytics files present"
    elif len(found) >= 1:
        status = "local_only"
        msg = f"Partial: {len(found)}/6 files. No live API analytics."
    else:
        status = "not_available"
        msg = "No analytics files found"

    return {
        "status": status,
        "connected": len(found) >= 1,
        "usable": len(found) >= 1,
        "how_verified": "local_file_check",
        "files_found": found,
        "files_missing": [f for f, v in files.items() if not v],
        "message": msg,
    }


def full_readiness_report() -> Dict:
    """Run all checks and return full readiness report."""
    postiz = check_postiz()
    gdrive = check_google_drive()
    analytics = check_analytics()

    all_ok = postiz["usable"] and gdrive["usable"] and analytics["usable"]
    autonomous_ready = gdrive["usable"] and analytics["usable"]  # can work without Postiz (local drafts)

    missing = []
    if not postiz["usable"]:
        missing.append("Postiz API key — needed for publishing")
    if not gdrive["usable"]:
        missing.append("Google Drive — needed for asset access")
    if not analytics["usable"]:
        missing.append("Analytics files — needed for performance analysis")

    return {
        "postiz": postiz,
        "google_drive": gdrive,
        "analytics": analytics,
        "overall": "ready" if all_ok else ("partial" if autonomous_ready else "not_ready"),
        "autonomous_mode_ready": autonomous_ready,
        "missing": missing,
    }


def format_report(report: Dict) -> str:
    """Format readiness report as clean text."""
    def icon(status):
        return {"connected": "✅", "local_only": "⚠️", "degraded": "⚠️", "not_available": "❌"}.get(status, "❓")

    p = report["postiz"]
    g = report["google_drive"]
    a = report["analytics"]

    lines = [
        "🔌 Publishing Readiness",
        "",
        f"Postiz:       {icon(p['status'])} {p['status']} — {p['message']}",
        f"  verified:   {p.get('how_verified', '?')}",
    ]
    if p.get("platforms"):
        lines.append(f"  platforms:  {', '.join(p['platforms'])}")

    lines += [
        "",
        f"Google Drive: {icon(g['status'])} {g['status']} — {g['message']}",
        f"  verified:   {g.get('how_verified', '?')}",
    ]
    if g.get("asset_count"):
        lines.append(f"  assets:     {g['asset_count']} files in villa folder")
    if g.get("assets"):
        for asset in g["assets"][:3]:
            lines.append(f"    • {asset['name']}")

    lines += [
        "",
        f"Analytics:    {icon(a['status'])} {a['status']} — {a['message']}",
        f"  verified:   {a.get('how_verified', '?')}",
    ]

    lines += [
        "",
        f"Overall: {report['overall']}",
        f"Autonomous mode ready: {'✅ כן' if report['autonomous_mode_ready'] else '❌ לא'}",
    ]
    if report["missing"]:
        lines.append("\nחסר:")
        for m in report["missing"]:
            lines.append(f"  • {m}")

    return "\n".join(lines)
