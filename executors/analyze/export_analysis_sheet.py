#!/usr/bin/env python3
"""Export content analysis results to a Google Sheet with 4 tabs.

Tabs:
  1. Performance Overview — ranked video list with metrics
  2. Hook Library — all hooks from hooks.json with scores/categories
  3. Pattern Insights — patterns, evidence, actionable recommendations
  4. Content Gaps — competitor-covered topics missing from own channel

Each run creates or updates 4 tabs prefixed with the project name.
If tabs already exist for the same project, they are cleared and rewritten.
The same spreadsheet is reused across sessions.

Usage:
    python3 executors/analyze/export_analysis_sheet.py \
        --performance workspace/temp/analyze/<PROJECT>/performance_overview.json \
        --hooks workspace/config/hooks.json \
        --patterns workspace/temp/analyze/<PROJECT>/pattern_insights.json \
        --gaps workspace/temp/analyze/<PROJECT>/content_gaps.json \
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


# ── Row builders ──────────────────────────────────────────────────────────

def build_performance_rows(data: list[dict]) -> list[list]:
    """Build rows for Performance Overview tab."""
    header = [
        "#", "Title", "Channel", "Own?", "Views", "Outlier",
        "Engagement", "Like/View", "Duration", "Upload Date", "Days Old",
    ]
    rows = [header]
    for i, v in enumerate(data, 1):
        rows.append([
            i,
            v.get("title", ""),
            v.get("channel", ""),
            "Yes" if v.get("is_own_channel") else "",
            v.get("views", v.get("view_count", "")),
            v.get("outlier_score", ""),
            v.get("engagement_rate", ""),
            v.get("like_view_ratio", ""),
            v.get("duration", ""),
            v.get("upload_date", ""),
            v.get("days_since_upload", ""),
        ])
    return rows


def build_hooks_rows(data: dict) -> list[list]:
    """Build rows for Hook Library tab from hooks.json."""
    header = [
        "#", "Hook Text", "Category", "Format", "Source Video",
        "Source Channel", "Views", "Outlier", "Score", "Times Seen",
        "Date Added",
    ]
    rows = [header]
    hooks = data.get("hooks", []) if isinstance(data, dict) else data
    for i, h in enumerate(hooks, 1):
        rows.append([
            i,
            h.get("text", ""),
            h.get("category", ""),
            h.get("format", ""),
            h.get("source_video_id", ""),
            h.get("source_channel", ""),
            h.get("views", ""),
            h.get("outlier_score", ""),
            h.get("performance_score", ""),
            h.get("times_seen", 1),
            h.get("date_added", ""),
        ])
    return rows


def build_patterns_rows(data: list[dict]) -> list[list]:
    """Build rows for Pattern Insights tab."""
    header = ["#", "Pattern", "Category", "Evidence", "Strength", "Actionable Insight"]
    rows = [header]
    for i, p in enumerate(data, 1):
        rows.append([
            i,
            p.get("pattern", ""),
            p.get("category", ""),
            p.get("evidence", ""),
            p.get("strength", ""),
            p.get("actionable_insight", ""),
        ])
    return rows


def build_gaps_rows(data: list[dict]) -> list[list]:
    """Build rows for Content Gaps tab."""
    header = [
        "#", "Topic", "Competitor Coverage", "Own Coverage",
        "Gap Type", "Opportunity Score", "Suggested Angle",
    ]
    rows = [header]
    for i, g in enumerate(data, 1):
        rows.append([
            i,
            g.get("topic", ""),
            g.get("competitor_coverage", ""),
            g.get("own_coverage", ""),
            g.get("gap_type", ""),
            g.get("opportunity_score", ""),
            g.get("suggested_angle", ""),
        ])
    return rows


# ── Formatting ────────────────────────────────────────────────────────────

def apply_tab_formatting(service, spreadsheet_id: str, tab_id: int,
                         num_rows: int, col_widths: list[int],
                         wrap_cols: list[int] | None = None,
                         score_cols: list[int] | None = None) -> None:
    """Apply standard formatting to a tab: frozen header, column widths, wrapping."""
    requests = [
        # Freeze header row
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": tab_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
    ]

    # Column widths
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

    # Bold header with gray background
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
                    "backgroundColor": {"red": 0.93, "green": 0.93, "blue": 0.93},
                }
            },
            "fields": "userEnteredFormat(textFormat,backgroundColor)",
        }
    })

    # Text wrapping for specified columns
    if wrap_cols:
        for col_idx in wrap_cols:
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
                        "userEnteredFormat": {"wrapStrategy": "WRAP"}
                    },
                    "fields": "userEnteredFormat.wrapStrategy",
                }
            })

    # Conditional formatting for score columns (green >= 7, yellow 4-6, red < 4)
    if score_cols:
        for col_idx in score_cols:
            for threshold, color, condition_type, values, index in [
                (7, {"red": 0.72, "green": 0.88, "blue": 0.72}, "NUMBER_GREATER_THAN_EQ", ["7"], 0),
                (4, {"red": 1.0, "green": 0.95, "blue": 0.6}, "NUMBER_BETWEEN", ["4", "6.99"], 1),
                (0, {"red": 0.96, "green": 0.7, "blue": 0.7}, "NUMBER_LESS", ["4"], 2),
            ]:
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
                                    "type": condition_type,
                                    "values": [{"userEnteredValue": v} for v in values],
                                },
                                "format": {"backgroundColor": color},
                            },
                        },
                        "index": index,
                    }
                })

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


def write_tab(service, spreadsheet_id: str, tab_name: str,
              rows: list[list], col_widths: list[int],
              wrap_cols: list[int] | None = None,
              score_cols: list[int] | None = None,
              last_updated: str | None = None) -> int:
    """Create or update a tab, write data, and apply formatting. Returns tab ID."""
    tab_id = get_or_create_tab(service, spreadsheet_id, tab_name)

    range_name = f"'{tab_name}'!A1"
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    # Write "Last Updated" in the cell right after the last header column
    if last_updated:
        num_cols = len(rows[0]) if rows else 0
        col_letter = chr(ord("A") + num_cols) if num_cols < 26 else "Z"
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{tab_name}'!{col_letter}1",
            valueInputOption="USER_ENTERED",
            body={"values": [[f"Updated: {last_updated}"]]},
        ).execute()

    apply_tab_formatting(
        service, spreadsheet_id, tab_id, len(rows),
        col_widths, wrap_cols, score_cols,
    )
    return tab_id


def main():
    parser = argparse.ArgumentParser(
        description="Export content analysis results to Google Sheets."
    )
    parser.add_argument("--performance", required=True,
                        help="Path to performance_overview.json")
    parser.add_argument("--hooks", required=True,
                        help="Path to hooks.json")
    parser.add_argument("--patterns", required=True,
                        help="Path to pattern_insights.json")
    parser.add_argument("--gaps", required=True,
                        help="Path to content_gaps.json")
    parser.add_argument("--tab-name",
                        help="Unused, kept for backwards compatibility")
    parser.add_argument("--credentials",
                        default=os.path.join(os.getcwd(), "credentials.json"),
                        help="Path to OAuth credentials.json")
    parser.add_argument("--sheet-config",
                        default=os.path.join(
                            os.getcwd(), "workspace", "config", "intelligence_sheet.json"
                        ),
                        help="Path to store/read spreadsheet ID")
    args = parser.parse_args()

    check_dependencies()

    # Load all data files
    data = {}
    for name, path in [
        ("performance", args.performance),
        ("hooks", args.hooks),
        ("patterns", args.patterns),
        ("gaps", args.gaps),
    ]:
        if not os.path.isfile(path):
            fail(f"{name} file not found: {path}")
        with open(path) as f:
            data[name] = json.load(f)

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

    # Write all 4 tabs (fixed names, updated in place each run)
    from datetime import date
    updated = str(date.today())

    # Tab 1: Performance Overview
    perf_rows = build_performance_rows(data["performance"])
    write_tab(
        service, spreadsheet_id, "Performance",
        perf_rows,
        col_widths=[40, 300, 150, 50, 80, 70, 80, 70, 70, 90, 60],
        wrap_cols=[1],
        score_cols=[5],  # Outlier score column
        last_updated=updated,
    )

    # Tab 2: Hook Library
    hooks_rows = build_hooks_rows(data["hooks"])
    write_tab(
        service, spreadsheet_id, "Hooks",
        hooks_rows,
        col_widths=[40, 400, 100, 70, 100, 150, 80, 70, 70, 70, 90],
        wrap_cols=[1],
        score_cols=[8],  # Performance score column
        last_updated=updated,
    )

    # Tab 3: Pattern Insights
    pattern_rows = build_patterns_rows(data["patterns"])
    write_tab(
        service, spreadsheet_id, "Patterns",
        pattern_rows,
        col_widths=[40, 300, 100, 350, 80, 350],
        wrap_cols=[1, 3, 5],
        last_updated=updated,
    )

    # Tab 4: Content Gaps
    gaps_rows = build_gaps_rows(data["gaps"])
    last_tab_id = write_tab(
        service, spreadsheet_id, "Gaps",
        gaps_rows,
        col_widths=[40, 250, 120, 100, 100, 100, 300],
        wrap_cols=[6],
        score_cols=[5],  # Opportunity score column
        last_updated=updated,
    )

    # Build result
    sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

    print(json.dumps({
        "status": "success",
        "sheet_id": spreadsheet_id,
        "sheet_url": sheet_url,
        "tabs_updated": [
            "Performance",
            "Hooks",
            "Patterns",
            "Gaps",
        ],
        "rows_written": {
            "performance": len(perf_rows) - 1,
            "hooks": len(hooks_rows) - 1,
            "patterns": len(pattern_rows) - 1,
            "gaps": len(gaps_rows) - 1,
        },
    }))


if __name__ == "__main__":
    main()
