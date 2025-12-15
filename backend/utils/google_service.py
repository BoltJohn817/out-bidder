"""Utilities for building and managing Google API services."""
from typing import Any

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

from config import Config
from extensions import db


def build_google_credentials(profile: dict[str, Any]) -> Credentials:
    """
    Build and refresh Google credentials from a profile document.
    
    Args:
        profile: Profile document containing google_credentials
    
    Returns:
        Refreshed Credentials object
    
    Raises:
        ValueError: If profile doesn't have Google credentials
    """
    creds_info = profile.get("google_credentials")
    if not creds_info:
        raise ValueError("Profile does not have Google credentials")

    creds = Credentials(
        token=creds_info.get("token"),
        refresh_token=creds_info.get("refresh_token"),
        token_uri=creds_info.get("token_uri"),
        client_id=creds_info.get("client_id"),
        client_secret=creds_info.get("client_secret"),
        scopes=creds_info.get("scopes"),
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        # Persist refreshed token
        profiles_collection = db["profiles"]
        profiles_collection.update_one(
            {"_id": profile["_id"]},
            {
                "$set": {
                    "google_credentials.token": creds.token,
                }
            },
        )

    return creds


def build_sheets_service(credentials: Credentials):
    """Build a Google Sheets API service."""
    return build("sheets", "v4", credentials=credentials)


def build_sheets_service_with_api_key(api_key: str):
    """Build a Google Sheets API service using an API key (no OAuth)."""
    if not api_key:
        raise ValueError("Google Sheets API key is not configured")
    return build("sheets", "v4", developerKey=api_key)


def build_gmail_service(credentials: Credentials):
    """Build a Gmail API service."""
    return build("gmail", "v1", credentials=credentials)


def get_sheet_title(service, spreadsheet_id: str, sheet_id: int) -> str | None:
    """
    Get the title of a sheet by its ID.
    
    Args:
        service: Google Sheets service instance
        spreadsheet_id: ID of the spreadsheet
        sheet_id: ID of the sheet
    
    Returns:
        Sheet title or None if not found
    """
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = meta.get("sheets", [])
    
    for s in sheets:
        props = s.get("properties", {})
        if props.get("sheetId") == sheet_id:
            return props.get("title")
    
    return None

