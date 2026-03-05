#!/usr/bin/env python3
"""Fetch own-channel and competitor video data for content analysis.

Two modes:
  Full: Fetch own-channel (50 videos) + competitors (20 per channel, up to 15 channels)
  Deep-dive: Fetch one specific video + search for competitors on the same topic

Usage:
    # Full analysis
    python3 executors/analyze/fetch_channel_data.py \
        --channel-profile memory/channel-profile.md \
        --channel-id UCxxx \
        [--own-count 50] [--competitor-count 20] \
        [--max-channels 15] [--days 180] \
        --output workspace/temp/analyze/<PROJECT>/channel_data.json

    # Deep-dive (specific video)
    python3 executors/analyze/fetch_channel_data.py \
        --channel-profile memory/channel-profile.md \
        --channel-id UCxxx \
        --video-url "https://www.youtube.com/watch?v=abc123" \
        [--competitor-count 20] \
        --output workspace/temp/analyze/<PROJECT>/channel_data.json

Depends on: yt-dlp (brew install yt-dlp)
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import sys
import time
from collections import defaultdict
from datetime import date, datetime

_EXECUTORS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EXECUTORS_DIR not in sys.path:
    sys.path.insert(0, _EXECUTORS_DIR)
from shared.youtube import search_youtube, fetch_channel_recent_videos, enrich_video, batch_enrich_metadata
from shared.parse_profile import parse_channel_profile


def compute_outlier_scores(videos: list[dict]) -> list[dict]:
    """Compute outlier_score and engagement_rate for a list of videos."""
    # Group views by channel to compute averages
    channel_views: dict[str, list[int]] = defaultdict(list)
    for vid in videos:
        cid = vid.get("channel_id")
        vc = vid.get("view_count")
        if cid and vc is not None and vc > 0:
            channel_views[cid].append(vc)

    channel_avg: dict[str, int] = {}
    for cid, views_list in channel_views.items():
        channel_avg[cid] = int(sum(views_list) / len(views_list))

    for vid in videos:
        cid = vid.get("channel_id")
        avg = channel_avg.get(cid) if cid else None
        if avg is None:
            subs = vid.get("channel_subscribers") or 0
            avg = max(int(subs * 0.02), 1)
        vid["channel_average_views"] = avg

        views = vid.get("view_count") or 0
        vid["outlier_score"] = round(views / max(avg, 1), 2)

        likes = vid.get("like_count") or 0
        comments = vid.get("comment_count") or 0
        vid["engagement_rate"] = round((likes + comments) / max(views, 1), 4)

    return videos


def filter_by_days(videos: list[dict], days: int) -> list[dict]:
    """Filter videos to lookback period. Keep videos with unknown upload date."""
    return [
        v for v in videos
        if v.get("days_since_upload") is None or v["days_since_upload"] <= days
    ]


def compute_monthly_trends(videos: list[dict]) -> list[dict]:
    """Group own-channel videos by month and compute trends."""
    monthly: dict[str, list[int]] = defaultdict(list)
    for vid in videos:
        upload = vid.get("upload_date")
        if upload:
            try:
                month = f"{upload[:4]}-{upload[4:6]}"
                views = vid.get("view_count") or 0
                monthly[month].append(views)
            except (IndexError, ValueError):
                pass

    trends = []
    for month in sorted(monthly.keys()):
        views_list = monthly[month]
        trends.append({
            "month": month,
            "avg_views": int(sum(views_list) / len(views_list)),
            "video_count": len(views_list),
        })
    return trends


def main():
    parser = argparse.ArgumentParser(
        description="Fetch channel data for content analysis."
    )
    parser.add_argument("--channel-profile", required=True,
                        help="Path to channel-profile.md")
    parser.add_argument("--channel-id", required=True,
                        help="Own YouTube channel ID")
    parser.add_argument("--video-url", default=None,
                        help="Specific video URL for deep-dive mode")
    parser.add_argument("--own-count", type=int, default=50,
                        help="Number of own-channel videos to fetch (default: 50)")
    parser.add_argument("--competitor-count", type=int, default=20,
                        help="Videos per competitor channel (default: 20)")
    parser.add_argument("--max-channels", type=int, default=15,
                        help="Max competitor channels to scan (default: 15)")
    parser.add_argument("--days", type=int, default=180,
                        help="Lookback period in days (default: 180)")
    parser.add_argument("--output", default=None,
                        help="Output JSON file path")
    args = parser.parse_args()

    start = time.time()

    # Load config
    if not os.path.isfile(args.channel_profile):
        print(json.dumps({"status": "error", "error": f"channel-profile.md not found: {args.channel_profile}"}))
        sys.exit(1)

    profile = parse_channel_profile(args.channel_profile)
    own_categories = profile.get("own_niche_categories", [])
    adjacent_categories = profile.get("adjacent_niche_categories", [])
    all_categories = own_categories + adjacent_categories
    monitored_raw = profile.get("monitored_channels", {})

    # Flatten monitored channels
    competitor_channels: dict[str, str] = {}
    for category, channels in monitored_raw.items():
        if category in all_categories and isinstance(channels, dict):
            competitor_channels.update(channels)

    errors: list[str] = []
    is_deep_dive = args.video_url is not None

    # -----------------------------------------------------------------------
    # Deep-dive mode: fetch target video + search for topic competitors
    # -----------------------------------------------------------------------
    if is_deep_dive:
        target_videos: list[dict] = []
        competitor_videos: list[dict] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            # Fetch target video metadata via search
            target_future = pool.submit(search_youtube, args.video_url, 1)

            # Wait for target to get title for competitor search
            try:
                target_videos = target_future.result()
            except Exception as e:
                errors.append(f"target_video: {e}")

            if target_videos:
                target = target_videos[0]
                # Search for competitors on the same topic using title keywords
                title_words = target.get("title", "").split()
                # Take first 5 meaningful words as search query
                search_query = " ".join(w for w in title_words[:8] if len(w) > 2)[:60]
                try:
                    competitor_videos = search_youtube(search_query, args.competitor_count)
                except Exception as e:
                    errors.append(f"competitor_search: {e}")

        # Enrich all videos
        all_vids = target_videos + competitor_videos
        all_vids = [enrich_video(v) for v in all_vids]

        # Mark target
        for v in all_vids:
            v["is_own_channel"] = (v.get("channel_id") == args.channel_id)
            v["is_target"] = (v.get("video_id") == target_videos[0].get("video_id")) if target_videos else False

        # Dedup
        seen: set[str] = set()
        deduped: list[dict] = []
        for v in all_vids:
            vid_id = v.get("video_id")
            if vid_id and vid_id not in seen:
                seen.add(vid_id)
                deduped.append(v)

        # Compute scores
        deduped = compute_outlier_scores(deduped)
        deduped.sort(key=lambda v: v.get("outlier_score", 0), reverse=True)

        elapsed = round(time.time() - start, 2)
        result = {
            "status": "success",
            "mode": "deep-dive",
            "target_video": target_videos[0] if target_videos else None,
            "all_videos_sorted": deduped,
            "total_videos": len(deduped),
            "elapsed_seconds": elapsed,
            "errors": errors,
        }

    # -----------------------------------------------------------------------
    # Full mode: own channel + all competitors
    # -----------------------------------------------------------------------
    else:
        # Sample channels
        channel_items = list(competitor_channels.items())
        sampled = random.sample(channel_items, min(args.max_channels, len(channel_items)))

        own_videos: list[dict] = []
        competitor_videos: list[dict] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            # Own channel
            own_future = pool.submit(
                fetch_channel_recent_videos, args.channel_id, "own_channel", args.own_count
            )

            # Competitor channels
            comp_futures = {}
            for ch_id, ch_name in sampled:
                future = pool.submit(fetch_channel_recent_videos, ch_id, ch_name, args.competitor_count)
                comp_futures[future] = (ch_id, ch_name)

            # Collect own channel
            try:
                own_videos = own_future.result()
            except Exception as e:
                errors.append(f"own_channel: {e}")

            # Collect competitors
            for future in concurrent.futures.as_completed(comp_futures):
                ch_id, ch_name = comp_futures[future]
                try:
                    vids = future.result()
                    for v in vids:
                        v["_source"] = "competitor"
                    competitor_videos.extend(vids)
                except Exception as e:
                    errors.append(f"channel '{ch_name}': {e}")

        # Fetch full metadata (upload_date, likes, comments) for all videos
        # flat-playlist doesn't return these fields
        import sys as _sys
        print("Fetching full metadata for own-channel videos...", file=_sys.stderr)
        own_videos = batch_enrich_metadata(own_videos, max_workers=10)
        print("Fetching full metadata for competitor videos...", file=_sys.stderr)
        competitor_videos = batch_enrich_metadata(competitor_videos, max_workers=10)

        # Enrich all videos (compute derived fields)
        own_videos = [enrich_video(v) for v in own_videos]
        competitor_videos = [enrich_video(v) for v in competitor_videos]

        # Filter to lookback period
        own_videos = filter_by_days(own_videos, args.days)
        competitor_videos = filter_by_days(competitor_videos, args.days)

        # Exclude own channel from competitors
        competitor_videos = [
            v for v in competitor_videos
            if v.get("channel_id") != args.channel_id
        ]

        # Dedup competitors
        seen: set[str] = set()
        unique_competitors: list[dict] = []
        for vid in competitor_videos:
            vid_id = vid.get("video_id")
            if vid_id and vid_id not in seen:
                seen.add(vid_id)
                unique_competitors.append(vid)

        # Mark own-channel
        for v in own_videos:
            v["is_own_channel"] = True
        for v in unique_competitors:
            v["is_own_channel"] = False

        # Compute outlier scores for own channel
        own_views = [v.get("view_count", 0) for v in own_videos if v.get("view_count")]
        own_avg = int(sum(own_views) / len(own_views)) if own_views else 0
        for v in own_videos:
            v["channel_average_views"] = own_avg
            views = v.get("view_count") or 0
            v["outlier_score"] = round(views / max(own_avg, 1), 2)
            likes = v.get("like_count") or 0
            comments = v.get("comment_count") or 0
            v["engagement_rate"] = round((likes + comments) / max(views, 1), 4)

        # Compute outlier scores for competitors
        unique_competitors = compute_outlier_scores(unique_competitors)

        # Merge and sort
        all_videos = own_videos + unique_competitors
        all_videos.sort(key=lambda v: v.get("outlier_score", 0), reverse=True)

        # Monthly trends for own channel
        monthly_trends = compute_monthly_trends(own_videos)

        elapsed = round(time.time() - start, 2)
        mins, secs = divmod(int(elapsed), 60)

        result = {
            "status": "success",
            "mode": "full",
            "own_channel": {
                "channel_id": args.channel_id,
                "videos": own_videos,
                "average_views": own_avg,
                "total_videos": len(own_videos),
                "monthly_trends": monthly_trends,
            },
            "competitors": {
                ch_id: {
                    "channel_name": ch_name,
                    "videos": [v for v in unique_competitors if v.get("channel_id") == ch_id],
                }
                for ch_id, ch_name in sampled
            },
            "all_videos_sorted": all_videos,
            "total_videos": len(all_videos),
            "channels_scanned": len(sampled),
            "lookback_days": args.days,
            "elapsed_seconds": elapsed,
            "elapsed_formatted": f"{mins}m {secs:02d}s" if mins else f"{secs}s",
            "errors": errors,
        }

    # Write output
    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
