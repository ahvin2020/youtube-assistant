#!/usr/bin/env python3
"""One-off: Generate a Google Sheet showing 1 thumbnail per curated channel.

Usage:
    python3 executors/thumbnail/preview_channels_sheet.py \
        [--thumbnail-channels memory/thumbnail-channels.md] \
        [--credentials credentials.json] \
        [--sheet-config workspace/config/research_sheet.json]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys

_EXECUTORS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EXECUTORS_DIR not in sys.path:
    sys.path.insert(0, _EXECUTORS_DIR)

from shared.parse_profile import parse_thumbnail_channels
from shared.youtube import fetch_channel_recent_videos, search_youtube
from shared.google_sheets import (
    fail, check_dependencies, authenticate,
    load_sheet_config, save_sheet_config,
    sheet_exists, create_spreadsheet, add_tab,
    get_tab_id, clear_tab,
)

SPREADSHEET_TITLE = "YouTube Thumbnail Research"
TAB_NAME = "channel_preview"


def fetch_one_video(channel_id: str, channel_name: str) -> dict | None:
    """Try flat-playlist first, fall back to ytsearch."""
    videos = fetch_channel_recent_videos(channel_id, channel_name, max_videos=1)
    if videos:
        v = videos[0]
        return {
            "channel_name": channel_name,
            "channel_id": channel_id,
            "video_id": v.get("video_id", ""),
            "title": v.get("title", ""),
            "view_count": v.get("view_count", 0),
        }

    # Fallback: search by channel name
    try:
        results = search_youtube(f"{channel_name} latest", 1)
        if results:
            v = results[0]
            return {
                "channel_name": channel_name,
                "channel_id": channel_id,
                "video_id": v.get("video_id", ""),
                "title": v.get("title", ""),
                "view_count": v.get("view_count", 0),
            }
    except Exception:
        pass

    return None


def main():
    parser = argparse.ArgumentParser(description="Preview curated channel thumbnails")
    parser.add_argument("--thumbnail-channels",
                        default=os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "memory", "thumbnail-channels.md"
                        ))
    parser.add_argument("--credentials",
                        default=os.path.join(os.getcwd(), "credentials.json"))
    parser.add_argument("--sheet-config",
                        default=os.path.join(
                            os.getcwd(), "workspace", "config", "research_sheet.json"
                        ))
    args = parser.parse_args()

    check_dependencies()

    # Load channels
    channels = parse_thumbnail_channels(args.thumbnail_channels)
    print(f"Loaded {len(channels)} channels", file=sys.stderr)

    # Fetch 1 recent video per channel (parallel, with search fallback)
    results: list[dict] = []
    failed: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {}
        for cid, cname in channels.items():
            future = pool.submit(fetch_one_video, cid, cname)
            futures[future] = (cid, cname)

        for future in concurrent.futures.as_completed(futures):
            cid, cname = futures[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
                else:
                    failed.append(cname)
                    print(f"  Failed: {cname}", file=sys.stderr)
            except Exception as e:
                failed.append(cname)
                print(f"  Error {cname}: {e}", file=sys.stderr)

    print(f"Fetched {len(results)} channels, {len(failed)} failed", file=sys.stderr)
    if failed:
        print(f"  Failed channels: {', '.join(failed)}", file=sys.stderr)

    # Sort by channel name
    results.sort(key=lambda x: x["channel_name"].lower())

    # Build rows — use IMAGE() formula for thumbnail display
    header = ["Thumbnail", "Thumbnail URL", "Channel Name", "Video Title",
              "Views", "Video Link", "Channel Link"]
    rows = [header]
    for r in results:
        vid = r["video_id"]
        thumb_url = f"https://img.youtube.com/vi/{vid}/mqdefault.jpg"
        rows.append([
            f'=IMAGE("{thumb_url}")',
            thumb_url,
            r["channel_name"],
            r["title"],
            r["view_count"],
            f"https://youtube.com/watch?v={vid}",
            f"https://youtube.com/channel/{r['channel_id']}",
        ])

    # Authenticate and write to sheet
    creds = authenticate(args.credentials)
    from googleapiclient.discovery import build
    service = build("sheets", "v4", credentials=creds)

    config = load_sheet_config(args.sheet_config)
    spreadsheet_id = None
    if config and config.get("sheet_id"):
        if sheet_exists(service, config["sheet_id"]):
            spreadsheet_id = config["sheet_id"]

    if not spreadsheet_id:
        spreadsheet_id, sheet_url = create_spreadsheet(service, SPREADSHEET_TITLE)
        save_sheet_config(args.sheet_config, spreadsheet_id, sheet_url)

    # Reuse or create tab
    tab_id = get_tab_id(service, spreadsheet_id, TAB_NAME)
    if tab_id is not None:
        clear_tab(service, spreadsheet_id, tab_id, TAB_NAME)
    else:
        tab_id = add_tab(service, spreadsheet_id, TAB_NAME)

    # Write data
    range_name = f"'{TAB_NAME}'!A1"
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    # Formatting
    requests = [
        # Freeze header
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": tab_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        # Row heights for thumbnails (120px for better visibility)
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": tab_id,
                    "dimension": "ROWS",
                    "startIndex": 1,
                    "endIndex": len(rows),
                },
                "properties": {"pixelSize": 120},
                "fields": "pixelSize",
            }
        },
        # Bold header
        {
            "repeatCell": {
                "range": {
                    "sheetId": tab_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "backgroundColor": {"red": 0.93, "green": 0.93, "blue": 0.93},
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor)",
            }
        },
    ]

    # Column widths: Thumbnail(220), ThumbURL(200), Channel(180), Title(350),
    #                Views(90), VideoLink(280), ChannelLink(280)
    col_widths = [220, 200, 180, 350, 90, 280, 280]
    for idx, width in enumerate(col_widths):
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": tab_id,
                    "dimension": "COLUMNS",
                    "startIndex": idx,
                    "endIndex": idx + 1,
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        })

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()

    sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit#gid={tab_id}"
    print(json.dumps({
        "status": "success",
        "sheet_url": sheet_url,
        "channels": len(results),
        "errors": len(failed),
    }))


if __name__ == "__main__":
    main()
