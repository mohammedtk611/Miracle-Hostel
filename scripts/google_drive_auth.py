"""
Google Drive OAuth 2.0 Local Authorization Utility for Miracle Hostel.
Guides administrators through generating a long-term refresh token with scope:
    https://www.googleapis.com/auth/drive.file

Run this script on your local machine once before deploying to Render:
    python scripts/google_drive_auth.py
or
    python scripts/google_drive_auth.py --client-id <id> --client-secret <secret>
"""
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present in project root
basedir = Path(__file__).resolve().parent.parent
load_dotenv(basedir / '.env')


def run_auth(client_id=None, client_secret=None):
    """Execute local OAuth 2.0 consent flow and output refresh token."""
    client_id = client_id or os.environ.get('GOOGLE_DRIVE_CLIENT_ID')
    client_secret = client_secret or os.environ.get('GOOGLE_DRIVE_CLIENT_SECRET')

    if not client_id:
        client_id = input("Enter your Google Cloud OAuth 2.0 Client ID: ").strip()
    if not client_secret:
        client_secret = input("Enter your Google Cloud OAuth 2.0 Client Secret: ").strip()

    if not client_id or not client_secret:
        print("\n[Error] Both Client ID and Client Secret are required.")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("\n[Error] google-auth-oauthlib is required. Install via: pip install google-auth-oauthlib")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost", "http://localhost:8080/"]
        }
    }

    scopes = ["https://www.googleapis.com/auth/drive.file"]

    print("\n" + "=" * 76)
    print("  Miracle Hostel - Google Drive OAuth 2.0 Authorization Flow")
    print("=" * 76)
    print("Starting local authorization server on port 8080...")
    print("Scope requested: https://www.googleapis.com/auth/drive.file")
    print("(Allows Miracle Hostel to manage only files that it creates)\n")

    try:
        flow = InstalledAppFlow.from_client_config(client_config, scopes=scopes)
        creds = flow.run_local_server(
            port=8080,
            access_type='offline',
            prompt='consent',
            success_message="Authorization completed! You may close this browser window and return to the terminal."
        )
    except Exception as e:
        print(f"\n[Error] Authorization failed: {e}")
        sys.exit(1)

    if not creds.refresh_token:
        print("\n[Warning] No refresh token was returned by Google.")
        print("This can happen if consent was already granted without offline access.")
        print("To fix: Go to https://myaccount.google.com/permissions, remove access for this app, and re-run.")
        sys.exit(1)

    print("\n" + "=" * 76)
    print("  SUCCESS: Google Drive Refresh Token Generated!")
    print("=" * 76)
    print("\nCopy the following environment variables into your Render Web Service dashboard:\n")
    print("STORAGE_BACKEND=google_drive")
    print(f"GOOGLE_DRIVE_CLIENT_ID={client_id}")
    print(f"GOOGLE_DRIVE_CLIENT_SECRET={client_secret}")
    print(f"GOOGLE_DRIVE_REFRESH_TOKEN={creds.refresh_token}")
    print("GOOGLE_DRIVE_FOLDER_ID=  <-- Leave blank to auto-create, or specify a private folder ID")
    print("\nCRITICAL GOOGLE CLOUD CONFIGURATION NOTE:")
    print("1. In Google Cloud Console (APIs & Services -> OAuth consent screen):")
    print("   Ensure the 'Publishing Status' is set to 'In Production'.")
    print("   If left in 'Testing' status, Google automatically expires refresh tokens after 7 days!")
    print("2. Keep this refresh token strictly confidential. Never commit it to GitHub.\n")
    print("=" * 76 + "\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate Google Drive OAuth Refresh Token for Miracle Hostel")
    parser.add_argument("--client-id", help="Google Cloud OAuth 2.0 Client ID")
    parser.add_argument("--client-secret", help="Google Cloud OAuth 2.0 Client Secret")
    args = parser.parse_args()

    run_auth(client_id=args.client_id, client_secret=args.client_secret)
