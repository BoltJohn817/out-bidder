import random
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials


def retry_with_exponential_backoff(max_retries: int = 3, base_delay: int = 1, max_delay: int = 60):
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (HttpError, ConnectionError, TimeoutError, OSError) as e:  # type: ignore[name-defined]
                    last_exception = e
                    if attempt == max_retries:
                        break
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = random.uniform(0.1, 0.3) * delay
                    total_delay = delay + jitter
                    time.sleep(total_delay)
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


@retry_with_exponential_backoff(max_retries=3, base_delay=1, max_delay=30)
def _search_gmail_messages(service, query: str):
    response = service.users().messages().list(userId="me", q=query).execute()
    return response.get("messages", [])


@retry_with_exponential_backoff(max_retries=3, base_delay=1, max_delay=30)
def _get_gmail_message(service, message_id: str):
    return service.users().messages().get(userId="me", id=message_id, format="metadata").execute()


def _parse_applied_date(date_str: str) -> date:
    """Parse applied date supporting m/d/yyyy and m/d, defaulting year to current."""
    cleaned = date_str.strip()
    # Try m/d/yyyy
    try:
        return datetime.strptime(cleaned, "%m/%d/%Y").date()
    except ValueError:
        pass

    # Try m/d with current year
    try:
        d = datetime.strptime(cleaned, "%m/%d").date()
        return d.replace(year=datetime.now().year)
    except ValueError as exc:  # noqa: BLE001
        raise ValueError(f"Unable to parse applied date: {cleaned}") from exc


def _is_email_within_time_window(
    email_timestamp_ms: str,
    applied_date_str: str,
    applied_time_str: Optional[str] = None,
) -> bool:
    """
    Gmail internalDate (ms since epoch UTC) -> compare with applied date/time.

    - If time is provided (HH:MM or HH:MM:SS), check within ±30 minutes.
    - If no time, compare date only with ±3 day tolerance.
    """
    try:
        # Email datetime in UTC
        email_dt_utc = datetime.fromtimestamp(int(email_timestamp_ms) / 1000, tz=timezone.utc)

        applied_date = _parse_applied_date(applied_date_str)

        if applied_time_str and applied_time_str.strip():
            # Accept either HH:MM or HH:MM:SS
            cleaned = applied_time_str.strip()
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    applied_time = datetime.strptime(cleaned, fmt).time()
                    break
                except ValueError:
                    applied_time = None
            if applied_time is None:
                return False

            applied_dt = datetime.combine(applied_date, applied_time, tzinfo=timezone.utc)
            delta = timedelta(minutes=30)
            return applied_dt - delta <= email_dt_utc <= applied_dt + delta

        # Date-only comparison with ±3 days
        email_date = email_dt_utc.date()
        return abs((email_date - applied_date).days) <= 3
    except Exception:
        return False


def search_gmail_for_company(
    creds: Credentials,
    company: str,
    applied_date: str,
    applied_time: Optional[str] = None,
) -> bool:
    """
    Search Gmail for emails related to a company around the applied date.

    Returns True if a matching email is found, False otherwise.
    """
    service = build("gmail", "v1", credentials=creds)

    lowered = company.lower()
    query = f'from:"{lowered}" OR subject:"{lowered}" OR "{lowered}"'

    # Build inclusive date window of ±3 days around the applied date for Gmail query
    base_date = _parse_applied_date(applied_date)
    start_date = base_date - timedelta(days=3)
    end_date = base_date + timedelta(days=3)
    query += f' after:{start_date.strftime("%Y/%m/%d")} before:{(end_date + timedelta(days=1)).strftime("%Y/%m/%d")}'

    messages = _search_gmail_messages(service, query)
    if not messages:
        return False

    for msg in messages:
        msg_detail = _get_gmail_message(service, msg["id"])
        internal_ms = msg_detail.get("internalDate")
        if not internal_ms:
            continue
        if _is_email_within_time_window(internal_ms, applied_date, applied_time):
            return True

    return False


