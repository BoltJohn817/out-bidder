from functools import wraps
from typing import Any, Callable, Dict, Tuple

from flask import Request, jsonify, request

from extensions import jwt_manager


def _extract_token(req: Request) -> str | None:
    auth_header = req.headers.get("Authorization")
    if not auth_header:
        return None
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip()


def require_auth(fn: Callable) -> Callable:
    """Decorator to require a valid JWT and inject `current_user_id` into `kwargs`."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        token = _extract_token(request)
        if not token:
            return jsonify({"message": "Missing Authorization header"}), 401

        try:
            payload: Dict[str, Any] = jwt_manager.decode(token)
        except Exception:
            return jsonify({"message": "Invalid or expired token"}), 401

        user_id = payload.get("sub")
        if not user_id:
            return jsonify({"message": "Invalid token payload"}), 401

        kwargs["current_user_id"] = user_id
        return fn(*args, **kwargs)

    return wrapper


def make_auth_token(user_id: str) -> str:
    payload: Dict[str, Any] = {"sub": user_id}
    return jwt_manager.encode(payload)


