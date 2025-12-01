"""Utilities for ObjectId conversion."""
from typing import Any
from bson import ObjectId


def convert_objectid_to_str(doc: dict[str, Any]) -> dict[str, Any]:
    """
    Convert ObjectId fields in a document to strings.
    
    Args:
        doc: MongoDB document
    
    Returns:
        Document with ObjectIds converted to strings
    """
    result = doc.copy()
    if "_id" in result:
        result["_id"] = str(result["_id"])
    if "profile_id" in result:
        result["profile_id"] = str(result["profile_id"])
    return result


def convert_objectids_in_list(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert ObjectId fields in a list of documents to strings.
    
    Args:
        docs: List of MongoDB documents
    
    Returns:
        List of documents with ObjectIds converted to strings
    """
    return [convert_objectid_to_str(doc) for doc in docs]


def safe_objectid(profile_id: str) -> ObjectId:
    """
    Safely convert a string to ObjectId, raising ValueError if invalid.
    
    Args:
        profile_id: String representation of ObjectId
    
    Returns:
        ObjectId instance
    
    Raises:
        ValueError: If the string is not a valid ObjectId
    """
    try:
        return ObjectId(profile_id)
    except Exception as e:
        raise ValueError(f"Invalid profile_id: {profile_id}") from e

