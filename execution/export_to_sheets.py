#!/usr/bin/env python3
"""
Google Sheets Export - Layer 3 Execution Script
Exports coach profiles to Google Sheets for projectFIVE.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment
load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

# Google Sheets API settings
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Column headers (A-O)
HEADERS = [
    "Coach Name",           # A
    "Nationality",          # B
    "Age / DOB",            # C
    "Current Role",         # D
    "Current Club",         # E
    "License Level",        # F
    "Agent Name",           # G
    "Agent Agency",         # H
    "TM Profile Link",      # I
    "Career History",       # J
    "Key Teammates",        # K
    "Coaches Worked With",  # L
    "SDs Worked With",      # M
    "Top Players Coached",  # N
    "Background Summary",   # O
]


def get_credentials():
    """Get or refresh Google API credentials."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"ERROR: credentials.json not found at {CREDENTIALS_FILE}")
                print("Download it from Google Cloud Console:")
                print("1. Go to https://console.cloud.google.com/apis/credentials")
                print("2. Create OAuth 2.0 Client ID (Desktop App)")
                print("3. Download JSON and save as credentials.json")
                return None

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def format_career_history(career: list) -> str:
    """Format career history as readable text."""
    if not career:
        return ""

    lines = []
    for entry in career:
        club = entry.get("club", "Unknown")
        role = entry.get("role", "")
        period = entry.get("period", "")
        lines.append(f"• {club} ({role}) - {period}")

    return "\n".join(lines)


def format_list(items: list, key: str = "name") -> str:
    """Format a list of items as comma-separated text."""
    if not items:
        return ""

    names = [item.get(key, str(item)) for item in items if isinstance(item, dict)]
    if not names:
        names = [str(item) for item in items]

    return ", ".join(names[:15])  # Limit to 15 items


def profile_to_row(profile: dict, teammates: dict = None, players_used: dict = None) -> list:
    """Convert coach profile data to a spreadsheet row."""
    # Basic profile data
    row = [
        profile.get("name", ""),                                    # A: Name
        profile.get("nationality", ""),                             # B: Nationality
        profile.get("dob", f"Age: {profile.get('age', 'Unknown')}"),  # C: Age/DOB
        profile.get("current_role", ""),                            # D: Current Role
        profile.get("current_club", ""),                            # E: Current Club
        profile.get("license", "Unknown"),                          # F: License
        profile.get("agent_name", ""),                              # G: Agent Name
        profile.get("agent_agency", ""),                            # H: Agent Agency
        profile.get("url", ""),                                     # I: TM Link
        format_career_history(profile.get("career_history", [])),   # J: Career History
    ]

    # Teammates data
    if teammates:
        row.append(format_list(teammates.get("players", [])[:10]))         # K: Key Teammates
        row.append(format_list(teammates.get("coaches", [])))              # L: Coaches Worked With
        row.append(format_list(teammates.get("sporting_directors", [])))   # M: SDs Worked With
    else:
        row.extend(["", "", ""])

    # Players used data
    if players_used:
        significant = players_used.get("significant_players", [])
        players_text = ", ".join([
            f"{p['name']} ({p.get('games', 0)} games)"
            for p in significant[:10]
        ])
        row.append(players_text)  # N: Top Players Coached
    else:
        row.append("")

    # Background summary (placeholder - can be AI-generated)
    row.append("")  # O: Background Summary

    return row


def export_coach(
    profile: dict,
    teammates: dict = None,
    players_used: dict = None,
    sheet_id: str = None,
    sheet_name: str = "Coaches Database"
) -> bool:
    """
    Export a single coach to Google Sheets.
    Returns True if successful.
    """
    print(f"\n{'=' * 50}")
    print(f"Exporting to Google Sheets")
    print(f"{'=' * 50}")

    # Get sheet ID from env if not provided
    if not sheet_id:
        sheet_id = os.getenv("GOOGLE_SHEET_ID")

    if not sheet_id:
        print("ERROR: No Google Sheet ID provided.")
        print("Set GOOGLE_SHEET_ID in .env or pass --sheet-id")
        return False

    # Get credentials
    creds = get_credentials()
    if not creds:
        return False

    try:
        service = build("sheets", "v4", credentials=creds)
        sheets = service.spreadsheets()

        # Check if sheet exists, create headers if needed
        try:
            result = sheets.values().get(
                spreadsheetId=sheet_id,
                range=f"{sheet_name}!A1:O1"
            ).execute()

            existing_headers = result.get("values", [[]])[0]
            if not existing_headers:
                # Add headers
                sheets.values().update(
                    spreadsheetId=sheet_id,
                    range=f"{sheet_name}!A1:O1",
                    valueInputOption="RAW",
                    body={"values": [HEADERS]}
                ).execute()
                print("  Added headers to sheet")

        except HttpError as e:
            if "Unable to parse range" in str(e):
                # Sheet doesn't exist - create it
                print(f"  Creating new sheet: {sheet_name}")
                sheets.batchUpdate(
                    spreadsheetId=sheet_id,
                    body={
                        "requests": [{
                            "addSheet": {
                                "properties": {"title": sheet_name}
                            }
                        }]
                    }
                ).execute()

                # Add headers
                sheets.values().update(
                    spreadsheetId=sheet_id,
                    range=f"{sheet_name}!A1:O1",
                    valueInputOption="RAW",
                    body={"values": [HEADERS]}
                ).execute()
            else:
                raise

        # Check if coach already exists (by URL in column I)
        coach_url = profile.get("url", "")
        result = sheets.values().get(
            spreadsheetId=sheet_id,
            range=f"{sheet_name}!I:I"
        ).execute()

        existing_urls = [row[0] if row else "" for row in result.get("values", [])]

        if coach_url in existing_urls:
            row_index = existing_urls.index(coach_url) + 1
            print(f"  Coach already exists at row {row_index}")
            # Update existing row
            update_range = f"{sheet_name}!A{row_index}:O{row_index}"
        else:
            # Append new row
            row_index = len(existing_urls) + 1
            update_range = f"{sheet_name}!A{row_index}:O{row_index}"
            print(f"  Adding new coach at row {row_index}")

        # Format row data
        row_data = profile_to_row(profile, teammates, players_used)

        # Write to sheet
        sheets.values().update(
            spreadsheetId=sheet_id,
            range=update_range,
            valueInputOption="RAW",
            body={"values": [row_data]}
        ).execute()

        print(f"\n✓ Exported: {profile.get('name', 'Unknown')}")
        print(f"  Sheet: https://docs.google.com/spreadsheets/d/{sheet_id}")

        return True

    except HttpError as e:
        print(f"ERROR: Google Sheets API error: {e}")
        return False


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Export coach to Google Sheets")
    parser.add_argument("--profile", "-p", required=True, help="Coach profile JSON file")
    parser.add_argument("--teammates", "-t", help="Teammates JSON file")
    parser.add_argument("--players", help="Players used JSON file")
    parser.add_argument("--sheet-id", help="Google Sheet ID")
    parser.add_argument("--sheet-name", default="Coaches Database", help="Sheet name")

    args = parser.parse_args()

    # Load profile
    with open(args.profile, "r") as f:
        profile = json.load(f)

    # Load optional data
    teammates = None
    if args.teammates and Path(args.teammates).exists():
        with open(args.teammates, "r") as f:
            teammates = json.load(f)

    players_used = None
    if args.players and Path(args.players).exists():
        with open(args.players, "r") as f:
            players_used = json.load(f)

    # Export
    success = export_coach(
        profile=profile,
        teammates=teammates,
        players_used=players_used,
        sheet_id=args.sheet_id,
        sheet_name=args.sheet_name
    )

    return success


if __name__ == "__main__":
    main()
