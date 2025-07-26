import logging
import time

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from config.settings import get_session
from models.message_quota import MessageQuota

quotas_bp = Blueprint("quotas", __name__)
logger = logging.getLogger(__name__)


@quotas_bp.route("", methods=["GET", "OPTIONS"])
@jwt_required()
def get_quota() -> Response:
    """Retrieves the message quota for the current user."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    user_id = get_jwt_identity()
    with get_session() as session:
        current_month = time.strftime("%Y-%m")
        quota = (
            session.query(MessageQuota)
            .filter_by(user_id=user_id, month=current_month)
            .first()
        )
        return jsonify(
            {
                "plan": quota.plan if quota else "free",
                "messages_used": quota.message_count if quota else 0,
                "messages_limit": 100 if (quota and quota.plan == "free") else 999999,
            }
        )
