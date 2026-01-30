from flask import Blueprint, current_app, jsonify, redirect, request
import jwt
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from auth_utils import require_auth
from config import Config
from models import (
    clear_application_statuses_for_sheet,
    create_or_update_profile_from_oauth_state,
    create_profile,
    delete_profile,
    get_application_statuses_for_sheet,
    get_profile_with_credentials,
    list_profiles,
    upsert_application_status,
    update_profile,
)
from gmail_utils import search_gmail_for_company
from outlook_utils import search_outlook_for_company
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread
from msal import ConfidentialClientApplication
import requests
from utils import (
    build_google_credentials,
    build_sheets_service,
    build_sheets_service_with_api_key,
    build_gmail_service,
    get_sheet_title,
    find_header_row,
    parse_sheet_columns,
    convert_objectids_in_list,
    error_response,
    success_response,
    validation_error,
)
from utils.outlook_service import build_outlook_credentials, get_outlook_user_email
from utils.job_status_store import create_job, update_job_progress, complete_job, fail_job, get_job_status

profile_bp = Blueprint("profiles", __name__)


@profile_bp.get("/")
@require_auth
def get_profiles(current_user_id: str):
    profiles = list_profiles(current_user_id)
    # Convert ObjectIds to strings for JSON
    profiles = convert_objectids_in_list(profiles)
    # Never leak raw credentials to the frontend
    for p in profiles:
        if "google_credentials" in p:
            del p["google_credentials"]
        if "outlook_credentials" in p:
            del p["outlook_credentials"]
    return success_response({"profiles": profiles})


@profile_bp.post("/")
@require_auth
def create_profile_route(current_user_id: str):
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    google_email = data.get("google_email")
    spreadsheet_id = data.get("spreadsheet_id")
    techstack = data.get("techstack") or []

    if not name or not google_email or not spreadsheet_id:
        missing = []
        if not name:
            missing.append("name")
        if not google_email:
            missing.append("google_email")
        if not spreadsheet_id:
            missing.append("spreadsheet_id")
        return validation_error(missing)

    if not isinstance(techstack, list):
        return error_response("techstack must be a list")

    profile_id = create_profile(
        owner_user_id=current_user_id,
        name=name,
        google_email=google_email,
        spreadsheet_id=spreadsheet_id,
        techstack=techstack,
    )
    return success_response({"profile_id": profile_id}, 201)


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
        return error_response("techstack must be a list")

    updated = update_profile(
        owner_user_id=current_user_id,
        profile_id=profile_id,
        name=name,
        google_email=google_email,
        spreadsheet_id=spreadsheet_id,
        techstack=techstack,
    )
    if not updated:
        return error_response("Profile not found", 404)

    return success_response({"profile_id": profile_id})


@profile_bp.delete("/<profile_id>")
@require_auth
def delete_profile_route(current_user_id: str, profile_id: str):
    """
    Delete a profile and all associated data (applications, bids references).
    """
    deleted = delete_profile(
        owner_user_id=current_user_id,
        profile_id=profile_id,
    )
    if not deleted:
        return error_response("Profile not found", 404)

    return success_response({"message": "Profile deleted successfully"})


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


def _build_microsoft_oauth_app():
    """Build MSAL ConfidentialClientApplication for Microsoft OAuth."""
    return ConfidentialClientApplication(
        client_id=Config.MICROSOFT_CLIENT_ID,
        client_credential=Config.MICROSOFT_CLIENT_SECRET,
        authority=Config.MICROSOFT_AUTHORITY,
    )


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
        missing = []
        if not name:
            missing.append("name")
        if not google_email:
            missing.append("google_email")
        if not spreadsheet_id:
            missing.append("spreadsheet_id")
        return validation_error(missing)

    # Optional: profile_id when refreshing Google credentials for an existing profile
    profile_id = data.get("profile_id")

    # Embed the pending profile data + user id into the OAuth state token
    state_payload = {
        "owner_user_id": current_user_id,
        "name": name,
        "google_email": google_email,
        "spreadsheet_id": spreadsheet_id,
        "techstack": techstack,
        "email_provider": "gmail",
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

    return success_response({"auth_url": auth_url})


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
        return error_response(f"Google OAuth error: {error}")

    code = request.args.get("code")
    state = request.args.get("state")
    if not code or not state:
        return error_response("Missing code or state")

    try:
        state_payload = jwt.decode(
            state,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
    except Exception:
        return error_response("Invalid state parameter")

    flow = _build_oauth_flow(Config.GOOGLE_REDIRECT_URI)
    flow.fetch_token(code=code)
    credentials: Credentials = flow.credentials

    # Verify Gmail access: get the user's email address
    gmail_service = build_gmail_service(credentials)
    gmail_profile = gmail_service.users().getProfile(userId="me").execute()
    email_address = gmail_profile.get("emailAddress")

    expected_email = state_payload.get("google_email")
    if expected_email and email_address and email_address.lower() != expected_email.lower():
        return error_response(
            "Authenticated Google account does not match requested google_email",
            details={"expected_email": expected_email, "actual_email": email_address}
        )

    # Verify Sheets access by fetching spreadsheet metadata
    spreadsheet_id = state_payload.get("spreadsheet_id")
    try:
        sheets_service = build_sheets_service(credentials)
        sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    except Exception as exc:  # noqa: BLE001
        return error_response(
            "Failed to access Google Sheet with provided account.",
            details=str(exc)
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


@profile_bp.post("/outlook/auth-url")
@require_auth
def outlook_auth_url(current_user_id: str):
    """
    Start Microsoft/Outlook OAuth for a profile.
    Expects JSON: { name, google_email, spreadsheet_id, techstack[], email_provider }
    Returns: { auth_url } that the frontend should redirect the user to.
    """
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    google_email = data.get("google_email")
    spreadsheet_id = data.get("spreadsheet_id")
    techstack = data.get("techstack") or []
    email_provider = data.get("email_provider", "outlook")

    if not name or not google_email or not spreadsheet_id:
        missing = []
        if not name:
            missing.append("name")
        if not google_email:
            missing.append("google_email")
        if not spreadsheet_id:
            missing.append("spreadsheet_id")
        return validation_error(missing)

    # Optional: profile_id when refreshing Outlook credentials for an existing profile
    profile_id = data.get("profile_id")

    # Embed the pending profile data + user id into the OAuth state token
    state_payload = {
        "owner_user_id": current_user_id,
        "name": name,
        "google_email": google_email,
        "spreadsheet_id": spreadsheet_id,
        "techstack": techstack,
        "email_provider": email_provider,
    }
    if profile_id:
        state_payload["profile_id"] = profile_id
    
    state = jwt.encode(
        state_payload,
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    app = _build_microsoft_oauth_app()
    auth_url = app.get_authorization_request_url(
        scopes=Config.MICROSOFT_SCOPES,
        state=state,
        redirect_uri=Config.MICROSOFT_REDIRECT_URI,
    )

    return success_response({"auth_url": auth_url})


@profile_bp.get("/outlook/callback")
def outlook_callback():
    """
    Microsoft/Outlook OAuth callback.
    - Exchanges code for tokens
    - Verifies Outlook inbox access
    - Creates a profile with attached Outlook credentials.
    Note: Spreadsheet access still requires Google credentials (separate OAuth flow).
    """
    error = request.args.get("error")
    if error:
        return error_response(f"Microsoft OAuth error: {error}")

    code = request.args.get("code")
    state = request.args.get("state")
    if not code or not state:
        return error_response("Missing code or state")

    try:
        state_payload = jwt.decode(
            state,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
    except Exception:
        return error_response("Invalid state parameter")

    app = _build_microsoft_oauth_app()
    result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=Config.MICROSOFT_SCOPES,
        redirect_uri=Config.MICROSOFT_REDIRECT_URI,
    )

    if "error" in result:
        return error_response(f"Microsoft OAuth token error: {result.get('error_description', result.get('error'))}")

    access_token = result.get("access_token")
    if not access_token:
        return error_response("Failed to obtain access token from Microsoft")

    # Verify Outlook access: get the user's email address
    try:
        email_address = get_outlook_user_email(access_token)
    except Exception as exc:  # noqa: BLE001
        return error_response(f"Failed to get Outlook email address: {exc}")

    expected_email = state_payload.get("google_email")
    if expected_email and email_address and email_address.lower() != expected_email.lower():
        return error_response(
            "Authenticated Microsoft account does not match requested email",
            details={"expected_email": expected_email, "actual_email": email_address}
        )

    # Persist credentials with the new profile
    outlook_credentials = {
        "access_token": access_token,
        "refresh_token": result.get("refresh_token"),
        "id_token": result.get("id_token"),
        "expires_in": result.get("expires_in"),
        "token_type": result.get("token_type", "Bearer"),
    }

    profile_id = create_or_update_profile_from_oauth_state(
        state_payload=state_payload,
        outlook_credentials=outlook_credentials,
    )

    # Redirect back to the frontend profile page with a success flag
    frontend_base = current_app.config.get("FRONTEND_BASE_URL", "http://localhost:5173")
    frontend_url = frontend_base.rstrip("/") + "/profile"
    return redirect(f"{frontend_url}?outlook_connected=1&profile_id={profile_id}")




@profile_bp.get("/<profile_id>/sheets")
@require_auth
def list_sheets(current_user_id: str, profile_id: str):
    """List sheets (tabs) available in the profile's spreadsheet."""
    profile = get_profile_with_credentials(current_user_id, profile_id)
    if not profile:
        return error_response("Profile not found", 404)

    spreadsheet_id = profile.get("spreadsheet_id")
    if not spreadsheet_id:
        return error_response("Profile is missing spreadsheet_id", 400)

    email_provider = profile.get("email_provider", "gmail")

    # For Gmail profiles, use OAuth credentials; for Outlook-only profiles, fall back to API key
    try:
        if email_provider == "outlook" and not profile.get("google_credentials"):
            api_key = current_app.config.get("GOOGLE_SHEETS_API_KEY", "")
            service = build_sheets_service_with_api_key(api_key)
        else:
            creds = build_google_credentials(profile)
            service = build_sheets_service(creds)
    except ValueError as exc:
        return error_response(str(exc))
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

    return success_response({"sheets": result})


@profile_bp.get("/<profile_id>/sheets/<int:sheet_id>")
@require_auth
def get_sheet_values(current_user_id: str, profile_id: str, sheet_id: int):
    """Return values from columns A-G of the given sheet."""
    profile = get_profile_with_credentials(current_user_id, profile_id)
    if not profile:
        return error_response("Profile not found", 404)

    spreadsheet_id = profile.get("spreadsheet_id")
    if not spreadsheet_id:
        return error_response("Profile is missing spreadsheet_id", 400)

    email_provider = profile.get("email_provider", "gmail")

    # For Gmail profiles, use OAuth credentials; for Outlook-only profiles, fall back to API key
    try:
        if email_provider == "outlook" and not profile.get("google_credentials"):
            api_key = current_app.config.get("GOOGLE_SHEETS_API_KEY", "")
            service = build_sheets_service_with_api_key(api_key)
        else:
            creds = build_google_credentials(profile)
            service = build_sheets_service(creds)
    except ValueError as exc:
        return error_response(str(exc))
    
    title = get_sheet_title(service, spreadsheet_id, sheet_id)
    if not title:
        return error_response("Sheet not found", 404)

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
        return success_response(
            {
                "sheet_id": sheet_id,
                "title": title,
                "headers": [],
                "rows": [],
            }
        )

    # Find the header row
    header_row_idx = find_header_row(values, min_matches=2)
    raw_headers = values[header_row_idx]
    data_rows = values[header_row_idx + 1:]

    # Only look at columns A–G (0–6)
    headers = (raw_headers + [""] * 7)[:7]

    # Parse column indices
    column_indices = parse_sheet_columns(headers)
    company_idx = column_indices["company_idx"]
    position_idx = column_indices["position_idx"]
    job_url_idx = column_indices["job_url_idx"]

    # Load any cached application statuses for this sheet (keyed by original row index)
    status_map = get_application_statuses_for_sheet(
        owner_user_id=current_user_id,
        profile_id=profile_id,
        spreadsheet_id=spreadsheet_id,
        sheet_id=sheet_id,
    )

    rows: list[list[str]] = []
    statuses: list[str | None] = []
    for idx, row in enumerate(data_rows):
        padded = (row + [""] * 7)[:7]
        company = padded[company_idx]
        position = padded[position_idx]
        job_url = padded[job_url_idx]

        # Ignore rows that don't have required fields
        if not company or not position or not job_url:
            continue

        rows.append(padded)
        statuses.append(status_map.get(idx))

    return success_response(
        {
            "sheet_id": sheet_id,
            "title": title,
            "headers": headers,
            "rows": rows,
            "statuses": statuses,
        }
    )


@profile_bp.post("/<profile_id>/email/check-application")
@require_auth
def check_email_application(current_user_id: str, profile_id: str):
    """
    Check if a position appears to be applied based on email messages (Gmail or Outlook) for the profile's account.

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
        missing = []
        if not company_name:
            missing.append("company_name")
        if not applied_date:
            missing.append("applied_date")
        if sheet_id is None:
            missing.append("sheet_id")
        if row_index is None:
            missing.append("row_index")
        return validation_error(missing)

    profile = get_profile_with_credentials(current_user_id, profile_id)
    if not profile:
        return error_response("Profile not found", 404)

    email_provider = profile.get("email_provider", "gmail")
    applied = False

    try:
        if email_provider == "outlook":
            access_token = build_outlook_credentials(profile)
            applied = search_outlook_for_company(
                access_token=access_token,
                company=company_name,
                applied_date=applied_date,
                applied_time=applied_time,
            )
        else:  # Default to Gmail
            creds = build_google_credentials(profile)
            applied = search_gmail_for_company(
                creds=creds,
                company=company_name,
                applied_date=applied_date,
                applied_time=applied_time,
            )
    except ValueError as exc:
        return error_response(str(exc))
    except Exception as exc:  # noqa: BLE001
        provider_name = "Outlook" if email_provider == "outlook" else "Gmail"
        return error_response(f"Failed to query {provider_name}: {exc}", 500)

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

    return success_response({"applied": applied})


# Keep the old route for backward compatibility
@profile_bp.post("/<profile_id>/gmail/check-application")
@require_auth
def check_gmail_application(current_user_id: str, profile_id: str):
    """Legacy route - redirects to email/check-application."""
    return check_email_application(current_user_id, profile_id)


@profile_bp.post("/<profile_id>/sheets/<int:sheet_id>/gmail/check-all")
@require_auth
def check_gmail_applications_for_sheet(current_user_id: str, profile_id: str, sheet_id: int):
    """
    Recalculate application status for all rows in a sheet.
    Ignores any cached statuses and overwrites them.
    Returns: { job_id: str } - use this to poll for status
    """
    profile = get_profile_with_credentials(current_user_id, profile_id)
    if not profile:
        return error_response("Profile not found", 404)

    spreadsheet_id = profile.get("spreadsheet_id")
    # Preprocessing: synchronously clear all previous statuses for this sheet
    clear_application_statuses_for_sheet(
        owner_user_id=current_user_id,
        profile_id=profile_id,
        spreadsheet_id=spreadsheet_id,
        sheet_id=sheet_id,
    )

    job_id = str(uuid.uuid4())
    create_job(job_id, current_user_id, profile_id)

    def _worker():
        email_provider = profile.get("email_provider", "gmail")
        
        # Build email credentials based on provider
        if email_provider == "outlook":
            try:
                access_token = build_outlook_credentials(profile)
            except ValueError as exc:
                fail_job(job_id, str(exc))
                return
            creds = None  # Not used for Outlook
        else:
            try:
                creds = build_google_credentials(profile)
            except ValueError as exc:
                fail_job(job_id, str(exc))
                return
            access_token = None  # Not used for Gmail
        
        # Sheets service: use Google OAuth when available; for Outlook-only profiles, fall back to API key
        try:
            if email_provider == "outlook" and not profile.get("google_credentials"):
                api_key = current_app.config.get("GOOGLE_SHEETS_API_KEY", "")
                service = build_sheets_service_with_api_key(api_key)
            else:
                google_creds = build_google_credentials(profile)
                service = build_sheets_service(google_creds)
        except ValueError as exc:
            fail_job(job_id, str(exc))
            return

        # Fetch sheet title
        title = get_sheet_title(service, spreadsheet_id, sheet_id)
        if not title:
            fail_job(job_id, "Sheet not found")
            return

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
            complete_job(job_id, [], 0, 0)
            return

        # Find the header row
        header_row_idx = find_header_row(values, min_matches=3)
        headers = (values[header_row_idx] + [""] * 7)[:7]
        data_rows = values[header_row_idx + 1:]

        # Parse column indices
        column_indices = parse_sheet_columns(headers)
        company_idx = column_indices["company_idx"]
        date_idx = column_indices["date_idx"]
        position_idx = column_indices["position_idx"]
        job_url_idx = column_indices["job_url_idx"]

        # Only allocate statuses array for the rows we'll actually process
        # This reduces memory usage for large sheets
        statuses: list[str | None] = [None] * len(data_rows)

        # Track seen URLs so duplicate postings can be marked without re-checking email
        from threading import Lock

        seen_urls: dict[str, int] = {}
        seen_urls_lock = Lock()
        
        # Clear large data structures after processing to help GC
        def cleanup_after_processing():
            nonlocal values, data_rows, headers
            values = None
            data_rows = None
            headers = None

        def process_row(idx: int, padded_row: list[str]) -> tuple[int, str | None]:
            company = padded_row[company_idx]
            applied_date = padded_row[date_idx]
            position = padded_row[position_idx]
            job_url = padded_row[job_url_idx]

            # Skip rows missing any required field
            if not company or not applied_date or not position or not job_url:
                update_job_progress(job_id, idx, None)
                return idx, None

            # If this URL has already been processed for this job, mark as duplicate
            with seen_urls_lock:
                if job_url in seen_urls:
                    status_str = "duplicate"
                    # Mark duplicate in DB and job progress, no email call needed
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
                    update_job_progress(job_id, idx, status_str)
                    return idx, status_str
                # First time we've seen this URL; remember it
                seen_urls[job_url] = idx

            try:
                if email_provider == "outlook":
                    applied = search_outlook_for_company(
                        access_token=access_token,
                        company=company,
                        applied_date=applied_date,
                        applied_time=None,
                    )
                else:
                    applied = search_gmail_for_company(
                        creds=creds,
                        company=company,
                        applied_date=applied_date,
                        applied_time=None,
                    )
            except Exception:
                update_job_progress(job_id, idx, None)
                return idx, None

            status_str = "applied" if applied else "not_applied"

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

            update_job_progress(job_id, idx, status_str)
            return idx, status_str

        with ThreadPoolExecutor(max_workers=4) as executor:
            future_map = {
                executor.submit(process_row, idx, (row + [""] * 7)[:7]): idx
                for idx, row in enumerate(data_rows)
            }

            for future in as_completed(future_map):
                idx, status = future.result()
                statuses[idx] = status

        applied_count = sum(1 for s in statuses if s == "applied")
        duplicate_count = sum(1 for s in statuses if s == "duplicate")
        not_applied_count = sum(1 for s in statuses if s == "not_applied")

        complete_job(job_id, statuses, applied_count, not_applied_count, duplicate_count)
        
        # Cleanup large data structures
        cleanup_after_processing()
        seen_urls.clear()

    # Start background thread
    thread = Thread(target=_worker, daemon=True)
    thread.start()

    return success_response({"job_id": job_id}, 202)


@profile_bp.post("/<profile_id>/sheets/<int:sheet_id>/gmail/check-batch")
@require_auth
def check_gmail_applications_for_range(current_user_id: str, profile_id: str, sheet_id: int):
    """
    Recalculate application status for a range of rows in a sheet.
    Ignores any cached statuses and overwrites them for the specified range.
    Body: { start_row: int, end_row: int } (0-based indices)
    Returns: { job_id: str } - use this to poll for status
    """
    data = request.get_json(silent=True) or {}
    start_row = data.get("start_row")
    end_row = data.get("end_row")

    if start_row is None or end_row is None:
        missing = []
        if start_row is None:
            missing.append("start_row")
        if end_row is None:
            missing.append("end_row")
        return validation_error(missing)

    if not isinstance(start_row, int) or not isinstance(end_row, int):
        return error_response("start_row and end_row must be integers")

    if start_row < 0 or end_row < 0:
        return error_response("start_row and end_row must be non-negative")

    if start_row > end_row:
        return error_response("start_row must be less than or equal to end_row")

    profile = get_profile_with_credentials(current_user_id, profile_id)
    if not profile:
        return error_response("Profile not found", 404)

    spreadsheet_id = profile.get("spreadsheet_id")

    job_id = str(uuid.uuid4())
    create_job(job_id, current_user_id, profile_id)

    def _worker():
        email_provider = profile.get("email_provider", "gmail")
        
        # Build email credentials based on provider
        if email_provider == "outlook":
            try:
                access_token = build_outlook_credentials(profile)
            except ValueError as exc:
                fail_job(job_id, str(exc))
                return
            creds = None  # Not used for Outlook
        else:
            try:
                creds = build_google_credentials(profile)
            except ValueError as exc:
                fail_job(job_id, str(exc))
                return
            access_token = None  # Not used for Gmail
        
        # Sheets service: use Google OAuth when available; for Outlook-only profiles, fall back to API key
        try:
            if email_provider == "outlook" and not profile.get("google_credentials"):
                api_key = current_app.config.get("GOOGLE_SHEETS_API_KEY", "")
                service = build_sheets_service_with_api_key(api_key)
            else:
                google_creds = build_google_credentials(profile)
                service = build_sheets_service(google_creds)
        except ValueError as exc:
            fail_job(job_id, str(exc))
            return

        # Fetch sheet title
        title = get_sheet_title(service, spreadsheet_id, sheet_id)
        if not title:
            fail_job(job_id, "Sheet not found")
            return

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
            complete_job(job_id, [], 0, 0, 0)
            return

        # Find the header row
        header_row_idx = find_header_row(values, min_matches=3)
        headers = (values[header_row_idx] + [""] * 7)[:7]
        data_rows = values[header_row_idx + 1:]

        # Validate range
        total_rows = len(data_rows)
        if start_row >= total_rows:
            fail_job(job_id, f"start_row ({start_row}) is out of range (max: {total_rows - 1})")
            return

        # Clamp end_row to available rows
        end_row_clamped = min(end_row, total_rows - 1)
        if end_row_clamped < start_row:
            fail_job(job_id, "Invalid range: end_row is less than start_row after clamping")
            return

        # Parse column indices
        column_indices = parse_sheet_columns(headers)
        company_idx = column_indices["company_idx"]
        date_idx = column_indices["date_idx"]
        position_idx = column_indices["position_idx"]
        job_url_idx = column_indices["job_url_idx"]

        # Initialize statuses array for the entire sheet (needed for job tracking)
        # But only process the specified range
        statuses: list[str | None] = [None] * total_rows

        # Track seen URLs so duplicate postings can be marked without re-checking email
        from threading import Lock

        seen_urls: dict[str, int] = {}
        seen_urls_lock = Lock()
        
        # Clear large data structures after processing to help GC
        def cleanup_after_processing():
            nonlocal values, data_rows, headers, range_rows
            values = None
            data_rows = None
            headers = None
            range_rows = None

        def process_row(idx: int, padded_row: list[str]) -> tuple[int, str | None]:
            company = padded_row[company_idx]
            applied_date = padded_row[date_idx]
            position = padded_row[position_idx]
            job_url = padded_row[job_url_idx]

            # Skip rows missing any required field
            if not company or not applied_date or not position or not job_url:
                update_job_progress(job_id, idx, None)
                return idx, None

            # If this URL has already been processed for this job, mark as duplicate
            with seen_urls_lock:
                if job_url in seen_urls:
                    status_str = "duplicate"
                    # Mark duplicate in DB and job progress, no email call needed
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
                    update_job_progress(job_id, idx, status_str)
                    return idx, status_str
                # First time we've seen this URL; remember it
                seen_urls[job_url] = idx

            try:
                if email_provider == "outlook":
                    applied = search_outlook_for_company(
                        access_token=access_token,
                        company=company,
                        applied_date=applied_date,
                        applied_time=None,
                    )
                else:
                    applied = search_gmail_for_company(
                        creds=creds,
                        company=company,
                        applied_date=applied_date,
                        applied_time=None,
                    )
            except Exception:
                update_job_progress(job_id, idx, None)
                return idx, None

            status_str = "applied" if applied else "not_applied"

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

            update_job_progress(job_id, idx, status_str)
            return idx, status_str

        # Only process rows in the specified range
        range_rows = data_rows[start_row:end_row_clamped + 1]
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_map = {
                executor.submit(process_row, start_row + idx, (row + [""] * 7)[:7]): start_row + idx
                for idx, row in enumerate(range_rows)
            }

            for future in as_completed(future_map):
                idx, status = future.result()
                statuses[idx] = status

        # Count only the processed range
        range_statuses = statuses[start_row:end_row_clamped + 1]
        applied_count = sum(1 for s in range_statuses if s == "applied")
        duplicate_count = sum(1 for s in range_statuses if s == "duplicate")
        not_applied_count = sum(1 for s in range_statuses if s == "not_applied")

        complete_job(job_id, statuses, applied_count, not_applied_count, duplicate_count)
        
        # Cleanup large data structures
        cleanup_after_processing()
        seen_urls.clear()
        range_statuses = None

    # Start background thread
    thread = Thread(target=_worker, daemon=True)
    thread.start()

    return success_response({"job_id": job_id}, 202)


@profile_bp.get("/<profile_id>/jobs/<job_id>/status")
@require_auth
def get_job_status_route(current_user_id: str, profile_id: str, job_id: str):
    """
    Poll endpoint to check the status of a background job.
    Returns: { status: 'running' | 'completed' | 'error', statuses?: [...], error_message?: str, ... }
    """
    # Verify profile ownership
    profile = get_profile_with_credentials(current_user_id, profile_id)
    if not profile:
        return error_response("Profile not found", 404)

    job_data = get_job_status(job_id)
    if not job_data:
        return error_response("Job not found", 404)

    return success_response(job_data)


