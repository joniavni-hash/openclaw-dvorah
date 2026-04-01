#!/usr/bin/env python3
"""
Telegram Channel Reader for Tzofit Research
Fetches recent messages from public news channels
Usage: python3 scripts/telegram_channels.py --channels kann_news,bbcnewsukraine --limit 10
"""

import asyncio
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Load env
env_file = Path(__file__).parent.parent / "secrets" / ".env"
env = {}
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

API_ID = int(env.get("TELEGRAM_API_ID", 0))
API_HASH = env.get("TELEGRAM_API_HASH", "")
SESSION_FILE = str(Path(__file__).parent.parent / "secrets" / "tzofit_telegram")

# Default news channels
DEFAULT_CHANNELS = [
    "kann_news",        # כאן חדשות
    "ynet",             # ynet
    "Israel_army",      # דובר צה"ל
    "MiddleEastSpectator",
    "disclosetv",
    "Intel_Slava_Z",
]

async def fetch_channels(channels, limit=10, query=None):
    from telethon import TelegramClient
    from telethon.errors import ChannelPrivateError, UsernameNotOccupiedError

    results = []

    async with TelegramClient(SESSION_FILE, API_ID, API_HASH) as client:
        for channel in channels:
            channel = channel.strip().lstrip("@")
            try:
                messages = []
                async for msg in client.iter_messages(channel, limit=limit):
                    if not msg.text:
                        continue
                    text = msg.text.strip()
                    if query and query.lower() not in text.lower():
                        continue
                    messages.append({
                        "channel": channel,
                        "date": msg.date.strftime("%Y-%m-%d %H:%M"),
                        "text": text[:500],
                        "url": f"https://t.me/{channel}/{msg.id}"
                    })
                results.extend(messages)
            except (ChannelPrivateError, UsernameNotOccupiedError) as e:
                results.append({"channel": channel, "error": str(e)})
            except Exception as e:
                results.append({"channel": channel, "error": str(e)})

    # Sort by date descending
    results.sort(key=lambda x: x.get("date", ""), reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channels", default=",".join(DEFAULT_CHANNELS),
                        help="Comma-separated channel usernames")
    parser.add_argument("--limit", type=int, default=5,
                        help="Messages per channel")
    parser.add_argument("--query", default=None,
                        help="Filter messages containing this keyword")
    args = parser.parse_args()

    if not API_ID or not API_HASH:
        print(json.dumps({"error": "TELEGRAM_API_ID or TELEGRAM_API_HASH not configured"}))
        sys.exit(1)

    channels = [c.strip() for c in args.channels.split(",") if c.strip()]
    results = asyncio.run(fetch_channels(channels, args.limit, args.query))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
