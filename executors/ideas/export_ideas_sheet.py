#!/usr/bin/env python3
"""Export scored topic analysis results to a Google Sheet.

Uses a fixed "Topics" tab that is updated in place each run (no date-based tabs).
Shares a spreadsheet with the /analyze pipeline ("YouTube Content Intelligence").

Usage:
    python3 executors/ideas/export_ideas_sheet.py \
        --input workspace/temp/ideas/<PROJECT>/ideas_analysis.json \
        [--tab-name Topics] \
        [--credentials credentials.json] \
        [--sheet-config workspace/config/intelligence_sheet.json]

Depends on: google-api-python-client google-auth-httplib2 google-auth-oauthlib
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
    sheet_exists, create_spreadsheet, get_or_create_tab,
)

SPREADSHEET_TITLE = "YouTube Content Intelligence"


# ── Row building ───────────────────────────────────────────────────────────

def flatten_value(val) -> str:
    """Convert any value to a plain string for Sheets API.

    Handles nested dicts (e.g., {"longform": [...], "shorts": [...]})
    and lists by joining with newlines.
    """
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, (int, float)):
        return val  # Keep numeric types as-is for Sheets
    if isinstance(val, list):
        return "\n".join(str(item) for item in val)
    if isinstance(val, dict):
        parts = []
        for key, sub_val in val.items():
            if isinstance(sub_val, list):
                items = "\n".join(f"  - {item}" for item in sub_val)
                parts.append(f"[{key}]\n{items}")
            else:
                parts.append(f"[{key}] {sub_val}")
        return "\n".join(parts)
    return str(val)


def build_rows(topics: list[dict]) -> list[list]:
    """Build header + data rows for the 13-column topic analysis layout."""
    header = [
        "#",                    # 1  - Rank
        "Topic",                # 2
        "LF Score",             # 3  - Long-form score (0-10)
        "Shorts Score",         # 4  - Shorts score (0-10)
        "Format",               # 5  - Recommended format
        "Trend",                # 6  - Rising / Stable / Viral / Declining
        "Why It Works",         # 7
        "Suggested Angle",      # 8
        "Hook Ideas",           # 9
        "Sources",              # 10 - YT, Trends, Reddit, Social
        "Evidence",             # 11 - Top videos/posts
        "Research More",        # 12 - Where to dive deeper
        "Gap Status",           # 13 - Uncovered / Partially / Covered
    ]
    rows = [header]

    for i, topic in enumerate(topics, 1):
        row = [
            i,
            topic.get("topic", ""),
            topic.get("lf_score", ""),
            topic.get("shorts_score", ""),
            flatten_value(topic.get("format_rec", "")),
            flatten_value(topic.get("trend", "")),
            flatten_value(topic.get("why_it_works", "")),
            flatten_value(topic.get("suggested_angle", "")),
            flatten_value(topic.get("hook_ideas", "")),
            flatten_value(topic.get("sources", "")),
            flatten_value(topic.get("evidence", "")),
            flatten_value(topic.get("research_more", "")),
            flatten_value(topic.get("gap_status", "")),
        ]
        rows.append(row)

    return rows


def apply_formatting(service, spreadsheet_id: str, tab_id: int,
                     num_rows: int) -> None:
    """Apply formatting: frozen header, column widths, conditional formatting."""
    requests = [
        # Freeze header row
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
    ]

    # Column widths (13 columns):
    # Rank(50), Topic(250), LF Score(70), Shorts Score(80), Format(80),
    # Trend(80), Why It Works(300), Suggested Angle(250), Hook Ideas(300),
    # Sources(100), Evidence(350), Research More(250), Gap Status(100)
    col_widths = [50, 250, 70, 80, 80, 80, 300, 250, 300, 100, 350, 250, 100]
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

    # Bold header row with gray background
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

    # Text wrapping for long text columns (6-11: Why It Works through Research More)
    for col_idx in [6, 7, 8, 10, 11]:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": tab_id,
                    "startRowIndex": 1,
                    "endRowIndex": num_rows,
                    "startColumnIndex": col_idx,
                    "endColumnIndex": col_idx + 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "wrapStrategy": "WRAP",
                    }
                },
                "fields": "userEnteredFormat.wrapStrategy",
            }
        })

    # Conditional formatting: LF Score (col 2) and Shorts Score (col 3)
    # Green >= 7, Yellow 4-6, Red < 4
    for col_idx in [2, 3]:
        # Green for >= 7
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": tab_id,
                        "startRowIndex": 1,
                        "endRowIndex": num_rows,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1,
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "NUMBER_GREATER_THAN_EQ",
                            "values": [{"userEnteredValue": "7"}],
                        },
                        "format": {
                            "backgroundColor": {"red": 0.72, "green": 0.88, "blue": 0.72},
                        },
                    },
                },
                "index": 0,
            }
        })
        # Yellow for 4-6
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": tab_id,
                        "startRowIndex": 1,
                        "endRowIndex": num_rows,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1,
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "NUMBER_BETWEEN",
                            "values": [
                                {"userEnteredValue": "4"},
                                {"userEnteredValue": "6.99"},
                            ],
                        },
                        "format": {
                            "backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.6},
                        },
                    },
                },
                "index": 1,
            }
        })
        # Red for < 4
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": tab_id,
                        "startRowIndex": 1,
                        "endRowIndex": num_rows,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1,
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "NUMBER_LESS",
                            "values": [{"userEnteredValue": "4"}],
                        },
                        "format": {
                            "backgroundColor": {"red": 0.96, "green": 0.7, "blue": 0.7},
                        },
                    },
                },
                "index": 2,
            }
        })

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


def main():
    parser = argparse.ArgumentParser(
        description="Export topic analysis results to Google Sheets."
    )
    parser.add_argument("--input", required=True,
                        help="Path to ideas_analysis.json (scored idea list)")
    parser.add_argument("--tab-name", default="Topics",
                        help="Tab/sheet name (default: Topics)")
    parser.add_argument("--credentials",
                        default=os.path.join(os.getcwd(), "credentials.json"),
                        help="Path to OAuth credentials.json (default: ./credentials.json)")
    parser.add_argument("--sheet-config",
                        default=os.path.join(
                            os.getcwd(), "workspace", "config", "intelligence_sheet.json"
                        ),
                        help="Path to store/read spreadsheet ID for reuse")
    args = parser.parse_args()

    check_dependencies()

    # Load topic analysis data
    if not os.path.isfile(args.input):
        fail(f"Input file not found: {args.input}")

    with open(args.input) as f:
        topics = json.load(f)

    if not isinstance(topics, list) or len(topics) == 0:
        fail("Input JSON must be a non-empty array of topic objects.")

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

    # Get or create tab (clears existing data if tab exists)
    tab_id = get_or_create_tab(service, spreadsheet_id, args.tab_name)

    # Build and write rows
    rows = build_rows(topics)

    range_name = f"'{args.tab_name}'!A1"
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    # Write "Last Updated" after the last header column
    from datetime import datetime
    updated = datetime.now().strftime("%Y-%m-%d %H:%M")
    num_cols = len(rows[0]) if rows else 0
    if num_cols < 26:
        col_letter = chr(ord("A") + num_cols)
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{args.tab_name}'!{col_letter}1",
            valueInputOption="USER_ENTERED",
            body={"values": [[f"Updated: {updated}"]]},
        ).execute()

    # Apply formatting
    apply_formatting(service, spreadsheet_id, tab_id, len(rows))

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
