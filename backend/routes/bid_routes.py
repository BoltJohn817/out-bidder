from flask import Blueprint, jsonify, request

from auth_utils import require_auth
from models import create_bid, list_bids

bid_bp = Blueprint("bids", __name__)


@bid_bp.get("/")
@require_auth
def get_bids(current_user_id: str):
    bids = list_bids(current_user_id)
    for b in bids:
        b["_id"] = str(b.get("_id"))
        if "profile_id" in b:
            b["profile_id"] = str(b["profile_id"])
    return jsonify({"bids": bids}), 200


@bid_bp.post("/")
@require_auth
def create_bid_route(current_user_id: str):
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    client = data.get("client")
    profile_id = data.get("profile_id")
    status = data.get("status", "draft")

    if not title or not client:
        return jsonify({"message": "title and client are required"}), 400

    bid_id = create_bid(
        owner_user_id=current_user_id,
        title=title,
        client=client,
        profile_id=profile_id,
        status=status,
    )
    return jsonify({"bid_id": bid_id}), 201


