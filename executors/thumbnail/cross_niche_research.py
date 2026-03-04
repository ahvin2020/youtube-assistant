#!/usr/bin/env python3
"""Search YouTube for cross-niche outlier videos with transferable hooks.

Uses curated keyword lists, monitored channel scanning, and exclusion filters
from a config file to find high-performing videos from outside the user's niche.
Filters out own-niche content and non-transferable formats, keeping only genuine
outliers.

Two sources of cross-niche content:
  A) Keyword search — samples from curated cross_niche_keywords
  B) Channel monitoring — samples from monitored_channels and fetches recent videos

Usage:
    python3 executors/thumbnail/cross_niche_research.py <output_dir> \
        [--config workspace/config/cross_niche.json] \
        [--max-keywords 6] [--max-channels 8] [--count 100] \
        [--min-outlier 1.5] [--exclude-channel UC...]

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
from datetime import date, datetime
from typing import Optional


# ---------------------------------------------------------------------------
# YouTube search & metadata
# ---------------------------------------------------------------------------

def search_youtube(query: str, count: int) -> list[dict]:
    """Search YouTube via yt-dlp and return full video metadata."""
    cmd = [
        "yt-dlp",
        f"ytsearch{count}:{query}",
        "--dump-json",
        "--no-download",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp search failed: {result.stderr.strip()}")

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        vid = {
            "video_id": data.get("id"),
            "title": data.get("title"),
            "channel": data.get("channel") or data.get("uploader"),
            "channel_id": data.get("channel_id"),
            "channel_subscribers": data.get("channel_follower_count"),
            "channel_verified": data.get("channel_is_verified", False),
            "view_count": data.get("view_count"),
            "like_count": data.get("like_count"),
            "comment_count": data.get("comment_count"),
            "upload_date": data.get("upload_date"),
            "duration": data.get("duration"),
        }
        videos.append(vid)
    return videos


def enrich_video(vid: dict) -> dict:
    """Add computed fields to a video entry."""
    views = vid.get("view_count") or 0
    subs = vid.get("channel_subscribers") or 0
    likes = vid.get("like_count") or 0
    vid["views_per_subscriber"] = round(views / subs, 2) if subs > 0 else None
    vid["like_view_ratio"] = round(likes / views, 4) if views > 0 else None

    duration = vid.get("duration") or 0
    if duration < 300:
        vid["duration_category"] = "short"
    elif duration <= 900:
        vid["duration_category"] = "medium"
    else:
        vid["duration_category"] = "long"

    upload = vid.get("upload_date")
    if upload:
        try:
            upload_dt = datetime.strptime(upload, "%Y%m%d").date()
            vid["days_since_upload"] = (date.today() - upload_dt).days
        except ValueError:
            vid["days_since_upload"] = None
    else:
        vid["days_since_upload"] = None

    return vid


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


def fetch_transcript(video_id: str, output_path: str) -> Optional[str]:
    """Fetch auto-generated subtitles for a video using yt-dlp.

    Downloads the best available English auto-caption, converts to plain text
    (vtt → stripped text), and saves to output_path. Returns the path on
    success, None on failure.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    # Write subtitles to a temp location, then convert
    base = output_path.rsplit(".", 1)[0]
    cmd = [
        "yt-dlp",
        url,
        "--write-auto-sub",
        "--sub-lang", "en",
        "--sub-format", "vtt",
        "--skip-download",
        "--no-playlist",
        "-o", base,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return None

    # yt-dlp writes to <base>.en.vtt
    vtt_path = f"{base}.en.vtt"
    if not os.path.isfile(vtt_path):
        return None

    # Convert VTT to plain text (strip timestamps, tags, dedup lines)
    try:
        with open(vtt_path) as f:
            raw = f.read()
        lines: list[str] = []
        seen: set[str] = set()
        for line in raw.split("\n"):
            line = line.strip()
            # Skip VTT headers, timestamps, and empty lines
            if not line or line.startswith("WEBVTT") or line.startswith("Kind:") \
               or line.startswith("Language:") or "-->" in line or line[0:1].isdigit() and ":" in line:
                continue
            # Strip HTML-like tags
            clean = re.sub(r"<[^>]+>", "", line).strip()
            if clean and clean not in seen:
                seen.add(clean)
                lines.append(clean)
        text = " ".join(lines)
        with open(output_path, "w") as f:
            f.write(text)
        # Clean up VTT file
        os.remove(vtt_path)
        return output_path
    except Exception:
        return None


def fetch_channel_average_views(channel_id: str) -> int | None:
    """Fetch ~10 recent videos from a channel and calculate average views."""
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


def fetch_channel_recent_videos(channel_id: str, channel_name: str,
                                max_videos: int = 10) -> list[dict]:
    """Fetch recent videos from a monitored channel.

    Uses --flat-playlist for speed. Returns video dicts in the same format
    as search_youtube().
    """
    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    cmd = [
        "yt-dlp",
        url,
        "--flat-playlist",
        "--dump-json",
        "--no-download",
        "--playlist-items", f"1:{max_videos}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return []

    if result.returncode != 0:
        return []

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        vid = {
            "video_id": data.get("id"),
            "title": data.get("title"),
            "channel": channel_name,
            "channel_id": channel_id,
            "channel_subscribers": data.get("channel_follower_count"),
            "channel_verified": data.get("channel_is_verified", False),
            "view_count": data.get("view_count"),
            "like_count": data.get("like_count"),
            "comment_count": data.get("comment_count"),
            "upload_date": data.get("upload_date"),
            "duration": data.get("duration"),
            "_source": "channel",
            "_source_channel": channel_name,
        }
        videos.append(vid)
    return videos


# ---------------------------------------------------------------------------
# Cross-niche specific logic
# ---------------------------------------------------------------------------

def load_config(config_path: str) -> dict:
    """Load cross-niche config from JSON file."""
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path) as f:
        return json.load(f)


def flatten_monitored_channels(monitored: dict) -> dict[str, str]:
    """Flatten nested category → {channel_id: name} into a flat dict.

    Config format:
        {"business": {"UCxxx": "Alex Hormozi", ...}, "finance": {...}, ...}
    Returns:
        {"UCxxx": "Alex Hormozi", "UCyyy": "Graham Stephan", ...}
    """
    flat: dict[str, str] = {}
    for _category, channels in monitored.items():
        if isinstance(channels, dict):
            flat.update(channels)
    return flat


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
    exclude_channel: str | None = None,
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
        "filtered_own_channel": 0,
    }
    filtered = []

    for vid in videos:
        title = vid.get("title") or ""

        # Exclude own channel
        if exclude_channel and vid.get("channel_id") == exclude_channel:
            stats["filtered_own_channel"] += 1
            continue

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


def apply_hook_modifiers(videos: list[dict], config: dict) -> None:
    """Apply cross-niche hook modifiers to each video based on title text.

    Modifiers are keyword-matched from ``hook_categories`` in the config.
    Technical penalty is applied per technical term found.  The monitored
    channel boost is data-driven (``_is_monitored`` flag).

    Mutates each video dict in-place, adding:
        modifiers      – list of human-readable modifier strings
        modifier_sum   – float total of all modifiers
        final_score    – base_score × (1 + modifier_sum)
    """
    hook_cats = config.get("hook_categories", {})
    tech_terms = [t.lower() for t in config.get("technical_terms", [])]

    for vid in videos:
        title_lower = (vid.get("title") or "").lower()
        mods: list[str] = []
        mod_sum = 0.0

        # Monitored channel boost (data-driven, not text-based)
        if vid.get("_is_monitored"):
            mods.append("+0.25 (monitored channel)")
            mod_sum += 0.25

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


def main():
    parser = argparse.ArgumentParser(
        description="Search YouTube for cross-niche outlier videos with transferable hooks."
    )
    parser.add_argument("output_dir",
                        help="Directory to save downloaded thumbnails and metadata")
    parser.add_argument("--config",
                        default=os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "workspace", "config", "cross_niche.json"
                        ),
                        help="Path to cross_niche.json config file")
    parser.add_argument("--max-keywords", type=int, default=6,
                        help="Number of keywords to randomly sample per run (default: 6)")
    parser.add_argument("--max-channels", type=int, default=8,
                        help="Number of monitored channels to randomly sample per run (default: 8)")
    parser.add_argument("--count", type=int, default=100,
                        help="Number of outlier thumbnails to keep (default: 100)")
    parser.add_argument("--min-outlier", type=float, default=1.5,
                        help="Minimum outlier score to keep (default: 1.5)")
    parser.add_argument("--exclude-channel",
                        help="YouTube channel ID to exclude (e.g., UCxxx)")
    args = parser.parse_args()

    start = time.time()

    # Load config
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)

    keywords = config.get("cross_niche_keywords", [])
    monitored_channels_raw = config.get("monitored_channels", {})
    monitored_channels = flatten_monitored_channels(monitored_channels_raw)
    monitored_channel_ids: set[str] = set(monitored_channels.keys())
    own_niche_terms = config.get("own_niche_terms", [])
    exclude_formats = config.get("exclude_formats", [])
    constants = config.get("constants", {})
    min_subscribers = constants.get("min_subscribers", 100000)
    min_view_count = constants.get("min_view_count", 1000)
    min_duration = constants.get("min_video_duration_seconds", 180)
    max_per_keyword = constants.get("max_videos_per_keyword", 30)

    if not keywords and not monitored_channels:
        print(json.dumps({
            "status": "error",
            "error": "No cross_niche_keywords or monitored_channels found in config file.",
        }))
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    all_videos: list[dict] = []
    search_errors: list[str] = []
    videos_from_keywords = 0
    videos_from_channels = 0

    # --- Source A: Keyword search (parallel) ---
    sampled_keywords = []
    if keywords:
        sampled_keywords = random.sample(keywords, min(args.max_keywords, len(keywords)))

    # --- Source B: Monitored channel scanning (parallel) ---
    sampled_channels: list[tuple[str, str]] = []
    if monitored_channels:
        channel_items = list(monitored_channels.items())  # flat: [(id, name), ...]
        sampled_channels = random.sample(channel_items, min(args.max_channels, len(channel_items)))

    # Run keyword searches and channel scans concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        keyword_futures = {}
        for keyword in sampled_keywords:
            future = pool.submit(search_youtube, keyword, max_per_keyword)
            keyword_futures[future] = keyword

        channel_futures = {}
        for channel_id, channel_name in sampled_channels:
            future = pool.submit(fetch_channel_recent_videos, channel_id, channel_name, max_videos=10)
            channel_futures[future] = (channel_id, channel_name)

        for future in concurrent.futures.as_completed(keyword_futures):
            keyword = keyword_futures[future]
            try:
                videos = future.result()
                for v in videos:
                    v["_source"] = "keyword"
                    v["_search_keyword"] = keyword
                videos_from_keywords += len(videos)
                all_videos.extend(videos)
            except FileNotFoundError:
                print(json.dumps({
                    "status": "error",
                    "error": "yt-dlp not found. Install with: brew install yt-dlp",
                }))
                sys.exit(1)
            except RuntimeError as e:
                search_errors.append(f"keyword '{keyword}': {e}")

        for future in concurrent.futures.as_completed(channel_futures):
            channel_id, channel_name = channel_futures[future]
            try:
                videos = future.result()
                videos_from_channels += len(videos)
                all_videos.extend(videos)
            except Exception as e:
                search_errors.append(f"channel '{channel_name}': {e}")

    if not all_videos:
        print(json.dumps({
            "status": "error",
            "error": f"No results from any source. Errors: {search_errors}",
        }))
        sys.exit(1)

    # Deduplicate by video_id
    seen_ids: set[str] = set()
    unique_videos: list[dict] = []
    for vid in all_videos:
        vid_id = vid.get("video_id")
        if vid_id and vid_id not in seen_ids:
            seen_ids.add(vid_id)
            unique_videos.append(vid)
    duplicates_removed = len(all_videos) - len(unique_videos)

    # Tag monitored channel status (applies to keyword-sourced videos too)
    for vid in unique_videos:
        vid["_is_monitored"] = vid.get("channel_id") in monitored_channel_ids

    # Apply cross-niche filters (own-niche, format, views, duration, subscribers)
    videos, filter_stats = filter_cross_niche(
        unique_videos,
        own_niche_terms,
        exclude_formats,
        min_view_count=min_view_count,
        min_duration=min_duration,
        exclude_channel=args.exclude_channel,
        min_subscribers=min_subscribers,
    )

    if not videos:
        print(json.dumps({
            "status": "error",
            "error": "All results were filtered out. Try more keywords or relax filters.",
            "filter_stats": filter_stats,
            "keywords_searched": sampled_keywords,
        }))
        sys.exit(1)

    # Enrich with computed fields
    videos = [enrich_video(v) for v in videos]

    # Fetch channel average views and calculate outlier scores (always-on)
    unique_channel_ids = {v.get("channel_id") for v in videos if v.get("channel_id")}
    channel_cache: dict[str, int | None] = {}

    # Fetch all channel averages in parallel
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
            # Fallback: estimate average as 2% of subscriber count
            subs = vid.get("channel_subscribers") or 0
            avg = max(int(subs * 0.02), 1)
        vid["channel_average_views"] = avg

        views = vid.get("view_count") or 0
        vid["outlier_score"] = round(views / max(avg, 1), 2)

    # Add recency multiplier and base score
    for vid in videos:
        days = vid.get("days_since_upload")
        if days is not None:
            if days <= 30:
                vid["recency_multiplier"] = 1.15
            elif days <= 90:
                vid["recency_multiplier"] = 1.10
            elif days <= 180:
                vid["recency_multiplier"] = 1.0
            else:
                vid["recency_multiplier"] = 0.95
        else:
            vid["recency_multiplier"] = 1.0

        outlier = vid.get("outlier_score", 1.0)
        vid["base_score"] = round(outlier * vid["recency_multiplier"], 2)

    # Apply cross-niche hook modifiers (title-based keyword matching)
    apply_hook_modifiers(videos, config)

    # Filter by minimum outlier score
    before_outlier = len(videos)
    videos = [v for v in videos if v.get("outlier_score", 0) >= args.min_outlier]
    outlier_filtered = before_outlier - len(videos)

    if not videos:
        print(json.dumps({
            "status": "error",
            "error": f"No videos above outlier threshold ({args.min_outlier}). "
                     "Try lowering --min-outlier or searching more keywords.",
            "filter_stats": filter_stats,
            "keywords_searched": sampled_keywords,
        }))
        sys.exit(1)

    # Sort by final score (with modifiers) descending, take top N
    videos.sort(key=lambda v: v.get("final_score", v.get("outlier_score", 0)), reverse=True)
    videos = videos[:args.count]

    # Download thumbnails + fetch transcripts (parallel)
    thumbnails = []
    for i, vid in enumerate(videos):
        vid["index"] = i
        vid["thumbnail_url"] = f"https://img.youtube.com/vi/{vid['video_id']}/maxresdefault.jpg"
        thumbnails.append(vid)

    transcript_dir = os.path.join(args.output_dir, "transcripts")
    os.makedirs(transcript_dir, exist_ok=True)
    transcripts_fetched = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        # Submit thumbnail downloads
        thumb_futures = {}
        for vid in thumbnails:
            filename = f"thumb_{vid['index']:02d}_{vid['video_id']}.jpg"
            filepath = os.path.join(args.output_dir, filename)
            future = pool.submit(download_thumbnail, vid["video_id"], filepath)
            thumb_futures[future] = vid

        # Submit transcript fetches
        tx_futures = {}
        for vid in thumbnails:
            tx_path = os.path.join(transcript_dir, f"{vid['video_id']}.txt")
            future = pool.submit(fetch_transcript, vid["video_id"], tx_path)
            tx_futures[future] = vid

        # Collect thumbnail results
        for future in concurrent.futures.as_completed(thumb_futures):
            vid = thumb_futures[future]
            try:
                result_path = future.result()
                vid["local_path"] = os.path.abspath(result_path) if result_path else None
            except Exception:
                vid["local_path"] = None

        # Collect transcript results
        for future in concurrent.futures.as_completed(tx_futures):
            vid = tx_futures[future]
            try:
                tx_result = future.result()
                vid["transcript_path"] = os.path.abspath(tx_result) if tx_result else None
                if tx_result:
                    transcripts_fetched += 1
            except Exception:
                vid["transcript_path"] = None

    # Save metadata
    metadata_path = os.path.join(args.output_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(thumbnails, f, indent=2)

    downloaded = sum(1 for t in thumbnails if t["local_path"] is not None)
    elapsed = round(time.time() - start, 2)
    mins, secs = divmod(int(elapsed), 60)
    elapsed_fmt = f"{mins}m {secs:02d}s" if mins else f"{secs}s"

    result = {
        "status": "success",
        "query": f"cross-niche ({len(sampled_keywords)} keywords + {len(sampled_channels)} channels)",
        "keywords_searched": sampled_keywords,
        "channels_scanned": [name for _, name in sampled_channels],
        "videos_from_keywords": videos_from_keywords,
        "videos_from_channels": videos_from_channels,
        "channels_fetched": channels_fetched,
        "thumbnails_downloaded": downloaded,
        "thumbnails_total": len(thumbnails),
        "videos_scanned": len(all_videos),
        "duplicates_removed": duplicates_removed,
        "filtered_own_niche": filter_stats.get("filtered_own_niche", 0),
        "filtered_formats": filter_stats.get("filtered_formats", 0),
        "filtered_views": filter_stats.get("filtered_views", 0),
        "filtered_duration": filter_stats.get("filtered_duration", 0),
        "filtered_subscribers": filter_stats.get("filtered_subscribers", 0),
        "filtered_below_outlier": outlier_filtered,
        "transcripts_fetched": transcripts_fetched,
        "output_dir": os.path.abspath(args.output_dir),
        "metadata_file": os.path.abspath(metadata_path),
        "elapsed_seconds": elapsed,
        "elapsed_formatted": elapsed_fmt,
    }
    if search_errors:
        result["search_errors"] = search_errors

    print(json.dumps(result))


if __name__ == "__main__":
    main()
