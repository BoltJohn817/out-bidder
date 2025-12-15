"""Utilities for building and managing Microsoft Graph API services."""
from typing import Any

import requests
from msal import ConfidentialClientApplication

from extensions import db


def build_outlook_credentials(profile: dict[str, Any]) -> str:
    """
    Build and refresh Outlook access token from a profile document.
    
    Args:
        profile: Profile document containing outlook_credentials
    
    Returns:
        Access token string
    
    Raises:
        ValueError: If profile doesn't have Outlook credentials
    """
    creds_info = profile.get("outlook_credentials")
    if not creds_info:
        raise ValueError("Profile does not have Outlook credentials")
    
    from config import Config
    
    access_token = creds_info.get("access_token")
    if not access_token:
        raise ValueError("No access token found in Outlook credentials")
    
    # Check if token is expired (simple check - in production, you might want to check expires_in)
    # For now, try to use the existing token. If it fails, we'll need to refresh.
    # In a production system, you'd check the token expiration time.
    
    # Try to refresh using refresh token if available
    refresh_token = creds_info.get("refresh_token")
    if refresh_token:
        try:
            app = ConfidentialClientApplication(
                client_id=Config.MICROSOFT_CLIENT_ID,
                client_credential=Config.MICROSOFT_CLIENT_SECRET,
                authority=Config.MICROSOFT_AUTHORITY,
            )
            
            result = app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=Config.MICROSOFT_SCOPES
            )
            
            if result and "access_token" in result:
                # Update stored credentials if token was refreshed
                profiles_collection = db["profiles"]
                update_data = {
                    "outlook_credentials.access_token": result.get("access_token"),
                }
                if result.get("refresh_token"):
                    update_data["outlook_credentials.refresh_token"] = result.get("refresh_token")
                
                profiles_collection.update_one(
                    {"_id": profile["_id"]},
                    {"$set": update_data}
                )
                return result["access_token"]
        except Exception:
            # If refresh fails, try using the existing token
            pass
    
    # Return existing token (caller will handle if it's expired)
    return access_token


def get_outlook_user_email(access_token: str) -> str:
    """
    Get the user's Outlook email address using Microsoft Graph API.
    
    Args:
        access_token: Microsoft Graph API access token
    
    Returns:
        User's email address
    
    Raises:
        requests.RequestException: If the API request fails
        ValueError: If email address cannot be determined
    """
    url = "https://graph.microsoft.com/v1.0/me"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    
    # Provide more detailed error information
    if response.status_code == 403:
        error_detail = response.json().get("error", {})
        error_message = error_detail.get("message", "Forbidden")
        raise requests.RequestException(
            f"403 Forbidden: {error_message}. "
            "This usually means the app doesn't have 'User.Read' permission, "
            "or the user hasn't consented to it. "
            "Please ensure 'User.Read' is added to API permissions in Azure portal "
            "and the user re-authenticates."
        )
    
    response.raise_for_status()
    data = response.json()
    email = data.get("mail") or data.get("userPrincipalName")
    if not email:
        raise ValueError("Could not determine email address from Microsoft Graph API response")
    return email

