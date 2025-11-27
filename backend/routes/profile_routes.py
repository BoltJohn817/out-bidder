from flask import Blueprint, current_app, jsonify, redirect, request
import jwt
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from auth_utils import require_auth
from config import Config
from models import create_profile, create_profile_from_oauth_state, list_profiles

profile_bp = Blueprint("profiles", __name__)


@profile_bp.get("/")
@require_auth
def get_profiles(current_user_id: str):
    profiles = list_profiles(current_user_id)
    # Convert ObjectIds to strings for JSON
    for p in profiles:
        p["_id"] = str(p.get("_id"))
        # Never leak raw Google credentials to the frontend
        if "google_credentials" in p:
            del p["google_credentials"]
    return jsonify({"profiles": profiles}), 200


@profile_bp.post("/")
@require_auth
def create_profile_route(current_user_id: str):
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    google_email = data.get("google_email")
    spreadsheet_id = data.get("spreadsheet_id")
    techstack = data.get("techstack") or []

    if not name or not google_email or not spreadsheet_id:
        return (
            jsonify(
                {
                    "message": "name, google_email and spreadsheet_id are required",
                }
            ),
            400,
        )

    if not isinstance(techstack, list):
        return jsonify({"message": "techstack must be a list"}), 400

    profile_id = create_profile(
        owner_user_id=current_user_id,
        name=name,
        google_email=google_email,
        spreadsheet_id=spreadsheet_id,
        techstack=techstack,
    )
    return jsonify({"profile_id": profile_id}), 201


def _build_oauth_flow(redirect_uri: str) -> Flow:
    client_config = {
        "web": {
            "client_id": Config.GOOGLE_CLIENT_ID,
            "client_secret": Config.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=Config.GOOGLE_SCOPES)
    flow.redirect_uri = redirect_uri
    return flow


@profile_bp.post("/google/auth-url")
@require_auth
def google_auth_url(current_user_id: str):
    """
    Start Google OAuth for a profile.
    Expects JSON: { name, google_email, spreadsheet_id, techstack[] }
    Returns: { auth_url } that the frontend should redirect the user to.
    """
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    google_email = data.get("google_email")
    spreadsheet_id = data.get("spreadsheet_id")
    techstack = data.get("techstack") or []

    if not name or not google_email or not spreadsheet_id:
        return (
            jsonify(
                {
                    "message": "name, google_email and spreadsheet_id are required",
                }
            ),
            400,
        )

    # Embed the pending profile data + user id into the OAuth state token
    state_payload = {
        "owner_user_id": current_user_id,
        "name": name,
        "google_email": google_email,
        "spreadsheet_id": spreadsheet_id,
        "techstack": techstack,
    }
    state = jwt.encode(
        state_payload,
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    flow = _build_oauth_flow(Config.GOOGLE_REDIRECT_URI)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )

    return jsonify({"auth_url": auth_url}), 200


@profile_bp.get("/google/callback")
def google_callback():
    """
    Google OAuth callback.
    - Exchanges code for tokens
    - Verifies Gmail inbox access and Spreadsheet access
    - Creates a profile with attached Google credentials.
    """
    error = request.args.get("error")
    if error:
        return jsonify({"message": f"Google OAuth error: {error}"}), 400

    code = request.args.get("code")
    state = request.args.get("state")
    if not code or not state:
        return jsonify({"message": "Missing code or state"}), 400

    try:
        state_payload = jwt.decode(
            state,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
    except Exception:
        return jsonify({"message": "Invalid state parameter"}), 400

    flow = _build_oauth_flow(Config.GOOGLE_REDIRECT_URI)
    flow.fetch_token(code=code)
    credentials: Credentials = flow.credentials

    # Verify Gmail access: get the user's email address
    gmail_service = build("gmail", "v1", credentials=credentials)
    gmail_profile = gmail_service.users().getProfile(userId="me").execute()
    email_address = gmail_profile.get("emailAddress")

    expected_email = state_payload.get("google_email")
    if expected_email and email_address and email_address.lower() != expected_email.lower():
        return (
            jsonify(
                {
                    "message": "Authenticated Google account does not match requested google_email",
                    "expected_email": expected_email,
                    "actual_email": email_address,
                }
            ),
            400,
        )

    # Verify Sheets access by fetching spreadsheet metadata
    spreadsheet_id = state_payload.get("spreadsheet_id")
    try:
        sheets_service = build("sheets", "v4", credentials=credentials)
        sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    except Exception as exc:  # noqa: BLE001
        return (
            jsonify(
                {
                    "message": "Failed to access Google Sheet with provided account.",
                    "details": str(exc),
                }
            ),
            400,
        )

    # Persist credentials with the new profile
    google_credentials = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or []),
    }

    profile_id = create_profile_from_oauth_state(
        state_payload=state_payload,
        google_credentials=google_credentials,
    )

    # Redirect back to the frontend profile page with a success flag
    frontend_base = current_app.config.get("FRONTEND_BASE_URL", "http://localhost:5173")
    frontend_url = frontend_base.rstrip("/") + "/profile"
    return redirect(f"{frontend_url}?google_connected=1&profile_id={profile_id}")


