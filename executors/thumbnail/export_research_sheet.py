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
        [--analysis workspace/temp/thumbnail/<PROJECT>/research/cross_niche/analysis.json] \
        [--credentials credentials.json] \
        [--sheet-config workspace/config/research_sheet.json]

    python3 executors/thumbnail/export_research_sheet.py --help

Arguments:
    --input PATH          Path to metadata.json (scored research results)
    --tab-name NAME       Tab/sheet name (e.g. YYYYMMDD_slug)

Options:
    --analysis PATH       Path to analysis.json (title variants)
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

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

TOKEN_DIR = os.path.expanduser("~/.cache/youtube-assistant")
TOKEN_PATH = os.path.join(TOKEN_DIR, "google_sheets_token.json")

SPREADSHEET_TITLE = "YouTube Thumbnail Research"

MAX_TRANSCRIPT_CHARS = 4000


def fail(message: str) -> None:
    """Print error JSON to stdout and exit 1."""
    print(json.dumps({"error": message}))
    sys.exit(1)


def check_dependencies() -> None:
    try:
        import google.oauth2.credentials  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
        import googleapiclient.discovery  # noqa: F401
    except ImportError:
        fail(
            "Google API libraries not found. Install with:\n"
            "  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )


def authenticate(credentials_path: str):
    """Authenticate with Google OAuth2, returning credentials."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if not os.path.exists(credentials_path):
            fail(
                f"credentials.json not found at {credentials_path}. To set up:\n"
                "  1. Go to https://console.cloud.google.com/\n"
                "  2. Create or select a project\n"
                "  3. Enable the Google Sheets API\n"
                "  4. Create OAuth 2.0 credentials (Desktop application)\n"
                "  5. Download the JSON and save it as credentials.json in the project root\n"
                "  (See credentials.sample.json for the expected format)"
            )
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        try:
            creds = flow.run_local_server(port=0)
        except Exception:
            try:
                creds = flow.run_console()
            except Exception as e:
                fail(f"OAuth authentication failed: {e}")

    os.makedirs(TOKEN_DIR, exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    return creds


def load_sheet_config(config_path: str) -> dict | None:
    """Load existing sheet config (sheet_id) if it exists."""
    if os.path.isfile(config_path):
        with open(config_path) as f:
            return json.load(f)
    return None


def save_sheet_config(config_path: str, sheet_id: str, sheet_url: str) -> None:
    """Save sheet config for reuse across runs."""
    from datetime import date
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump({
            "sheet_id": sheet_id,
            "sheet_url": sheet_url,
            "created": str(date.today()),
        }, f, indent=2)


def sheet_exists(service, sheet_id: str) -> bool:
    """Check if a spreadsheet still exists and is accessible."""
    try:
        service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        return True
    except Exception:
        return False


def create_spreadsheet(service) -> tuple[str, str]:
    """Create a new spreadsheet and return (sheet_id, sheet_url)."""
    body = {"properties": {"title": SPREADSHEET_TITLE}}
    spreadsheet = service.spreadsheets().create(body=body).execute()
    sheet_id = spreadsheet["spreadsheetId"]
    sheet_url = spreadsheet["spreadsheetUrl"]
    return sheet_id, sheet_url


def add_tab(service, spreadsheet_id: str, tab_name: str) -> int:
    """Add a new tab to the spreadsheet. Returns the new sheet (tab) ID."""
    body = {
        "requests": [{
            "addSheet": {
                "properties": {"title": tab_name}
            }
        }]
    }
    resp = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body=body
    ).execute()
    return resp["replies"][0]["addSheet"]["properties"]["sheetId"]


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

def build_rows(videos: list[dict], analysis: dict[str, dict]) -> list[list]:
    """Build header + data rows for the 19-column spreadsheet layout."""
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
        "Title Variant 1",          # 13
        "Title Variant 2",          # 14
        "Title Variant 3",          # 15
        "Raw Transcript",           # 16
        "Publish Date",             # 17
        "Source",                   # 18
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
        if source == "keyword":
            source_detail = "keyword: {}".format(vid.get("_search_keyword", ""))
        elif source == "channel":
            source_detail = "channel: {}".format(vid.get("_source_channel", vid.get("channel", "")))
        else:
            source_detail = source

        # Raw transcript (first 4000 chars)
        transcript_text = ""
        transcript_path = vid.get("transcript_path")
        if transcript_path and os.path.isfile(transcript_path):
            try:
                with open(transcript_path) as f:
                    transcript_text = f.read()[:MAX_TRANSCRIPT_CHARS]
            except Exception:
                pass

        # Analysis data (title variants)
        vid_analysis = analysis.get(video_id, {})

        # Category: from analysis if available, else auto-classify
        category = vid_analysis.get("category") or categorize(vid.get("title", ""))

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
            vid_analysis.get("title_variant_1", ""),
            vid_analysis.get("title_variant_2", ""),
            vid_analysis.get("title_variant_3", ""),
            transcript_text,
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
        # Column widths (18 columns):
        # Thumbnail (180), Thumbnail URL (200), Title (350),
        # Final Score (90), Outlier Score (80), Days Old (70),
        # Video Link (280), View Count (90), Duration (70),
        # Channel Name (150), Channel Avg Views (100), Category (100),
        # Title Variant 1-3 (250 each), Raw Transcript (400),
        # Publish Date (100), Source (200)
    ]

    col_widths = [
        180, 200, 350, 90, 80, 70, 280, 90, 70,
        150, 100, 100, 250, 250, 250, 400, 100, 200,
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

    # Text wrapping for Title Variants (12-14), Raw Transcript (15)
    for col_idx in [12, 13, 14, 15]:
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
    parser.add_argument("--analysis", default=None,
                        help="Path to analysis.json (AI summaries + title variants)")
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

    # Load analysis data if provided
    analysis = {}
    if args.analysis and os.path.isfile(args.analysis):
        with open(args.analysis) as f:
            analysis_list = json.load(f)
        analysis = {a["video_id"]: a for a in analysis_list}

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
        spreadsheet_id, sheet_url = create_spreadsheet(service)
        save_sheet_config(args.sheet_config, spreadsheet_id, sheet_url)

    # Add new tab
    tab_id = add_tab(service, spreadsheet_id, args.tab_name)

    # Build and write rows
    rows = build_rows(videos, analysis)

    range_name = f"'{args.tab_name}'!A1"
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body={"values": rows},
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
