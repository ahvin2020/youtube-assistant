"""Shared YouTube data-fetching utilities.

Used by executors/thumbnail/ and executors/topics/ for YouTube search,
channel video fetching, and video metadata enrichment.

Depends on: yt-dlp (brew install yt-dlp)
"""

from __future__ import annotations

import json
import subprocess
from datetime import date, datetime


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


def fetch_channel_recent_videos(channel_id: str, channel_name: str,
                                max_videos: int = 10) -> list[dict]:
    """Fetch recent videos from a channel using yt-dlp flat-playlist.

    Returns video dicts in the same format as search_youtube().
    Caller is responsible for adding source-tracking metadata
    (e.g. _source, _source_channel) to the returned dicts if needed.
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
        }
        videos.append(vid)
    return videos


def fetch_video_metadata(video_id: str) -> dict | None:
    """Fetch full metadata for a single video (upload_date, like_count, etc).

    Returns a dict with the enriched fields, or None on failure.
    This is slower than flat-playlist but returns complete data.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = [
        "yt-dlp", url,
        "--dump-json", "--no-download", "--skip-download",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return None

    if result.returncode != 0:
        return None

    try:
        data = json.loads(result.stdout.strip().split("\n")[0])
    except (json.JSONDecodeError, IndexError):
        return None

    return {
        "upload_date": data.get("upload_date"),
        "like_count": data.get("like_count"),
        "comment_count": data.get("comment_count"),
        "channel_subscribers": data.get("channel_follower_count"),
    }


def batch_enrich_metadata(videos: list[dict], max_workers: int = 10) -> list[dict]:
    """Fetch full metadata for videos missing upload_date, in parallel.

    Only fetches for videos where upload_date is None. Merges results
    back into the video dicts (non-None fields overwrite).
    """
    import concurrent.futures

    to_enrich = [(i, v) for i, v in enumerate(videos) if v.get("upload_date") is None]
    if not to_enrich:
        return videos

    def _fetch(idx_vid):
        idx, vid = idx_vid
        vid_id = vid.get("video_id")
        if not vid_id:
            return idx, None
        return idx, fetch_video_metadata(vid_id)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for idx, result in pool.map(_fetch, to_enrich):
            if result:
                for key, val in result.items():
                    if val is not None:
                        videos[idx][key] = val

    return videos


def enrich_video(vid: dict) -> dict:
    """Add computed fields to a video entry.

    Adds: views_per_subscriber, like_view_ratio, duration_category,
    days_since_upload.

    Note: Uses thumbnail/research duration thresholds (short < 300s).
    For Shorts-aware classification (short < 60s + is_short flag),
    see the inline version in executors/topics/youtube_topics.py.
    """
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
