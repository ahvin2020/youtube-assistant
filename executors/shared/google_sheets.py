"""Shared Google Sheets authentication and management utilities.

Used by executors/thumbnail/export_research_sheet.py and
executors/ideas/export_ideas_sheet.py for OAuth2 auth, spreadsheet
creation, and tab management.

Depends on: google-api-python-client google-auth-httplib2 google-auth-oauthlib
"""

from __future__ import annotations

import json
import os
import sys

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

TOKEN_DIR = os.path.expanduser("~/.cache/youtube-assistant")
TOKEN_PATH = os.path.join(TOKEN_DIR, "google_sheets_token.json")


def fail(message: str) -> None:
    """Print error JSON to stdout and exit 1."""
    print(json.dumps({"status": "error", "error": message}))
    sys.exit(1)


def check_dependencies() -> None:
    """Verify that Google API libraries are installed."""
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
    """Authenticate with Google OAuth2, returning credentials.

    Loads cached token if available, refreshes if expired, or runs
    the OAuth flow to obtain new credentials.
    """
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


def create_spreadsheet(service, title: str) -> tuple[str, str]:
    """Create a new spreadsheet and return (sheet_id, sheet_url)."""
    body = {"properties": {"title": title}}
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


def get_tab_id(service, spreadsheet_id: str, tab_name: str) -> int | None:
    """Return the sheet (tab) ID if a tab with tab_name exists, else None."""
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        for s in meta.get("sheets", []):
            if s["properties"]["title"] == tab_name:
                return s["properties"]["sheetId"]
    except Exception:
        pass
    return None


def clear_tab(service, spreadsheet_id: str, tab_id: int, tab_name: str) -> None:
    """Clear all data, formatting, and conditional format rules from a tab."""
    # Clear cell values
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab_name}'!A:ZZ",
    ).execute()

    # Remove conditional format rules for this tab and reset formatting
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    requests = []

    # Delete conditional format rules (in reverse order to keep indices stable)
    cf_rules = []
    for s in meta.get("sheets", []):
        if s["properties"]["sheetId"] == tab_id:
            cf_rules = s.get("conditionalFormats", [])
            break
    for i in range(len(cf_rules) - 1, -1, -1):
        requests.append({
            "deleteConditionalFormatRule": {
                "sheetId": tab_id,
                "index": i,
            }
        })

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()


def get_or_create_tab(service, spreadsheet_id: str, tab_name: str) -> int:
    """Return existing tab ID or create a new tab. Clears data if existing."""
    tab_id = get_tab_id(service, spreadsheet_id, tab_name)
    if tab_id is not None:
        clear_tab(service, spreadsheet_id, tab_id, tab_name)
        return tab_id
    return add_tab(service, spreadsheet_id, tab_name)
