#!/usr/bin/env python3
"""Search YouTube for cross-niche outlier videos with transferable hooks.

Fetches recent videos from a curated list of thumbnail-quality channels
(memory/thumbnail-channels.md), scores them by outlier performance, and
downloads the top thumbnails.

Features:
  - Rotation tracking: cycles through the full channel pool before repeating
  - Seen-video tracking: prevents the same video from appearing across runs
  - Topic relevance: boosts videos related to the current topic (+35%)

Usage:
    python3 executors/thumbnail/cross_niche_research.py <output_dir> \
        [--thumbnail-channels memory/thumbnail-channels.md] \
        [--topic "retire early"] \
        [--config workspace/config/research_config.json] \
        [--max-channels 20] [--count 70] [--min-outlier 1.5]

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
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Optional

_EXECUTORS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EXECUTORS_DIR not in sys.path:
    sys.path.insert(0, _EXECUTORS_DIR)
from shared.youtube import fetch_channel_recent_videos, enrich_video
from shared.parse_profile import parse_channel_profile, parse_thumbnail_channels


# ---------------------------------------------------------------------------
# Thumbnail download
# ---------------------------------------------------------------------------

def download_thumbnail(video_id: str, output_path: str) -> Optional[str]:
    """Download the highest-quality thumbnail for a video ID."""
    urls = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    data = resp.read()
                    if len(data) < 5000 and url.endswith("maxresdefault.jpg"):
                        continue
                    with open(output_path, "wb") as f:
                        f.write(data)
                    return output_path
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            continue
    return None


# ---------------------------------------------------------------------------
# Channel average views
# ---------------------------------------------------------------------------

def fetch_channel_average_views(channel_id: str) -> int | None:
    """Fetch recent videos from a channel and calculate average views."""
    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    cmd = [
        "yt-dlp",
        url,
        "--flat-playlist",
        "--dump-json",
        "--no-download",
        "--playlist-items", "1:10",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None

    if result.returncode != 0:
        return None

    view_counts = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            vc = data.get("view_count")
            if vc is not None and vc > 0:
                view_counts.append(vc)
        except json.JSONDecodeError:
            continue

    if not view_counts:
        return None

    return int(sum(view_counts) / len(view_counts))


# ---------------------------------------------------------------------------
# Seen-video tracking (cross-run deduplication)
# ---------------------------------------------------------------------------

def load_seen_file(path: str) -> dict:
    """Load seen video tracking file. Returns empty structure if missing."""
    if not os.path.isfile(path):
        return {"seen": {}, "last_cleaned": ""}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"seen": {}, "last_cleaned": ""}


def save_seen_videos(path: str, new_video_ids: list[str], existing: dict) -> None:
    """Add video IDs to seen file with today's date. Auto-prune >1 month old."""
    today = datetime.now().strftime("%Y-%m-%d")
    seen = existing.get("seen", {})

    # Add new entries
    for vid_id in new_video_ids:
        if vid_id not in seen:
            seen[vid_id] = today

    # Auto-prune entries older than 1 month
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    last_cleaned = existing.get("last_cleaned", "")
    if not last_cleaned or last_cleaned < cutoff:
        seen = {k: v for k, v in seen.items() if v >= cutoff}
        last_cleaned = today

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"seen": seen, "last_cleaned": last_cleaned}, f, indent=2)


# ---------------------------------------------------------------------------
# Rotation tracking (channel sampling fairness)
# ---------------------------------------------------------------------------

def load_rotation_file(path: str) -> dict[str, str]:
    """Load channel rotation tracking. Returns empty dict if missing."""
    if not os.path.isfile(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_rotation(path: str, channel_ids: list[str], existing: dict) -> None:
    """Update last-sampled date for channels."""
    today = datetime.now().strftime("%Y-%m-%d")
    for cid in channel_ids:
        existing[cid] = today
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(existing, f, indent=2)


def sample_with_rotation(
    channels: dict[str, str],
    rotation: dict[str, str],
    count: int,
) -> list[tuple[str, str]]:
    """Sample channels prioritizing least-recently-sampled.

    Channels never sampled before get highest priority. Among channels with
    the same last-sampled date, selection is random.
    """
    items = list(channels.items())
    # Sort by last-sampled date (never-sampled = "" sorts first)
    items.sort(key=lambda x: rotation.get(x[0], ""))
    # Take the least-recently-sampled batch and randomly pick from it
    if len(items) <= count:
        return items
    # Find the cutoff: take at least `count` items, expanding if there's a tie
    cutoff_date = rotation.get(items[count - 1][0], "")
    candidates = [x for x in items if rotation.get(x[0], "") <= cutoff_date]
    return random.sample(candidates, min(count, len(candidates)))


# ---------------------------------------------------------------------------
# Topic relevance scoring
# ---------------------------------------------------------------------------

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "and", "but", "or",
    "nor", "not", "so", "yet", "both", "either", "neither", "each",
    "every", "all", "any", "few", "more", "most", "other", "some",
    "such", "no", "only", "own", "same", "than", "too", "very",
    "just", "about", "how", "what", "why", "when", "where", "which",
    "who", "whom", "this", "that", "these", "those", "i", "me", "my",
    "you", "your", "he", "him", "his", "she", "her", "it", "its",
    "we", "us", "our", "they", "them", "their",
}


def extract_topic_keywords(topic: str) -> list[str]:
    """Extract meaningful keywords from a topic string."""
    words = re.findall(r"[a-zA-Z0-9]+", topic.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def topic_matches_title(title: str, topic_keywords: list[str]) -> bool:
    """Check if any topic keyword appears in the title."""
    title_lower = title.lower()
    return any(kw in title_lower for kw in topic_keywords)


# ---------------------------------------------------------------------------
# Cross-niche filtering and scoring
# ---------------------------------------------------------------------------

def load_config(config_path: str) -> dict:
    """Load research config (scoring rules, filters, thresholds) from JSON."""
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path) as f:
        return json.load(f)


def title_matches_terms(title: str, terms: list[str]) -> list[str]:
    """Check if a title matches any terms (case-insensitive).

    Returns list of matched terms.
    """
    title_lower = title.lower()
    matched = []
    for term in terms:
        term_lower = term.lower()
        # Word boundary check for short terms (2-3 chars) to avoid false positives
        if len(term_lower) <= 3:
            pattern = r'\b' + re.escape(term_lower) + r'\b'
            if re.search(pattern, title_lower):
                matched.append(term)
        else:
            if term_lower in title_lower:
                matched.append(term)
    return matched


def filter_cross_niche(
    videos: list[dict],
    own_niche_terms: list[str],
    exclude_formats: list[str],
    min_view_count: int = 1000,
    min_duration: int = 180,
    min_subscribers: int | None = None,
) -> tuple[list[dict], dict]:
    """Apply cross-niche filters: own-niche, format, duration, views.

    Returns (filtered_list, filter_stats).
    """
    stats = {
        "total_input": len(videos),
        "filtered_own_niche": 0,
        "filtered_formats": 0,
        "filtered_views": 0,
        "filtered_duration": 0,
        "filtered_subscribers": 0,
    }
    filtered = []

    for vid in videos:
        title = vid.get("title") or ""

        # Exclude own-niche content
        if title_matches_terms(title, own_niche_terms):
            stats["filtered_own_niche"] += 1
            continue

        # Exclude non-transferable formats
        if title_matches_terms(title, exclude_formats):
            stats["filtered_formats"] += 1
            continue

        # Minimum view count
        if (vid.get("view_count") or 0) < min_view_count:
            stats["filtered_views"] += 1
            continue

        # Minimum duration (filter out shorts)
        if (vid.get("duration") or 0) < min_duration:
            stats["filtered_duration"] += 1
            continue

        # Minimum subscribers
        if min_subscribers and (vid.get("channel_subscribers") or 0) < min_subscribers:
            stats["filtered_subscribers"] += 1
            continue

        filtered.append(vid)

    stats["remaining"] = len(filtered)
    return filtered, stats


def apply_hook_modifiers(
    videos: list[dict],
    config: dict,
    topic_keywords: list[str] | None = None,
) -> None:
    """Apply hook modifiers to each video based on title text.

    Includes topic relevance boost (+35%) when topic_keywords are provided.
    Mutates each video dict in-place.
    """
    hook_cats = config.get("hook_categories", {})
    tech_terms = [t.lower() for t in config.get("technical_terms", [])]

    for vid in videos:
        title_lower = (vid.get("title") or "").lower()
        mods: list[str] = []
        mod_sum = 0.0

        # Topic relevance boost
        if topic_keywords and topic_matches_title(vid.get("title", ""), topic_keywords):
            mods.append("+0.35 (topic relevance)")
            mod_sum += 0.35

        # Hook category modifiers (scan title)
        for cat_name, cat_data in hook_cats.items():
            if cat_name == "technical_penalty":
                continue
            if not isinstance(cat_data, dict):
                continue
            terms = [t.lower() for t in cat_data.get("terms", [])]
            modifier = cat_data.get("modifier", 0)
            if any(term in title_lower for term in terms):
                mods.append(f"+{modifier:.2f} ({cat_name})")
                mod_sum += modifier

        # Technical penalty (per term found)
        tech_count = sum(1 for t in tech_terms if t in title_lower)
        if tech_count > 0:
            penalty = -0.20 * tech_count
            mods.append(f"{penalty:.2f} (technical x{tech_count})")
            mod_sum += penalty

        vid["modifiers"] = mods
        vid["modifier_sum"] = round(mod_sum, 2)
        vid["final_score"] = round(
            vid.get("base_score", 0) * (1 + mod_sum), 2
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Search YouTube for cross-niche outlier videos with transferable hooks."
    )
    parser.add_argument("output_dir",
                        help="Directory to save downloaded thumbnails and metadata")
    parser.add_argument("--config",
                        default=os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "workspace", "config", "research_config.json"
                        ),
                        help="Path to research_config.json config file")
    parser.add_argument("--thumbnail-channels",
                        default=os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "memory", "thumbnail-channels.md"
                        ),
                        help="Path to thumbnail-channels.md (curated channel list)")
    parser.add_argument("--topic", default=None,
                        help="Video topic for relevance scoring (e.g. 'retire early')")
    parser.add_argument("--max-channels", type=int, default=20,
                        help="Number of channels to sample per run (default: 20)")
    parser.add_argument("--count", type=int, default=70,
                        help="Number of outlier thumbnails to keep (default: 70)")
    parser.add_argument("--min-outlier", type=float, default=1.5,
                        help="Minimum outlier score to keep (default: 1.5)")
    parser.add_argument("--channel-profile",
                        default=os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "memory", "channel-profile.md"
                        ),
                        help="Path to channel-profile.md (source of niche terms)")
    parser.add_argument("--seen-file",
                        default=os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "workspace", "config", "thumbnail_seen.json"
                        ),
                        help="Path to seen-video tracking file")
    parser.add_argument("--rotation-file",
                        default=os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "workspace", "config", "thumbnail_rotation.json"
                        ),
                        help="Path to channel rotation tracking file")
    args = parser.parse_args()

    start = time.time()

    # Load config
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)

    # Load curated thumbnail channels
    channels_path = args.thumbnail_channels
    if not os.path.isfile(channels_path):
        print(json.dumps({
            "status": "error",
            "error": f"Thumbnail channels file not found: {channels_path}. "
                     "Create memory/thumbnail-channels.md with curated channels.",
        }))
        sys.exit(1)

    curated_channels = parse_thumbnail_channels(channels_path)
    if not curated_channels:
        print(json.dumps({
            "status": "error",
            "error": "No channels found in thumbnail-channels.md.",
        }))
        sys.exit(1)

    # Channel-specific config from profile (for niche term filtering)
    profile = parse_channel_profile(args.channel_profile)
    own_niche_terms = profile.get("niche_terms", [])

    # System config from research_config.json
    exclude_formats = config.get("exclude_formats", [])
    constants = config.get("constants", {})
    min_subscribers = constants.get("min_subscribers", 100000)
    min_view_count = constants.get("min_view_count", 1000)
    min_duration = constants.get("min_video_duration_seconds", 180)

    # Topic relevance keywords
    topic_keywords = extract_topic_keywords(args.topic) if args.topic else None

    # Load tracking state
    seen_data = load_seen_file(args.seen_file)
    seen_ids = set(seen_data.get("seen", {}).keys())
    rotation = load_rotation_file(args.rotation_file)

    # Sample channels with rotation
    sampled = sample_with_rotation(curated_channels, rotation, args.max_channels)

    os.makedirs(args.output_dir, exist_ok=True)

    all_videos: list[dict] = []
    scan_errors: list[str] = []

    # Fetch recent videos from sampled channels (parallel)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        channel_futures = {}
        for channel_id, channel_name in sampled:
            future = pool.submit(fetch_channel_recent_videos, channel_id, channel_name, max_videos=5)
            channel_futures[future] = (channel_id, channel_name)

        for future in concurrent.futures.as_completed(channel_futures):
            channel_id, channel_name = channel_futures[future]
            try:
                videos = future.result()
                for v in videos:
                    v["_source"] = "curated"
                    v["_source_channel"] = channel_name
                all_videos.extend(videos)
            except FileNotFoundError:
                print(json.dumps({
                    "status": "error",
                    "error": "yt-dlp not found. Install with: brew install yt-dlp",
                }))
                sys.exit(1)
            except Exception as e:
                scan_errors.append(f"channel '{channel_name}': {e}")

    if not all_videos:
        print(json.dumps({
            "status": "error",
            "error": f"No results from any channel. Errors: {scan_errors}",
        }))
        sys.exit(1)

    # Deduplicate by video_id (within this run)
    dedup_ids: set[str] = set()
    unique_videos: list[dict] = []
    for vid in all_videos:
        vid_id = vid.get("video_id")
        if vid_id and vid_id not in dedup_ids:
            dedup_ids.add(vid_id)
            unique_videos.append(vid)
    duplicates_removed = len(all_videos) - len(unique_videos)

    # Filter out previously seen videos (cross-run dedup)
    before_seen = len(unique_videos)
    unique_videos = [v for v in unique_videos if v.get("video_id") not in seen_ids]
    seen_filtered = before_seen - len(unique_videos)

    # Apply cross-niche filters (own-niche, format, views, duration, subscribers)
    videos, filter_stats = filter_cross_niche(
        unique_videos,
        own_niche_terms,
        exclude_formats,
        min_view_count=min_view_count,
        min_duration=min_duration,
        min_subscribers=min_subscribers,
    )

    if not videos:
        print(json.dumps({
            "status": "error",
            "error": "All results were filtered out. Add more channels to thumbnail-channels.md.",
            "filter_stats": filter_stats,
            "channels_sampled": [name for _, name in sampled],
        }))
        sys.exit(1)

    # Enrich with computed fields
    videos = [enrich_video(v) for v in videos]

    # Fetch channel average views and calculate outlier scores
    unique_channel_ids = {v.get("channel_id") for v in videos if v.get("channel_id")}
    channel_cache: dict[str, int | None] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        future_to_cid = {
            pool.submit(fetch_channel_average_views, cid): cid
            for cid in unique_channel_ids
        }
        for future in concurrent.futures.as_completed(future_to_cid):
            cid = future_to_cid[future]
            try:
                channel_cache[cid] = future.result()
            except Exception:
                channel_cache[cid] = None

    channels_fetched = len(channel_cache)

    # Calculate outlier score: views / channel_average_views
    for vid in videos:
        cid = vid.get("channel_id")
        avg = channel_cache.get(cid) if cid else None
        if avg is None:
            subs = vid.get("channel_subscribers") or 0
            avg = max(int(subs * 0.02), 1)
        vid["channel_average_views"] = avg

        views = vid.get("view_count") or 0
        vid["outlier_score"] = round(views / max(avg, 1), 2)

    # Add recency multiplier and base score
    for vid in videos:
        days = vid.get("days_since_upload")
        if days is not None:
            if days <= 7:
                vid["recency_multiplier"] = 1.30
            elif days <= 30:
                vid["recency_multiplier"] = 1.15
            elif days <= 90:
                vid["recency_multiplier"] = 1.0
            elif days <= 180:
                vid["recency_multiplier"] = 0.85
            else:
                vid["recency_multiplier"] = 0.70
        else:
            vid["recency_multiplier"] = 1.0

        outlier = vid.get("outlier_score", 1.0)
        vid["base_score"] = round(outlier * vid["recency_multiplier"], 2)

    # Apply hook modifiers (title-based keyword matching + topic relevance)
    apply_hook_modifiers(videos, config, topic_keywords)

    # Filter by minimum outlier score
    before_outlier = len(videos)
    videos = [v for v in videos if v.get("outlier_score", 0) >= args.min_outlier]
    outlier_filtered = before_outlier - len(videos)

    if not videos:
        print(json.dumps({
            "status": "error",
            "error": f"No videos above outlier threshold ({args.min_outlier}). "
                     "Try lowering --min-outlier or adding more channels.",
            "filter_stats": filter_stats,
            "channels_sampled": [name for _, name in sampled],
        }))
        sys.exit(1)

    # Sort by final score descending, take top N
    videos.sort(key=lambda v: v.get("final_score", v.get("outlier_score", 0)), reverse=True)
    videos = videos[:args.count]

    # Download thumbnails (parallel)
    thumbnails = []
    for i, vid in enumerate(videos):
        vid["index"] = i
        vid["thumbnail_url"] = f"https://img.youtube.com/vi/{vid['video_id']}/maxresdefault.jpg"
        thumbnails.append(vid)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        thumb_futures = {}
        for vid in thumbnails:
            filename = f"thumb_{vid['index']:02d}_{vid['video_id']}.jpg"
            filepath = os.path.join(args.output_dir, filename)
            future = pool.submit(download_thumbnail, vid["video_id"], filepath)
            thumb_futures[future] = vid

        for future in concurrent.futures.as_completed(thumb_futures):
            vid = thumb_futures[future]
            try:
                result_path = future.result()
                vid["local_path"] = os.path.abspath(result_path) if result_path else None
            except Exception:
                vid["local_path"] = None

    # Save metadata
    metadata_path = os.path.join(args.output_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(thumbnails, f, indent=2)

    # Update tracking state
    result_video_ids = [v["video_id"] for v in thumbnails if v.get("video_id")]
    save_seen_videos(args.seen_file, result_video_ids, seen_data)
    sampled_channel_ids = [cid for cid, _ in sampled]
    save_rotation(args.rotation_file, sampled_channel_ids, rotation)

    downloaded = sum(1 for t in thumbnails if t["local_path"] is not None)
    elapsed = round(time.time() - start, 2)
    mins, secs = divmod(int(elapsed), 60)
    elapsed_fmt = f"{mins}m {secs:02d}s" if mins else f"{secs}s"

    result = {
        "status": "success",
        "query": f"curated channels ({len(sampled)} of {len(curated_channels)} sampled)",
        "channels_sampled": [name for _, name in sampled],
        "total_curated_channels": len(curated_channels),
        "videos_scanned": len(all_videos),
        "duplicates_removed": duplicates_removed,
        "seen_filtered": seen_filtered,
        "channels_fetched": channels_fetched,
        "thumbnails_downloaded": downloaded,
        "thumbnails_total": len(thumbnails),
        "filtered_own_niche": filter_stats.get("filtered_own_niche", 0),
        "filtered_formats": filter_stats.get("filtered_formats", 0),
        "filtered_views": filter_stats.get("filtered_views", 0),
        "filtered_duration": filter_stats.get("filtered_duration", 0),
        "filtered_subscribers": filter_stats.get("filtered_subscribers", 0),
        "filtered_below_outlier": outlier_filtered,
        "topic": args.topic,
        "topic_keywords": topic_keywords,
        "output_dir": os.path.abspath(args.output_dir),
        "metadata_file": os.path.abspath(metadata_path),
        "elapsed_seconds": elapsed,
        "elapsed_formatted": elapsed_fmt,
    }
    if scan_errors:
        result["scan_errors"] = scan_errors

    print(json.dumps(result))


if __name__ == "__main__":
    main()
