#!/usr/bin/env python3
"""
X (Twitter) Reader for Tzofit Research
Fetch recent tweets from specific users or search by keyword.
Usage:
  python3 scripts/x_reader.py --users elonmusk,OpenAI --limit 5
  python3 scripts/x_reader.py --query "Iran ceasefire" --limit 10
"""

import argparse
import json
import sys
from pathlib import Path

# Load env
env = {}
for line in (Path(__file__).parent.parent / "secrets" / ".env").read_text().splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

def get_client():
    import tweepy
    return tweepy.Client(
        bearer_token=env.get("X_BEARER_TOKEN", ""),
        consumer_key=env.get("X_API_KEY", ""),
        consumer_secret=env.get("X_API_SECRET", ""),
        access_token=env.get("X_ACCESS_TOKEN", ""),
        access_token_secret=env.get("X_ACCESS_TOKEN_SECRET", ""),
        wait_on_rate_limit=False
    )

def fetch_user_tweets(usernames, limit=5):
    import tweepy
    client = get_client()
    results = []
    for username in usernames:
        username = username.strip().lstrip("@")
        try:
            user = client.get_user(username=username, user_fields=["public_metrics"])
            if not user.data:
                results.append({"user": username, "error": "not found"})
                continue
            tweets = client.get_users_tweets(
                user.data.id,
                max_results=min(limit, 10),
                tweet_fields=["created_at", "text", "public_metrics"],
                exclude=["retweets", "replies"]
            )
            if tweets.data:
                for t in tweets.data:
                    results.append({
                        "user": username,
                        "date": str(t.created_at)[:16] if t.created_at else "",
                        "text": t.text[:400],
                        "url": f"https://x.com/{username}/status/{t.id}",
                        "likes": t.public_metrics.get("like_count", 0) if t.public_metrics else 0
                    })
        except tweepy.TooManyRequests:
            results.append({"user": username, "error": "rate_limit"})
        except Exception as e:
            results.append({"user": username, "error": str(e)[:100]})
    return results

def search_tweets(query, limit=10):
    import tweepy
    client = get_client()
    try:
        tweets = client.search_recent_tweets(
            query=query + " -is:retweet lang:en",
            max_results=min(limit, 10),
            tweet_fields=["created_at", "text", "author_id", "public_metrics"],
        )
        results = []
        if tweets.data:
            for t in tweets.data:
                results.append({
                    "date": str(t.created_at)[:16] if t.created_at else "",
                    "text": t.text[:400],
                    "likes": t.public_metrics.get("like_count", 0) if t.public_metrics else 0
                })
        return results
    except Exception as e:
        return [{"error": str(e)[:200]}]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", help="Comma-separated X usernames")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    if args.users:
        users = [u.strip() for u in args.users.split(",") if u.strip()]
        results = fetch_user_tweets(users, args.limit)
    elif args.query:
        results = search_tweets(args.query, args.limit)
    else:
        print(json.dumps({"error": "provide --users or --query"}))
        sys.exit(1)

    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
