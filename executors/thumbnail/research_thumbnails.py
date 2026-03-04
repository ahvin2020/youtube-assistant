#!/usr/bin/env python3
"""Search YouTube for a topic and download top thumbnail images for analysis.

Usage:
    python3 executors/thumbnail/research_thumbnails.py <query> <output_dir> \
        [--count 10] [--exclude-channel UC...] [--date-after YYYYMMDD] \
        [--min-subscribers 100000] [--sort-by relevance|views|performance] \
        [--fetch-channel-stats]

Depends on: yt-dlp (brew install yt-dlp)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from datetime import date, datetime
from typing import Optional


def search_youtube(query: str, count: int) -> list[dict]:
    """Search YouTube via yt-dlp and return full video metadata.

    Uses --dump-json (no --flat-playlist) to get performance fields:
    view_count, like_count, upload_date, channel_follower_count, etc.
    Slower (~3s/video) but much richer data.
    """
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


def filter_videos(
    videos: list[dict],
    exclude_channel: str | None,
    date_after: str | None,
    min_subscribers: int | None = None,
) -> tuple[list[dict], int]:
    """Filter out own-channel videos, videos older than date_after,
    and channels below the minimum subscriber threshold.

    Returns (filtered_list, count_removed).
    """
    original_count = len(videos)
    filtered = []
    for vid in videos:
        if exclude_channel and vid.get("channel_id") == exclude_channel:
            continue
        if date_after and vid.get("upload_date"):
            if vid["upload_date"] < date_after:
                continue
        if min_subscribers and (vid.get("channel_subscribers") or 0) < min_subscribers:
            continue
        filtered.append(vid)
    return filtered, original_count - len(filtered)


def sort_videos(videos: list[dict], sort_by: str) -> list[dict]:
    """Sort videos by the chosen strategy."""
    if sort_by == "views":
        return sorted(videos, key=lambda v: v.get("view_count") or 0, reverse=True)
    elif sort_by == "performance":
        def perf_score(v):
            views = v.get("view_count") or 0
            subs = v.get("channel_subscribers") or 1
            return views / subs
        return sorted(videos, key=perf_score, reverse=True)
    # relevance = keep YouTube's original order
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
    """Download the highest-quality thumbnail for a video ID.

    Tries maxresdefault first, falls back to hqdefault.
    Returns the path on success, None on failure.
    """
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
                    # maxresdefault returns a tiny placeholder if unavailable
                    if len(data) < 5000 and url.endswith("maxresdefault.jpg"):
                        continue
                    with open(output_path, "wb") as f:
                        f.write(data)
                    return output_path
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            continue
    return None


def fetch_channel_average_views(channel_id: str) -> int | None:
    """Fetch ~10 recent videos from a channel and calculate average views.

    Uses --flat-playlist for fast channel page scraping.
    Returns average view count, or None on failure.
    """
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


def _parse_vtt_to_text(vtt_content: str) -> str:
    """Parse WebVTT content into plain text, deduplicating auto-caption repeats."""
    timestamp_pattern = re.compile(
        r"\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}"
    )
    lines = vtt_content.strip().split("\n")
    texts = []
    prev_text = ""
    i = 0
    while i < len(lines):
        if timestamp_pattern.match(lines[i]):
            # Collect text lines after timestamp
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip() and not timestamp_pattern.match(lines[i]):
                clean = re.sub(r"<[^>]+>", "", lines[i]).strip()
                if clean:
                    text_lines.append(clean)
                i += 1
            text = " ".join(text_lines).strip()
            if text and text != prev_text:
                texts.append(text)
                prev_text = text
        else:
            i += 1
    return " ".join(texts)


def fetch_video_transcript(video_id: str, transcript_dir: str) -> tuple[str | None, str | None]:
    """Fetch auto-captions for a video. Returns (hook_text, transcript_path).

    hook_text = first ~500 words of transcript (the opening/hook).
    transcript_path = path to full transcript text file.
    Returns (None, None) if no captions available.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_template = os.path.join(tmpdir, "subs")
        cmd = [
            "yt-dlp",
            "--write-auto-subs",
            "--sub-langs", "en",
            "--skip-download",
            "--sub-format", "vtt",
            "--convert-subs", "vtt",
            "-o", output_template,
            f"https://www.youtube.com/watch?v={video_id}",
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            return None, None

        vtt_files = [f for f in os.listdir(tmpdir) if f.endswith(".vtt")]
        if not vtt_files:
            return None, None

        with open(os.path.join(tmpdir, vtt_files[0]), "r", encoding="utf-8") as f:
            vtt_content = f.read()

    full_text = _parse_vtt_to_text(vtt_content)
    if not full_text:
        return None, None

    # Save full transcript
    transcript_path = os.path.join(transcript_dir, f"{video_id}.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    # Extract first ~500 words as hook
    words = full_text.split()
    hook_text = " ".join(words[:500])

    return hook_text, os.path.abspath(transcript_path)


def main():
    parser = argparse.ArgumentParser(
        description="Search YouTube and download top thumbnail images for competitive analysis."
    )
    parser.add_argument("query", help="YouTube search query string")
    parser.add_argument("output_dir", help="Directory to save downloaded thumbnail images")
    parser.add_argument("--count", type=int, default=10, help="Number of thumbnails to keep after filtering (default: 10, max: 20)")
    parser.add_argument("--exclude-channel", help="YouTube channel ID to exclude (e.g., UCxxx)")
    parser.add_argument("--date-after", help="Only include videos uploaded after this date (YYYYMMDD)")
    parser.add_argument("--min-subscribers", type=int, default=None,
                        help="Exclude channels with fewer than this many subscribers")
    parser.add_argument("--sort-by", choices=["relevance", "views", "performance"], default="relevance",
                        help="Sort strategy: relevance (YouTube default), views (highest first), performance (views/subscribers)")
    parser.add_argument("--fetch-channel-stats", action="store_true",
                        help="Fetch channel average views for outlier score calculation")
    args = parser.parse_args()

    start = time.time()

    count = min(args.count, 20)
    # Request extra results to account for filtering
    has_filters = args.exclude_channel or args.date_after or args.min_subscribers
    search_count = count + 10 if has_filters else count
    search_count = min(search_count, 30)

    os.makedirs(args.output_dir, exist_ok=True)

    # Search YouTube
    try:
        videos = search_youtube(args.query, search_count)
    except FileNotFoundError:
        print(json.dumps({
            "status": "error",
            "error": "yt-dlp not found. Install with: brew install yt-dlp",
        }))
        sys.exit(1)
    except RuntimeError as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)

    if not videos:
        print(json.dumps({
            "status": "error",
            "error": f"No YouTube results found for query: {args.query}",
        }))
        sys.exit(1)

    # Filter
    videos, filtered_out = filter_videos(
        videos, args.exclude_channel, args.date_after, args.min_subscribers
    )

    if not videos:
        print(json.dumps({
            "status": "error",
            "error": f"All {filtered_out} results were filtered out (own channel or too old). Try a broader query.",
        }))
        sys.exit(1)

    # Sort
    videos = sort_videos(videos, args.sort_by)

    # Trim to requested count
    videos = videos[:count]

    # Enrich with computed fields
    videos = [enrich_video(v) for v in videos]

    # Download thumbnails
    thumbnails = []
    for i, vid in enumerate(videos):
        filename = f"thumb_{i:02d}_{vid['video_id']}.jpg"
        filepath = os.path.join(args.output_dir, filename)
        result_path = download_thumbnail(vid["video_id"], filepath)
        vid["index"] = i
        vid["thumbnail_url"] = f"https://img.youtube.com/vi/{vid['video_id']}/maxresdefault.jpg"
        vid["local_path"] = os.path.abspath(result_path) if result_path else None
        thumbnails.append(vid)

    # Fetch channel average views for outlier score calculation
    channels_fetched = 0
    if args.fetch_channel_stats:
        channel_cache: dict[str, int | None] = {}
        for vid in thumbnails:
            cid = vid.get("channel_id")
            if not cid:
                continue
            if cid not in channel_cache:
                channel_cache[cid] = fetch_channel_average_views(cid)
                channels_fetched += 1
                time.sleep(0.5)  # rate limit between channel fetches

            avg = channel_cache[cid]
            if avg is None:
                # Fallback: estimate from subscriber count
                subs = vid.get("channel_subscribers") or 0
                avg = max(int(subs * 0.02), 1)
            vid["channel_average_views"] = avg

            views = vid.get("view_count") or 0
            vid["outlier_score"] = round(views / max(avg, 1), 2)

        # Add recency multiplier and base score
        for vid in thumbnails:
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

    # Fetch transcripts for hook analysis
    transcripts_fetched = 0
    transcript_dir = os.path.join(args.output_dir, "transcripts")
    os.makedirs(transcript_dir, exist_ok=True)
    for vid in thumbnails:
        video_id = vid.get("video_id")
        if not video_id:
            vid["transcript_hook"] = None
            vid["transcript_path"] = None
            continue
        hook, path = fetch_video_transcript(video_id, transcript_dir)
        vid["transcript_hook"] = hook
        vid["transcript_path"] = path
        if hook:
            transcripts_fetched += 1

    # Save metadata
    metadata_path = os.path.join(args.output_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(thumbnails, f, indent=2)

    downloaded = sum(1 for t in thumbnails if t["local_path"] is not None)
    elapsed = round(time.time() - start, 2)

    result = {
        "status": "success",
        "query": args.query,
        "sort_by": args.sort_by,
        "thumbnails_downloaded": downloaded,
        "thumbnails_total": len(thumbnails),
        "filtered_out": filtered_out,
        "output_dir": os.path.abspath(args.output_dir),
        "metadata_file": os.path.abspath(metadata_path),
        "thumbnails": thumbnails,
        "elapsed_seconds": elapsed,
    }
    if args.fetch_channel_stats:
        result["channels_fetched"] = channels_fetched
    result["transcripts_fetched"] = transcripts_fetched

    print(json.dumps(result))


if __name__ == "__main__":
    main()
