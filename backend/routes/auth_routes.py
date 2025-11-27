from flask import Blueprint, jsonify, request

from auth_utils import make_auth_token, require_auth
from extensions import bcrypt
from models import create_user, find_user_by_user_id

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    password = data.get("user_password")

    if not user_id or not password:
        return jsonify({"message": "user_id and user_password are required"}), 400

    existing = find_user_by_user_id(user_id)
    if existing:
        return jsonify({"message": "User already exists"}), 409

    pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    create_user(user_id, pw_hash)

    token = make_auth_token(user_id)
    return jsonify({"token": token, "user_id": user_id}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    password = data.get("user_password")

    if not user_id or not password:
        return jsonify({"message": "user_id and user_password are required"}), 400

    user = find_user_by_user_id(user_id)
    if not user:
        return jsonify({"message": "Invalid credentials"}), 401

    if not bcrypt.check_password_hash(user["password_hash"], password):
        return jsonify({"message": "Invalid credentials"}), 401

    token = make_auth_token(user_id)
    return jsonify({"token": token, "user_id": user_id}), 200


@auth_bp.get("/me")
@require_auth
def me(current_user_id: str):
    return jsonify({"user_id": current_user_id}), 200


@auth_bp.post("/logout")
def logout():
    # With stateless JWT, logout is handled client-side by deleting the token.
    return jsonify({"message": "Logged out (client should delete token)"}), 200


