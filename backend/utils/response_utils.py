"""Utilities for consistent API responses."""
from flask import jsonify
from typing import Any


def success_response(data: dict[str, Any] | None = None, status_code: int = 200):
    """Create a successful JSON response."""
    if data is None:
        data = {}
    return jsonify(data), status_code


def error_response(message: str, status_code: int = 400, details: Any = None):
    """Create an error JSON response."""
    response = {"message": message}
    if details is not None:
        response["details"] = str(details)
    return jsonify(response), status_code


def validation_error(missing_fields: list[str]):
    """Create a validation error response for missing required fields."""
    return error_response(
        f"Missing required fields: {', '.join(missing_fields)}",
        400
    )

