#!/usr/bin/env python3
"""
Health Check — בדיקת תקינות API ושירותים
רץ יומית מ-HEARTBEAT או ידנית
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRETS_PATH = BASE_DIR / "secrets" / ".env"
RESULTS_PATH = BASE_DIR / "state" / "health_check.json"


def load_secrets():
    secrets = {}
    if SECRETS_PATH.exists():
        for line in SECRETS_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                secrets[k.strip()] = v.strip()
    return secrets


def check_outlook(secrets):
    """Test Microsoft Graph token acquisition"""
    try:
        import urllib.request
        import urllib.parse
        tenant = secrets.get('MS_GRAPH_TENANT', '')
        client_id = secrets.get('MS_GRAPH_CLIENT_ID', '')
        client_secret = secrets.get('MS_GRAPH_CLIENT_SECRET', '')
        if not all([tenant, client_id, client_secret]):
            return {"status": "missing_credentials", "ok": False}

        data = urllib.parse.urlencode({
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'https://graph.microsoft.com/.default',
            'grant_type': 'client_credentials'
        }).encode()
        url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        req = urllib.request.Request(url, data=data)
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if result.get('access_token'):
            return {"status": "ok", "ok": True}
        return {"status": "no_token", "ok": False}
    except Exception as e:
        return {"status": str(e)[:100], "ok": False}


def check_google_ads(secrets):
    """Test Google Ads OAuth refresh"""
    try:
        import urllib.request
        import urllib.parse
        client_id = secrets.get('GOOGLE_ADS_CLIENT_ID', '')
        client_secret = secrets.get('GOOGLE_ADS_CLIENT_SECRET', '')
        refresh_token = secrets.get('GOOGLE_ADS_REFRESH_TOKEN', '')
        if not all([client_id, client_secret, refresh_token]):
            return {"status": "missing_credentials", "ok": False}

        data = urllib.parse.urlencode({
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }).encode()
        req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data)
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if result.get('access_token'):
            return {"status": "ok", "ok": True}
        return {"status": "no_token", "ok": False}
    except Exception as e:
        return {"status": str(e)[:100], "ok": False}


def check_dashboard():
    """Test Vercel dashboard push endpoint"""
    try:
        import urllib.request
        url = "https://vercel-dashboard-two-ruby.vercel.app/api/data"
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        if data.get('error') == 'no_data':
            return {"status": "no_data_pushed", "ok": False}
        if 'tasks' in data or 'error' not in data:
            return {"status": "ok", "ok": True}
        return {"status": data.get('error', 'unknown'), "ok": False}
    except Exception as e:
        return {"status": str(e)[:100], "ok": False}


def check_gog():
    """Test GOG CLI (Gmail/Calendar)"""
    try:
        result = subprocess.run(
            ['gog', '--version'], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return {"status": "ok", "ok": True, "version": result.stdout.strip()}
        return {"status": "not_working", "ok": False}
    except FileNotFoundError:
        return {"status": "not_installed", "ok": False}
    except Exception as e:
        return {"status": str(e)[:100], "ok": False}


def check_brave_api():
    """Check if Brave Search API is configured"""
    try:
        result = subprocess.run(
            ['openclaw', 'status'], capture_output=True, text=True, timeout=10
        )
        # Just check if the tool works — actual key is in openclaw config
        return {"status": "check_manually", "ok": None, "note": "Run web_search to test"}
    except Exception as e:
        return {"status": str(e)[:100], "ok": False}





def main():
    secrets = load_secrets()
    checks = {
        "outlook": check_outlook(secrets),
        "google_ads": check_google_ads(secrets),
        "dashboard": check_dashboard(),
        "gog_cli": check_gog(),
        "brave_search": check_brave_api(),

    }

    report = {
        "timestamp": datetime.now().isoformat(),
        "checks": checks,
        "summary": {
            "total": len(checks),
            "ok": sum(1 for c in checks.values() if c.get("ok") is True),
            "failed": sum(1 for c in checks.values() if c.get("ok") is False),
            "unknown": sum(1 for c in checks.values() if c.get("ok") is None),
        }
    }

    # Save results
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    # Print summary
    print(f"🏥 Health Check — {report['timestamp'][:16]}")
    for name, result in checks.items():
        icon = "✅" if result.get("ok") is True else "❌" if result.get("ok") is False else "❓"
        print(f"  {icon} {name}: {result['status']}")

    ok_count = report['summary']['ok']
    total = report['summary']['total']
    print(f"\n{ok_count}/{total} services healthy")

    if report['summary']['failed'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
