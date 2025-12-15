import random
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests


def retry_with_exponential_backoff(max_retries: int = 3, base_delay: int = 1, max_delay: int = 60):
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (requests.RequestException, ConnectionError, TimeoutError, OSError) as e:  # type: ignore[name-defined]
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
def _search_outlook_messages(access_token: str, query: str, start_date: date, end_date: date):
    """
    Search Outlook messages using Microsoft Graph API.
    Note: Graph API $search and $filter cannot be used together.
    We'll use $filter for date range and then filter results in memory for content.
    """
    # Microsoft Graph API messages endpoint
    url = "https://graph.microsoft.com/v1.0/me/messages"
    
    # Build filter query for date range
    # Graph API uses ISO 8601 format: YYYY-MM-DDTHH:mm:ssZ
    start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
    
    # Filter by receivedDateTime (Graph API filter format)
    filter_query = f"receivedDateTime ge {start_datetime.isoformat()} and receivedDateTime le {end_datetime.isoformat()}"
    
    params = {
        "$filter": filter_query,
        "$top": 100,  # Get more results to filter in memory
        "$orderby": "receivedDateTime desc",
        "$select": "id,subject,from,receivedDateTime,bodyPreview"
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("value", [])


@retry_with_exponential_backoff(max_retries=3, base_delay=1, max_delay=30)
def _get_outlook_message(access_token: str, message_id: str):
    """
    Get a specific Outlook message by ID.
    """
    url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


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
    email_datetime_str: str,
    applied_date_str: str,
    applied_time_str: Optional[str] = None,
) -> bool:
    """
    Check if Outlook email datetime is within the applied date/time window.
    
    - If time is provided (HH:MM or HH:MM:SS), check within ±30 minutes.
    - If no time, compare date only with ±3 day tolerance.
    """
    try:
        # Parse Outlook datetime (ISO 8601 format)
        email_dt_utc = datetime.fromisoformat(email_datetime_str.replace("Z", "+00:00"))
        if email_dt_utc.tzinfo is None:
            email_dt_utc = email_dt_utc.replace(tzinfo=timezone.utc)

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


def search_outlook_for_company(
    access_token: str,
    company: str,
    applied_date: str,
    applied_time: Optional[str] = None,
) -> bool:
    """
    Search Outlook for emails related to a company around the applied date.
    
    Returns True if a matching email is found, False otherwise.
    """
    lowered = company.lower()
    
    # Build date window of ±3 days around the applied date
    base_date = _parse_applied_date(applied_date)
    start_date = base_date - timedelta(days=3)
    end_date = base_date + timedelta(days=3)
    
    # Get messages in date range (we'll filter by content in memory)
    messages = _search_outlook_messages(access_token, lowered, start_date, end_date)
    if not messages:
        return False
    
    # Filter messages by checking sender, subject, and body for company name
    for msg in messages:
        sender_email = msg.get("from", {}).get("emailAddress", {}).get("address", "").lower()
        subject = msg.get("subject", "").lower()
        body_preview = msg.get("bodyPreview", "").lower()
        
        # Check if company name appears in sender, subject, or body
        if (lowered in sender_email or 
            lowered in subject or 
            lowered in body_preview):
            
            received_datetime = msg.get("receivedDateTime")
            if not received_datetime:
                continue
            
            if _is_email_within_time_window(received_datetime, applied_date, applied_time):
                return True
    
    return False

