from flask import Blueprint, jsonify, request

from auth_utils import require_auth
from models import create_bid, list_bids
from utils import convert_objectids_in_list, error_response, success_response, validation_error

bid_bp = Blueprint("bids", __name__)


@bid_bp.get("/")
@require_auth
def get_bids(current_user_id: str):
    bids = list_bids(current_user_id)
    bids = convert_objectids_in_list(bids)
    return success_response({"bids": bids})


@bid_bp.post("/")
@require_auth
def create_bid_route(current_user_id: str):
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    client = data.get("client")
    profile_id = data.get("profile_id")
    status = data.get("status", "draft")

    if not title or not client:
        missing = []
        if not title:
            missing.append("title")
        if not client:
            missing.append("client")
        return validation_error(missing)

    bid_id = create_bid(
        owner_user_id=current_user_id,
        title=title,
        client=client,
        profile_id=profile_id,
        status=status,
    )
    return success_response({"bid_id": bid_id}, 201)


