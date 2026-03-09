#!/usr/bin/env python3
"""
Google Sheets Exporter for Thumbnail Research
==============================================
Exports scored cross-niche research results to a Google Sheet.
Each run creates a new tab so the same spreadsheet is reused across sessions.

Usage:
    python3 executors/thumbnail/export_research_sheet.py \
        --input workspace/temp/thumbnail/<PROJECT>/research/cross_niche/metadata.json \
        --tab-name 20260304_cpf-ers-vs-investing \
        [--credentials credentials.json] \
        [--sheet-config workspace/config/research_sheet.json]

    python3 executors/thumbnail/export_research_sheet.py --help

Arguments:
    --input PATH          Path to metadata.json (scored research results)
    --tab-name NAME       Tab/sheet name (e.g. YYYYMMDD_slug)

Options:
    --credentials PATH    Path to OAuth credentials.json (default: ./credentials.json)
    --sheet-config PATH   Path to store/read spreadsheet ID for reuse
                          (default: ./workspace/config/research_sheet.json)

Installation:
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

Output JSON (stdout):
    {"status": "success", "sheet_id": "...", "sheet_url": "...", "tab_name": "...", "rows_written": N}

Notes:
    - First run opens a browser for OAuth consent (token is cached afterward)
    - Token cached at ~/.cache/youtube-assistant/google_sheets_token.json
    - Scopes: spreadsheets (read/write spreadsheets this app creates or is given)
    - Requires Google Sheets API enabled in the GCP project
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_EXECUTORS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EXECUTORS_DIR not in sys.path:
    sys.path.insert(0, _EXECUTORS_DIR)
from shared.google_sheets import (
    fail, check_dependencies, authenticate,
    load_sheet_config, save_sheet_config,
    sheet_exists, create_spreadsheet, add_tab,
    get_tab_id, clear_tab,
)

SPREADSHEET_TITLE = "YouTube Thumbnail Research"


# ── Category classification ────────────────────────────────────────────────

CATEGORY_RULES = [
    ("Money", [
        "money", "revenue", "income", "profit", "$", "million", "millionaire",
        "cash", "earn", "wealthy", "wealth", "net worth", "salary", "pricing",
    ]),
    ("Productivity", [
        "productivity", "time", "efficient", "faster", "save time", "productive",
        "hack", "routine", "habits", "morning", "systems",
    ]),
    ("Creator", [
        "youtube", "content", "creator", "channel", "subscriber", "video",
        "views", "thumbnail", "algorithm",
    ]),
    ("Business", [
        "business", "startup", "founder", "entrepreneur", "company", "scale",
        "grow", "customers", "marketing", "sales",
    ]),
]


def categorize(title: str) -> str:
    """Classify video into a content category based on title keywords."""
    title_lower = title.lower()
    for category, terms in CATEGORY_RULES:
        if any(term in title_lower for term in terms):
            return category
    return "General"


# ── Row building ───────────────────────────────────────────────────────────

def build_rows(videos: list[dict]) -> list[list]:
    """Build header + data rows for the spreadsheet layout."""
    header = [
        "Thumbnail",                # 1
        "Thumbnail URL",            # 2
        "Title",                    # 3
        "Final Score",              # 4
        "Outlier Score",            # 5
        "Days Old",                 # 6
        "Video Link",               # 7
        "View Count",               # 8
        "Duration (min)",           # 9
        "Channel Name",             # 10
        "Channel Avg Views",        # 11
        "Category",                 # 12
        "Publish Date",             # 13
        "Source",                   # 14
    ]
    rows = [header]

    for vid in videos:
        video_id = vid.get("video_id", "")
        thumb_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
        video_url = f"https://youtube.com/watch?v={video_id}"

        # Duration in minutes
        duration_sec = vid.get("duration") or 0
        duration_min = round(duration_sec / 60, 1)

        # Source detail
        source = vid.get("_source", "")
        if source == "curated":
            source_detail = "channel: {}".format(vid.get("_source_channel", vid.get("channel", "")))
        elif source == "keyword":
            source_detail = "keyword: {}".format(vid.get("_search_keyword", ""))
        elif source == "channel":
            source_detail = "channel: {}".format(vid.get("_source_channel", vid.get("channel", "")))
        else:
            source_detail = source

        category = categorize(vid.get("title", ""))

        row = [
            '=IMAGE("{}")'.format(thumb_url),
            thumb_url,
            vid.get("title", ""),
            vid.get("final_score", ""),
            vid.get("outlier_score", ""),
            vid.get("days_since_upload", ""),
            video_url,
            vid.get("view_count", ""),
            duration_min,
            vid.get("channel", ""),
            vid.get("channel_average_views", ""),
            category,
            vid.get("upload_date", ""),
            source_detail,
        ]
        rows.append(row)

    return rows


def apply_formatting(service, spreadsheet_id: str, tab_id: int,
                     num_rows: int) -> None:
    """Apply formatting: frozen header, row heights for thumbnails, column widths."""
    requests = [
        # Freeze header row + first 2 columns (Thumbnail, Thumbnail URL)
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": tab_id,
                    "gridProperties": {
                        "frozenRowCount": 1,
                        "frozenColumnCount": 2,
                    },
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }
        },
        # Set row height for data rows (thumbnails need ~90px)
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": tab_id,
                    "dimension": "ROWS",
                    "startIndex": 1,
                    "endIndex": num_rows,
                },
                "properties": {"pixelSize": 90},
                "fields": "pixelSize",
            }
        },
        # Column widths (14 columns):
        # Thumbnail (180), Thumbnail URL (200), Title (350),
        # Final Score (90), Outlier Score (80), Days Old (70),
        # Video Link (280), View Count (90), Duration (70),
        # Channel Name (150), Channel Avg Views (100), Category (100),
        # Publish Date (100), Source (200)
    ]

    col_widths = [
        180, 200, 350, 90, 80, 70, 280, 90, 70,
        150, 100, 100, 100, 200,
    ]
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

    # Bold header row
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId": tab_id,
                "startRowIndex": 0,
                "endRowIndex": 1,
            },
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {"bold": True},
                    "backgroundColor": {
                        "red": 0.93, "green": 0.93, "blue": 0.93,
                    },
                }
            },
            "fields": "userEnteredFormat(textFormat,backgroundColor)",
        }
    })

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


def main():
    parser = argparse.ArgumentParser(
        description="Export thumbnail research results to Google Sheets."
    )
    parser.add_argument("--input", required=True,
                        help="Path to metadata.json (scored research results)")
    parser.add_argument("--tab-name", required=True,
                        help="Tab/sheet name (e.g. 20260304_cpf-ers-vs-investing)")
    parser.add_argument("--credentials",
                        default=os.path.join(os.getcwd(), "credentials.json"),
                        help="Path to OAuth credentials.json (default: ./credentials.json)")
    parser.add_argument("--sheet-config",
                        default=os.path.join(
                            os.getcwd(), "workspace", "config", "research_sheet.json"
                        ),
                        help="Path to store/read spreadsheet ID for reuse")
    args = parser.parse_args()

    check_dependencies()

    # Load scored research data
    if not os.path.isfile(args.input):
        fail(f"Input file not found: {args.input}")

    with open(args.input) as f:
        videos = json.load(f)

    if not isinstance(videos, list) or len(videos) == 0:
        fail("Input JSON must be a non-empty array of video objects.")

    # Authenticate
    creds = authenticate(args.credentials)

    from googleapiclient.discovery import build
    service = build("sheets", "v4", credentials=creds)

    # Get or create spreadsheet
    config = load_sheet_config(args.sheet_config)
    spreadsheet_id = None

    if config and config.get("sheet_id"):
        if sheet_exists(service, config["sheet_id"]):
            spreadsheet_id = config["sheet_id"]

    if not spreadsheet_id:
        spreadsheet_id, sheet_url = create_spreadsheet(service, SPREADSHEET_TITLE)
        save_sheet_config(args.sheet_config, spreadsheet_id, sheet_url)

    # Reuse existing tab or create new one
    tab_id = get_tab_id(service, spreadsheet_id, args.tab_name)
    reused = tab_id is not None
    if reused:
        clear_tab(service, spreadsheet_id, tab_id, args.tab_name)
    else:
        tab_id = add_tab(service, spreadsheet_id, args.tab_name)

    # Build and write rows
    rows = build_rows(videos)

    range_name = f"'{args.tab_name}'!A1"
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    # Apply formatting
    apply_formatting(service, spreadsheet_id, tab_id, len(rows))

    # Add "Last updated" note in the cell below the data
    from datetime import datetime
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    note_range = f"'{args.tab_name}'!A{len(rows) + 2}"
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=note_range,
        valueInputOption="USER_ENTERED",
        body={"values": [[f"Last updated: {updated_at}"]]},
    ).execute()

    # Build result
    sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit#gid={tab_id}"

    print(json.dumps({
        "status": "success",
        "sheet_id": spreadsheet_id,
        "sheet_url": sheet_url,
        "tab_name": args.tab_name,
        "rows_written": len(rows) - 1,
    }))


if __name__ == "__main__":
    main()
