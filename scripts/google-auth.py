#!/usr/bin/env python3
"""
One-time Google OAuth authorization for OpenClaw.
Run this once — it saves a token that all skills reuse.
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

CREDS_FILE = os.path.expanduser("~/.openclaw/credentials/google-oauth.json")
TOKEN_FILE = os.path.expanduser("~/.openclaw/credentials/google-token.pkl")

def main():
    flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)
    print(f"\nAuthorized. Token saved to: {TOKEN_FILE}")
    print("OpenClaw can now access Gmail, Calendar, Contacts, Sheets, Drive, YouTube.")

if __name__ == "__main__":
    main()
