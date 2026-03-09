#!/usr/bin/env python3
"""Gather competitor video data, own-channel coverage, and YouTube search
suggestions for content topic discovery.

Three parallel workstreams:
  A) Own channel analysis — fetch recent videos for gap analysis
  B) Competitor analysis — fetch from own-niche + adjacent categories
  C) Search suggestions — YouTube autocomplete for niche keywords

Unlike cross_niche_research.py (which searches OUTSIDE the niche for visual
hooks), this executor searches INSIDE the niche and adjacent niches for
content opportunities. No thumbnails or transcripts are downloaded.

Usage:
    python3 executors/ideas/youtube_ideas.py \
        --channel-profile memory/channel-profile.md \
        --channel-id UCJmaaSJX_PkfUmTuxWbrzLw \
        [--format both] [--max-channels 15] [--max-keywords 10] \
        [--days 90] \
        [--output workspace/temp/ideas/<PROJECT>/youtube_data.json]

Depends on: yt-dlp (brew install yt-dlp)
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime

_EXECUTORS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EXECUTORS_DIR not in sys.path:
    sys.path.insert(0, _EXECUTORS_DIR)
from collections import defaultdict
from shared.youtube import search_youtube, fetch_channel_recent_videos, enrich_video


def fetch_search_suggestions(keyword: str) -> list[str]:
    """Fetch YouTube search autocomplete suggestions for a keyword."""
    encoded = urllib.request.quote(keyword)
    url = f"https://suggestqueries-clients6.youtube.com/complete/search?client=youtube&q={encoded}&ds=yt"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return []

    # Response is JSONP: callback([...])
    # Extract the JSON array
    try:
        start = raw.index("[")
        # Find the matching end bracket for the outer array
        depth = 0
        end = start
        for i in range(start, len(raw)):
            if raw[i] == "[":
                depth += 1
            elif raw[i] == "]":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        data = json.loads(raw[start:end])
        if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
            return [item[0] if isinstance(item, list) else str(item) for item in data[1]]
    except (ValueError, json.JSONDecodeError, IndexError):
        pass

    return []


def flatten_channels_by_category(monitored: dict, categories: list[str]) -> dict[str, str]:
    """Flatten monitored_channels for specified categories only.

    Returns {channel_id: channel_name} dict.
    """
    flat: dict[str, str] = {}
    for category, channels in monitored.items():
        if category in categories and isinstance(channels, dict):
            flat.update(channels)
    return flat


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Gather YouTube data for topic discovery."
    )
    parser.add_argument("--channel-profile", required=True,
                        help="Path to channel-profile.md")
    parser.add_argument("--channel-id", required=True,
                        help="Own YouTube channel ID")
    parser.add_argument("--format", default="both",
                        choices=["longform", "shorts", "both"],
                        help="Content format to analyze (default: both)")
    parser.add_argument("--max-channels", type=int, default=15,
                        help="Max competitor channels to scan (default: 15)")
    parser.add_argument("--max-keywords", type=int, default=10,
                        help="Max niche keywords for search suggestions (default: 10)")
    parser.add_argument("--days", type=int, default=90,
                        help="Lookback period in days (default: 90)")
    parser.add_argument("--topic-hint", default=None,
                        help="Optional topic hint for targeted YouTube search")
    parser.add_argument("--output", default=None,
                        help="Output JSON file path (optional)")
    args = parser.parse_args()

    start = time.time()

    # Load config
    if not os.path.isfile(args.channel_profile):
        print(json.dumps({"status": "error", "error": f"channel-profile.md not found: {args.channel_profile}"}))
        sys.exit(1)

    from shared.parse_profile import parse_channel_profile
    ideas_config = parse_channel_profile(args.channel_profile)

    niche_keywords = ideas_config.get("niche_keywords", [])
    own_categories = ideas_config.get("own_niche_categories", [])
    adjacent_categories = ideas_config.get("adjacent_niche_categories", [])
    all_categories = own_categories + adjacent_categories

    monitored_raw = ideas_config.get("monitored_channels", {})
    competitor_channels = flatten_channels_by_category(monitored_raw, all_categories)

    errors: list[str] = []

    # Sample channels and keywords
    channel_items = list(competitor_channels.items())
    sampled_channels = random.sample(channel_items, min(args.max_channels, len(channel_items)))
    sampled_keywords = random.sample(niche_keywords, min(args.max_keywords, len(niche_keywords)))

    # ---------------------------------------------------------------------------
    # Three parallel workstreams
    # ---------------------------------------------------------------------------
    own_channel_videos: list[dict] = []
    competitor_videos: list[dict] = []
    search_suggestions: dict[str, list[str]] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        # Workstream A: Own channel
        own_future = pool.submit(
            fetch_channel_recent_videos, args.channel_id, "own_channel", 30
        )

        # Workstream B: Competitor channels
        comp_futures = {}
        for ch_id, ch_name in sampled_channels:
            future = pool.submit(fetch_channel_recent_videos, ch_id, ch_name, 15)
            comp_futures[future] = (ch_id, ch_name)

        # Workstream C: Search suggestions
        suggest_futures = {}
        for keyword in sampled_keywords:
            future = pool.submit(fetch_search_suggestions, keyword)
            suggest_futures[future] = keyword

        # Workstream D: Targeted search (if topic_hint provided)
        hint_future = None
        if args.topic_hint:
            hint_future = pool.submit(search_youtube, args.topic_hint, 20)

        # Collect own channel
        try:
            own_channel_videos = own_future.result()
        except Exception as e:
            errors.append(f"own_channel: {e}")

        # Collect competitor videos
        for future in concurrent.futures.as_completed(comp_futures):
            ch_id, ch_name = comp_futures[future]
            try:
                vids = future.result()
                for v in vids:
                    v["_source"] = "competitor"
                    v["_niche_category"] = next(
                        (cat for cat in all_categories
                         if ch_id in (monitored_raw.get(cat, {}))),
                        "unknown"
                    )
                competitor_videos.extend(vids)
            except Exception as e:
                errors.append(f"channel '{ch_name}': {e}")

        # Collect search suggestions
        for future in concurrent.futures.as_completed(suggest_futures):
            keyword = suggest_futures[future]
            try:
                suggestions = future.result()
                search_suggestions[keyword] = suggestions
            except Exception as e:
                errors.append(f"suggestions '{keyword}': {e}")

        # Collect targeted search results
        if hint_future:
            try:
                hint_videos = hint_future.result()
                for v in hint_videos:
                    v["_source"] = "targeted_search"
                    v["_topic_hint"] = args.topic_hint
                competitor_videos.extend(hint_videos)
            except Exception as e:
                errors.append(f"targeted_search '{args.topic_hint}': {e}")

    # ---------------------------------------------------------------------------
    # Enrich and filter
    # ---------------------------------------------------------------------------

    # Enrich own channel videos
    own_channel_videos = [enrich_video(v, shorts_aware=True) for v in own_channel_videos]
    # Filter to lookback period (keep videos with unknown upload date — flat-playlist
    # sometimes returns upload_date=None)
    own_channel_videos = [
        v for v in own_channel_videos
        if v.get("days_since_upload") is None or v["days_since_upload"] <= args.days
    ]

    # Calculate own channel average
    own_views = [v.get("view_count", 0) for v in own_channel_videos if v.get("view_count")]
    own_avg_views = int(sum(own_views) / len(own_views)) if own_views else 0

    # Enrich competitor videos
    competitor_videos = [enrich_video(v, shorts_aware=True) for v in competitor_videos]

    # Filter competitor videos by lookback period (keep if upload_date unknown)
    competitor_videos = [
        v for v in competitor_videos
        if v.get("days_since_upload") is None or v["days_since_upload"] <= args.days
    ]

    # Exclude own channel from competitors
    competitor_videos = [
        v for v in competitor_videos
        if v.get("channel_id") != args.channel_id
    ]

    # Format filtering
    if args.format == "longform":
        competitor_videos = [v for v in competitor_videos if not v.get("is_short")]
    elif args.format == "shorts":
        competitor_videos = [v for v in competitor_videos if v.get("is_short")]
    # "both" keeps everything

    # Deduplicate by video_id
    seen_ids: set[str] = set()
    unique_competitors: list[dict] = []
    for vid in competitor_videos:
        vid_id = vid.get("video_id")
        if vid_id and vid_id not in seen_ids:
            seen_ids.add(vid_id)
            unique_competitors.append(vid)

    # ---------------------------------------------------------------------------
    # Calculate outlier scores from already-fetched videos (no second pass)
    # ---------------------------------------------------------------------------

    # Group view counts by channel to compute averages in-memory
    channel_views: dict[str, list[int]] = defaultdict(list)
    for vid in unique_competitors:
        cid = vid.get("channel_id")
        vc = vid.get("view_count")
        if cid and vc is not None and vc > 0:
            channel_views[cid].append(vc)

    channel_avg_cache: dict[str, int] = {}
    for cid, views_list in channel_views.items():
        channel_avg_cache[cid] = int(sum(views_list) / len(views_list))

    for vid in unique_competitors:
        cid = vid.get("channel_id")
        avg = channel_avg_cache.get(cid) if cid else None
        if avg is None:
            subs = vid.get("channel_subscribers") or 0
            avg = max(int(subs * 0.02), 1)
        vid["channel_average_views"] = avg

        views = vid.get("view_count") or 0
        vid["outlier_score"] = round(views / max(avg, 1), 2)

    # Sort by outlier score descending
    unique_competitors.sort(key=lambda v: v.get("outlier_score", 0), reverse=True)

    elapsed = round(time.time() - start, 2)
    mins, secs = divmod(int(elapsed), 60)

    result = {
        "status": "success",
        "own_channel": {
            "channel_id": args.channel_id,
            "recent_videos": own_channel_videos,
            "average_views": own_avg_views,
            "total_videos_analyzed": len(own_channel_videos),
        },
        "competitor_videos": unique_competitors,
        "search_suggestions": search_suggestions,
        "channels_scanned": len(sampled_channels),
        "channels_sampled": [name for _, name in sampled_channels],
        "keywords_sampled": sampled_keywords,
        "total_competitor_videos": len(unique_competitors),
        "format_filter": args.format,
        "lookback_days": args.days,
        "elapsed_seconds": elapsed,
        "elapsed_formatted": f"{mins}m {secs:02d}s" if mins else f"{secs}s",
        "topic_hint": args.topic_hint,
        "errors": errors,
    }

    # Write to output file if specified
    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(json.dumps({
            "status": "success",
            "output": args.output,
            "total_competitor_videos": len(unique_competitors),
            "channels_scanned": len(sampled_channels),
            "elapsed_formatted": result["elapsed_formatted"],
        }))
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
