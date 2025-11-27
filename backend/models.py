from datetime import datetime
from typing import Any, Dict, List

from bson import ObjectId

from extensions import db


def _now() -> datetime:
    return datetime.utcnow()


def users_collection():
    return db["users"]


def profiles_collection():
    return db["profiles"]


def bids_collection():
    return db["bids"]


def create_user(user_id: str, password_hash: str) -> str:
    doc = {
        "user_id": user_id,
        "password_hash": password_hash,
        "created_at": _now(),
    }
    res = users_collection().insert_one(doc)
    return str(res.inserted_id)


def find_user_by_user_id(user_id: str) -> Dict[str, Any] | None:
    return users_collection().find_one({"user_id": user_id})


def create_profile(
    owner_user_id: str,
    name: str,
    google_email: str,
    spreadsheet_id: str,
    techstack: List[str],
    google_credentials: Dict[str, Any] | None = None,
) -> str:
    doc: Dict[str, Any] = {
        "owner_user_id": owner_user_id,
        "name": name,
        "google_email": google_email,
        "spreadsheet_id": spreadsheet_id,
        "techstack": techstack,
        "created_at": _now(),
    }
    if google_credentials:
        doc["google_credentials"] = google_credentials
    res = profiles_collection().insert_one(doc)
    return str(res.inserted_id)


def list_profiles(owner_user_id: str) -> List[Dict[str, Any]]:
    return list(profiles_collection().find({"owner_user_id": owner_user_id}))


def update_profile(
    owner_user_id: str,
    profile_id: str,
    name: str | None = None,
    google_email: str | None = None,
    spreadsheet_id: str | None = None,
    techstack: List[str] | None = None,
) -> bool:
    """Update basic profile fields for a given owner/profile."""
    update: Dict[str, Any] = {}
    if name is not None:
        update["name"] = name
    if google_email is not None:
        update["google_email"] = google_email
    if spreadsheet_id is not None:
        update["spreadsheet_id"] = spreadsheet_id
    if techstack is not None:
        update["techstack"] = techstack

    if not update:
        return False

    res = profiles_collection().update_one(
        {"_id": ObjectId(profile_id), "owner_user_id": owner_user_id},
        {"$set": update},
    )
    return res.matched_count == 1


def create_or_update_profile_from_oauth_state(
    state_payload: Dict[str, Any],
    google_credentials: Dict[str, Any],
) -> str:
    """
    Helper used by Google OAuth callback to create or update a profile with attached credentials.
    Expects state_payload to contain keys:
    - owner_user_id
    - name, google_email, spreadsheet_id, techstack (for create or update)
    - profile_id (optional: if provided, update that profile instead of creating)
    """
    owner_user_id = state_payload["owner_user_id"]
    name = state_payload["name"]
    google_email = state_payload["google_email"]
    spreadsheet_id = state_payload["spreadsheet_id"]
    techstack = state_payload.get("techstack", [])

    profile_id = state_payload.get("profile_id")

    if profile_id:
        # Update existing profile and replace credentials
        profiles_collection().update_one(
            {"_id": ObjectId(profile_id), "owner_user_id": owner_user_id},
            {
                "$set": {
                    "name": name,
                    "google_email": google_email,
                    "spreadsheet_id": spreadsheet_id,
                    "techstack": techstack,
                    "google_credentials": google_credentials,
                }
            },
        )
        return str(profile_id)

    return create_profile(
        owner_user_id=owner_user_id,
        name=name,
        google_email=google_email,
        spreadsheet_id=spreadsheet_id,
        techstack=techstack,
        google_credentials=google_credentials,
    )


def create_bid(
    owner_user_id: str,
    title: str,
    client: str,
    profile_id: str | None,
    status: str = "draft",
) -> str:
    doc: Dict[str, Any] = {
        "owner_user_id": owner_user_id,
        "title": title,
        "client": client,
        "status": status,
        "created_at": _now(),
    }
    if profile_id:
        doc["profile_id"] = ObjectId(profile_id)
    res = bids_collection().insert_one(doc)
    return str(res.inserted_id)


def list_bids(owner_user_id: str) -> List[Dict[str, Any]]:
    return list(bids_collection().find({"owner_user_id": owner_user_id}))


