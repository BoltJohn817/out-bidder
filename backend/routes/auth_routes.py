from flask import Blueprint, jsonify, request

from auth_utils import make_auth_token, require_auth
from extensions import bcrypt
from models import create_user, find_user_by_user_id
from utils import error_response, success_response, validation_error

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    password = data.get("user_password")

    if not user_id or not password:
        missing = []
        if not user_id:
            missing.append("user_id")
        if not password:
            missing.append("user_password")
        return validation_error(missing)

    existing = find_user_by_user_id(user_id)
    if existing:
        return error_response("User already exists", 409)

    pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    create_user(user_id, pw_hash)

    token = make_auth_token(user_id)
    return success_response({"token": token, "user_id": user_id}, 201)


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    password = data.get("user_password")

    if not user_id or not password:
        missing = []
        if not user_id:
            missing.append("user_id")
        if not password:
            missing.append("user_password")
        return validation_error(missing)

    user = find_user_by_user_id(user_id)
    if not user:
        return error_response("Invalid credentials", 401)

    if not bcrypt.check_password_hash(user["password_hash"], password):
        return error_response("Invalid credentials", 401)

    token = make_auth_token(user_id)
    return success_response({"token": token, "user_id": user_id})


@auth_bp.get("/me")
@require_auth
def me(current_user_id: str):
    return success_response({"user_id": current_user_id})


@auth_bp.post("/logout")
def logout():
    # With stateless JWT, logout is handled client-side by deleting the token.
    return success_response({"message": "Logged out (client should delete token)"})


