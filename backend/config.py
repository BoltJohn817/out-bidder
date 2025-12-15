import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/outbidder")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)

    # Google OAuth / API
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv(
        "GOOGLE_REDIRECT_URI", "http://localhost:5001/api/profiles/google/callback"
    )

    # Scopes needed: read Gmail inbox metadata + read/write a spreadsheet
    GOOGLE_SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/spreadsheets",
    ]

    # Optional: Google Sheets API key (used for Outlook-only profiles without Google OAuth)
    GOOGLE_SHEETS_API_KEY = os.getenv("GOOGLE_SHEETS_API_KEY", "")

    # Microsoft OAuth / API (Outlook)
    MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")
    MICROSOFT_REDIRECT_URI = os.getenv(
        "MICROSOFT_REDIRECT_URI", "http://localhost:5001/api/profiles/outlook/callback"
    )
    MICROSOFT_AUTHORITY = "https://login.microsoftonline.com/common"
    
    # Scopes needed: read Outlook mail + read user profile (for email verification)
    # Note: User.Read is needed to access /me endpoint to get user email
    MICROSOFT_SCOPES = [
        "https://graph.microsoft.com/Mail.Read",
        "https://graph.microsoft.com/User.Read",
    ]

    # Frontend base URL to redirect back to after OAuth
    FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")

