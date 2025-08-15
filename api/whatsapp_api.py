from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required

from models import WhatsAppConnection, db
from services.whatsapp_service import WhatsAppService

if TYPE_CHECKING:
    from flask.wrappers import Response


whatsapp_api_bp = Blueprint("whatsapp_api", __name__)
logger = logging.getLogger(__name__)


@whatsapp_api_bp.route("/whatsapp/connect", methods=["POST"])
@jwt_required()
def connect_to_twilio() -> tuple[Response, int]:
    """Establish the connection of a plubot with the configured Twilio number."""
    data: dict[str, Any] | None = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

    plubot_id = data.get("plubotId")
    if not plubot_id:
        return jsonify({"status": "error", "message": "plubotId es requerido"}), 400

    twilio_phone_number = current_app.config.get("TWILIO_PHONE_NUMBER")
    if not twilio_phone_number:
        logger.error("TWILIO_PHONE_NUMBER is not configured on the server.")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "La integración con Twilio no está configurada en el servidor.",
                },
            ),
            500,
        )

    clean_phone_number = twilio_phone_number.replace("whatsapp:", "")

    try:
        connection = db.session.query(WhatsAppConnection).filter_by(plubot_id=plubot_id).first()
        if not connection:
            connection = WhatsAppConnection(plubot_id=plubot_id)
            db.session.add(connection)

        connection.status = "connected"
        connection.whatsapp_number = clean_phone_number
        db.session.commit()

        logger.info(
            "Plubot %s successfully connected to Twilio number %s",
            plubot_id,
            clean_phone_number,
        )
        return jsonify({"status": "success", "message": "Conectado exitosamente a Twilio."}), 200
    except Exception:
        db.session.rollback()
        logger.exception("Error connecting plubot %s to Twilio", plubot_id)
        return jsonify({"status": "error", "message": "Error interno al conectar con Twilio."}), 500


@whatsapp_api_bp.route("/whatsapp/status/<string:plubot_id>", methods=["GET"])
@jwt_required()
def get_status(plubot_id: str) -> tuple[Response, int]:
    """Get the connection status of a plubot."""
    # TODO: Validate ownership of the plubot
    service = WhatsAppService()
    status = service.get_connection_status(plubot_id)
    return jsonify(status), 200


@whatsapp_api_bp.route("/disconnect", methods=["POST"])
@jwt_required()
def disconnect_whatsapp() -> tuple[Response, int]:
    """Disconnect a plubot from WhatsApp."""
    data: dict[str, Any] | None = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

    plubot_id = data.get("plubotId")
    if not plubot_id:
        return jsonify({"status": "error", "message": "plubotId es requerido"}), 400

    # TODO: Validate ownership of the plubot
    service = WhatsAppService()
    response, status_code = service.disconnect_plubot(plubot_id)
    return jsonify(response), status_code


@whatsapp_api_bp.route("/webhook", methods=["POST"])
def whatsapp_webhook() -> tuple[Response, int]:
    """Endpoint to receive webhooks from the WhatsApp API (e.g., Whapi.Cloud).

    These webhooks usually send data in JSON format.
    """
    data = request.get_json()
    service = WhatsAppService()
    service.handle_incoming_message(data)

    # Respond with 200 OK to confirm receipt.
    return jsonify({"status": "received"}), 200
