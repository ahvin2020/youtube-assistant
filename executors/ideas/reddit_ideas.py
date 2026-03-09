#!/usr/bin/env python3
"""Fetch hot and top posts from personal-finance-relevant subreddits.

Uses old.reddit.com public JSON endpoints (no authentication required).
Returns structured post data for topic discovery and analysis.

Usage:
    python3 executors/ideas/reddit_ideas.py \
        [--channel-profile memory/channel-profile.md] \
        [--subreddits personalfinance,investing,stocks] \
        [--timeframe month] [--max-posts 25] [--max-subs 8] \
        [--output workspace/temp/ideas/<PROJECT>/reddit_data.json]

Depends on: nothing (stdlib only)
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime

_EXECUTORS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EXECUTORS_DIR not in sys.path:
    sys.path.insert(0, _EXECUTORS_DIR)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

BASE_URL = "https://old.reddit.com"


def fetch_subreddit(subreddit: str, endpoint: str, timeframe: str = "month",
                    limit: int = 50, retries: int = 2) -> list[dict]:
    """Fetch posts from a subreddit endpoint (hot or top) via old.reddit.com.

    Uses system curl to avoid TLS fingerprint blocking by Reddit.
    Returns list of post dicts. Retries on transient failures.
    """
    if endpoint == "top":
        url = f"{BASE_URL}/r/{subreddit}/top.json?t={timeframe}&limit={limit}"
    else:
        url = f"{BASE_URL}/r/{subreddit}/hot.json?limit={limit}"

    last_err = None
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                ["curl", "-s", "-f", "-H", f"User-Agent: {USER_AGENT}", url],
                capture_output=True, text=True, timeout=20,
            )
            if result.returncode != 0:
                raise RuntimeError(f"curl returned {result.returncode}: {result.stderr.strip()}")
            data = json.loads(result.stdout)
            break
        except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"Failed to fetch r/{subreddit}/{endpoint}: {last_err}")

    posts = []
    children = data.get("data", {}).get("children", [])

    for child in children:
        post_data = child.get("data", {})

        # Skip pinned/stickied posts
        if post_data.get("stickied"):
            continue

        created_utc = post_data.get("created_utc", 0)
        days_old = (datetime.utcnow() - datetime.utcfromtimestamp(created_utc)).days if created_utc else None

        selftext = post_data.get("selftext", "") or ""

        posts.append({
            "post_id": post_data.get("id", ""),
            "title": post_data.get("title", ""),
            "score": post_data.get("score", 0),
            "num_comments": post_data.get("num_comments", 0),
            "subreddit": subreddit,
            "url": f"https://reddit.com{post_data.get('permalink', '')}",
            "created_utc": int(created_utc) if created_utc else None,
            "days_old": days_old,
            "selftext_preview": selftext[:500],
            "flair": post_data.get("link_flair_text", ""),
            "source": endpoint,
        })

    return posts


def _fetch_sub_endpoint(args: tuple) -> tuple[str, str, list[dict] | None, str | None]:
    """Fetch one subreddit+endpoint combo. Returns (sub, endpoint, posts, error)."""
    subreddit, endpoint, timeframe, max_posts = args
    try:
        posts = fetch_subreddit(subreddit, endpoint, timeframe, max_posts)
        return (subreddit, endpoint, posts, None)
    except RuntimeError as e:
        return (subreddit, endpoint, None, str(e))


def main():
    parser = argparse.ArgumentParser(
        description="Fetch hot and top posts from subreddits for topic discovery."
    )
    parser.add_argument("--channel-profile", default=None,
                        help="Path to channel-profile.md (reads Community Sources → Subreddits)")
    parser.add_argument("--subreddits", default=None,
                        help="Comma-separated subreddit names (overrides config)")
    parser.add_argument("--timeframe", default="month", choices=["week", "month", "year"],
                        help="Time window for top posts (default: month)")
    parser.add_argument("--max-posts", type=int, default=50,
                        help="Max posts per subreddit per endpoint (default: 50)")
    parser.add_argument("--max-subs", type=int, default=8,
                        help="Max subreddits to query (randomly sampled if more; default: 8)")
    parser.add_argument("--output", default=None,
                        help="Output JSON file path (optional; always prints to stdout)")
    args = parser.parse_args()

    # Resolve subreddit list
    subreddits = []
    if args.subreddits:
        subreddits = [s.strip() for s in args.subreddits.split(",") if s.strip()]
    elif args.channel_profile:
        if not os.path.isfile(args.channel_profile):
            print(json.dumps({"status": "error", "error": f"Channel profile not found: {args.channel_profile}"}))
            sys.exit(1)
        from shared.parse_profile import parse_channel_profile
        config = parse_channel_profile(args.channel_profile)
        subreddits = config.get("subreddits", [])
    else:
        print(json.dumps({
            "status": "error",
            "error": "Provide --subreddits or --channel-profile",
        }))
        sys.exit(1)

    if not subreddits:
        print(json.dumps({"status": "error", "error": "No subreddits specified"}))
        sys.exit(1)

    # Sample subreddits if more than max
    if len(subreddits) > args.max_subs:
        subreddits = random.sample(subreddits, args.max_subs)

    start = time.time()
    all_posts: list[dict] = []
    errors: list[str] = []

    # Build all (subreddit, endpoint) combos for parallel fetch
    tasks = []
    for subreddit in subreddits:
        for endpoint in ["hot", "top"]:
            tasks.append((subreddit, endpoint, args.timeframe, args.max_posts))

    # Parallel fetch with 4 workers (stays under old.reddit rate limits)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for sub, endpoint, posts, error in pool.map(_fetch_sub_endpoint, tasks):
            if error:
                errors.append(error)
            elif posts:
                all_posts.extend(posts)

    # Deduplicate by post_id (same post may appear in both hot and top)
    seen_ids: set[str] = set()
    unique_posts: list[dict] = []
    for post in all_posts:
        pid = post.get("post_id")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            unique_posts.append(post)

    # Sort by score descending
    unique_posts.sort(key=lambda p: p.get("score", 0), reverse=True)

    elapsed = round(time.time() - start, 2)

    result = {
        "status": "success",
        "subreddits_queried": subreddits,
        "total_posts": len(unique_posts),
        "posts": unique_posts,
        "errors": errors,
        "elapsed_seconds": elapsed,
    }

    # Write to output file if specified
    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(json.dumps({
            "status": "success",
            "output": args.output,
            "total_posts": len(unique_posts),
            "subreddits_queried": len(subreddits),
            "elapsed_seconds": elapsed,
        }))
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
