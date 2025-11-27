from flask import Blueprint, current_app, jsonify, redirect, request
import jwt
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from auth_utils import require_auth
from config import Config
from models import (
    clear_application_statuses_for_sheet,
    create_or_update_profile_from_oauth_state,
    create_profile,
    get_application_statuses_for_sheet,
    get_profile_with_credentials,
    list_profiles,
    upsert_application_status,
    update_profile,
)
from gmail_utils import search_gmail_for_company

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


@profile_bp.put("/<profile_id>")
@require_auth
def update_profile_route(current_user_id: str, profile_id: str):
    """
    Update an existing profile's basic fields (not Google credentials).
    Body can include: name, google_email, spreadsheet_id, techstack[]
    """
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    google_email = data.get("google_email")
    spreadsheet_id = data.get("spreadsheet_id")
    techstack = data.get("techstack")

    if techstack is not None and not isinstance(techstack, list):
        return jsonify({"message": "techstack must be a list"}), 400

    updated = update_profile(
        owner_user_id=current_user_id,
        profile_id=profile_id,
        name=name,
        google_email=google_email,
        spreadsheet_id=spreadsheet_id,
        techstack=techstack,
    )
    if not updated:
        return jsonify({"message": "Profile not found"}), 404

    return jsonify({"profile_id": profile_id}), 200


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

    # Optional: profile_id when refreshing Google credentials for an existing profile
    profile_id = data.get("profile_id")

    # Embed the pending profile data + user id into the OAuth state token
    state_payload = {
        "owner_user_id": current_user_id,
        "name": name,
        "google_email": google_email,
        "spreadsheet_id": spreadsheet_id,
        "techstack": techstack,
    }
    if profile_id:
        state_payload["profile_id"] = profile_id
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

    profile_id = create_or_update_profile_from_oauth_state(
        state_payload=state_payload,
        google_credentials=google_credentials,
    )

    # Redirect back to the frontend profile page with a success flag
    frontend_base = current_app.config.get("FRONTEND_BASE_URL", "http://localhost:5173")
    frontend_url = frontend_base.rstrip("/") + "/profile"
    return redirect(f"{frontend_url}?google_connected=1&profile_id={profile_id}")


def _build_google_credentials(profile: dict) -> Credentials:
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
        profiles_collection = get_profile_with_credentials.__globals__["profiles_collection"]  # type: ignore[index]
        profiles_collection().update_one(
            {"_id": profile["_id"]},
            {
                "$set": {
                    "google_credentials.token": creds.token,
                }
            },
        )

    return creds


@profile_bp.get("/<profile_id>/sheets")
@require_auth
def list_sheets(current_user_id: str, profile_id: str):
    """List sheets (tabs) available in the profile's spreadsheet."""
    profile = get_profile_with_credentials(current_user_id, profile_id)
    if not profile:
        return jsonify({"message": "Profile not found"}), 404

    try:
        creds = _build_google_credentials(profile)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400

    spreadsheet_id = profile.get("spreadsheet_id")
    service = build("sheets", "v4", credentials=creds)
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = meta.get("sheets", [])

    result = []
    for s in sheets:
        props = s.get("properties", {})
        result.append(
            {
                "sheet_id": props.get("sheetId"),
                "title": props.get("title"),
                "index": props.get("index"),
            }
        )

    return jsonify({"sheets": result}), 200


@profile_bp.get("/<profile_id>/sheets/<int:sheet_id>")
@require_auth
def get_sheet_values(current_user_id: str, profile_id: str, sheet_id: int):
    """Return values from columns A-G of the given sheet."""
    profile = get_profile_with_credentials(current_user_id, profile_id)
    if not profile:
        return jsonify({"message": "Profile not found"}), 404

    try:
        creds = _build_google_credentials(profile)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400

    spreadsheet_id = profile.get("spreadsheet_id")
    service = build("sheets", "v4", credentials=creds)
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = meta.get("sheets", [])

    title = None
    for s in sheets:
        props = s.get("properties", {})
        if props.get("sheetId") == sheet_id:
            title = props.get("title")
            break

    if not title:
        return jsonify({"message": "Sheet not found"}), 404

    range_a_g = f"'{title}'!A:G"
    res = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_a_g)
        .execute()
    )
    values = res.get("values", [])

    # If there are no rows, just return empty headers/rows
    if not values:
        return (
            jsonify(
                {
                    "sheet_id": sheet_id,
                    "title": title,
                    "headers": [],
                    "rows": [],
                }
            ),
            200,
        )

    # Treat the first row as headers, remaining rows as data.
    raw_headers = values[0]
    data_rows = values[1:]

    # Only look at columns A–G (0–6)
    headers = (raw_headers + [""] * 7)[:7]

    rows: list[list[str]] = []
    for row in data_rows:
        padded = (row + [""] * 7)[:7]
        rows.append(padded)

    # Load any cached application statuses for this sheet
    spreadsheet_id = profile.get("spreadsheet_id")
    status_map = get_application_statuses_for_sheet(
        owner_user_id=current_user_id,
        profile_id=profile_id,
        spreadsheet_id=spreadsheet_id,
        sheet_id=sheet_id,
    )
    statuses: list[str | None] = [status_map.get(i) for i in range(len(rows))]

    return jsonify(
        {
            "sheet_id": sheet_id,
            "title": title,
            "headers": headers,
            "rows": rows,
            "statuses": statuses,
        }
    ), 200


@profile_bp.post("/<profile_id>/gmail/check-application")
@require_auth
def check_gmail_application(current_user_id: str, profile_id: str):
    """
    Check if a position appears to be applied based on Gmail messages for the profile's account.

    Body: {
      company_name: string,
      applied_date: string,
      applied_time?: string,
      sheet_id: int,
      row_index: int,
      position?: string,
      job_url?: string
    }
    Returns: { applied: bool }
    """
    data = request.get_json(silent=True) or {}
    company_name = data.get("company_name")
    applied_date = data.get("applied_date")
    applied_time = data.get("applied_time")
    sheet_id = data.get("sheet_id")
    row_index = data.get("row_index")
    position = data.get("position")
    job_url = data.get("job_url")

    if not company_name or not applied_date or sheet_id is None or row_index is None:
        return jsonify({"message": "company_name, applied_date, sheet_id and row_index are required"}), 400

    profile = get_profile_with_credentials(current_user_id, profile_id)
    if not profile:
        return jsonify({"message": "Profile not found"}), 404

    try:
        creds = _build_google_credentials(profile)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400

    try:
        applied = search_gmail_for_company(
            creds=creds,
            company=company_name,
            applied_date=applied_date,
            applied_time=applied_time,
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"message": f"Failed to query Gmail: {exc}"}), 500

    # Persist status so subsequent loads can avoid recalculation
    spreadsheet_id = profile.get("spreadsheet_id")
    upsert_application_status(
        owner_user_id=current_user_id,
        profile_id=profile_id,
        spreadsheet_id=spreadsheet_id,
        sheet_id=int(sheet_id),
        row_index=int(row_index),
        company_name=company_name,
        position=position,
        job_url=job_url,
        applied_date=applied_date,
        status="applied" if applied else "not_applied",
    )

    return jsonify({"applied": applied}), 200


@profile_bp.post("/<profile_id>/sheets/<int:sheet_id>/gmail/check-all")
@require_auth
def check_gmail_applications_for_sheet(current_user_id: str, profile_id: str, sheet_id: int):
    """
    Recalculate application status for all rows in a sheet.
    Ignores any cached statuses and overwrites them.
    Returns: { statuses: [ 'applied' | 'not_applied' | null, ... ] }
    """
    profile = get_profile_with_credentials(current_user_id, profile_id)
    if not profile:
        return jsonify({"message": "Profile not found"}), 404

    try:
        creds = _build_google_credentials(profile)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400

    spreadsheet_id = profile.get("spreadsheet_id")
    service = build("sheets", "v4", credentials=creds)

    # Fetch sheet metadata to get title
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = meta.get("sheets", [])
    title = None
    for s in sheets:
        props = s.get("properties", {})
        if props.get("sheetId") == sheet_id:
            title = props.get("title")
            break
    if not title:
        return jsonify({"message": "Sheet not found"}), 404

    # Fetch values A:G
    range_a_g = f"'{title}'!A:G"
    res = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_a_g)
        .execute()
    )
    values = res.get("values", [])
    if not values:
        return jsonify({"statuses": []}), 200

    headers = (values[0] + [""] * 7)[:7]
    data_rows = values[1:]

    # Detect relevant columns by header names
    def _find_index(predicate, default: int) -> int:
        try:
            return next(i for i, h in enumerate(headers) if predicate(h.lower()))
        except StopIteration:
            return default

    company_idx = _find_index(lambda h: "company" in h, 0)
    date_idx = _find_index(lambda h: "date" in h, 1)
    position_idx = _find_index(lambda h: "position" in h, 2)
    job_url_idx = _find_index(lambda h: "job url" in h or "url" in h, 3)

    # Clear old cache for this sheet so we only store fresh statuses
    clear_application_statuses_for_sheet(
        owner_user_id=current_user_id,
        profile_id=profile_id,
        spreadsheet_id=spreadsheet_id,
        sheet_id=sheet_id,
    )

    statuses: list[str | None] = []

    for idx, row in enumerate(data_rows):
        padded = (row + [""] * 7)[:7]
        company = padded[company_idx]
        applied_date = padded[date_idx]
        position = padded[position_idx]
        job_url = padded[job_url_idx]

        if not company or not applied_date:
            statuses.append(None)
            continue

        try:
            applied = search_gmail_for_company(
                creds=creds,
                company=company,
                applied_date=applied_date,
                applied_time=None,
            )
        except Exception:
            statuses.append(None)
            continue

        status_str = "applied" if applied else "not_applied"
        statuses.append(status_str)

        upsert_application_status(
            owner_user_id=current_user_id,
            profile_id=profile_id,
            spreadsheet_id=spreadsheet_id,
            sheet_id=sheet_id,
            row_index=idx,
            company_name=company,
            position=position,
            job_url=job_url,
            applied_date=applied_date,
            status=status_str,
        )

    return jsonify({"statuses": statuses}), 200


