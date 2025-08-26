from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required
import requests

from models import WhatsAppConnection, db
from services.flow_executor import FlowExecutor
from services.whatsapp_service import WhatsAppService

if TYPE_CHECKING:
    from flask.wrappers import Response


whatsapp_api_bp = Blueprint("whatsapp_api", __name__)
logger = logging.getLogger(__name__)

# WhatsApp microservice URL
WHATSAPP_SERVICE_URL = os.getenv("WHATSAPP_API_URL", "http://localhost:3001")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "internal-api-key")


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


@whatsapp_api_bp.route("/whatsapp/process-message", methods=["POST"])
def process_whatsapp_message() -> tuple[Response, int]:
    """Process incoming WhatsApp message from the Node.js microservice."""
    # Verify API key
    api_key = request.headers.get("X-API-Key")
    if api_key != WHATSAPP_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    try:
        # Extract message data
        session_id = data.get("session_id")
        # user_id = data.get("user_id")  # noqa: ERA001
        plubot_id = data.get("plubot_id")
        from_number = data.get("from_number")
        message_text = data.get("message")

        if not all([session_id, plubot_id, from_number, message_text]):
            return jsonify({"error": "Missing required fields"}), 400

        # Execute flow for the message
        flow_executor = FlowExecutor()
        response = flow_executor.execute_whatsapp_flow(
            plubot_id=plubot_id,
            user_phone=from_number,
            message=message_text,
            session_id=session_id
        )

        return jsonify({
            "reply": response.get("reply", "Lo siento, no pude procesar tu mensaje."),
            "session_data": response.get("session_data", {})
        }), 200

    except Exception:
        logger.exception("Error processing WhatsApp message")
        return jsonify({
            "error": "Internal server error",
            "reply": "Ocurrió un error al procesar tu mensaje. Por favor, intenta nuevamente."
        }), 500


@whatsapp_api_bp.route("/whatsapp/session-status", methods=["POST"])
def update_session_status() -> tuple[Response, int]:
    """Update WhatsApp session status from the Node.js microservice."""
    # Verify API key
    api_key = request.headers.get("X-API-Key")
    if api_key != WHATSAPP_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    try:
        session_id = data.get("session_id")
        status = data.get("status")

        # Parse session_id to get user_id and plubot_id
        parts = session_id.split("-")
        if len(parts) >= 2:
            # user_id = parts[0]  # noqa: ERA001
            plubot_id = "-".join(parts[1:])

            # Update connection status in database
            connection = db.session.query(WhatsAppConnection).filter_by(
                plubot_id=plubot_id
            ).first()

            if connection:
                connection.status = status
                if status == "ready":
                    connection.whatsapp_number = data.get("phone_number")
                db.session.commit()

        logger.info("Session %s status updated to %s", session_id, status)
        return jsonify({"status": "success"}), 200

    except Exception:
        logger.exception("Error updating session status")
        return jsonify({"error": "Internal server error"}), 500


@whatsapp_api_bp.route("/whatsapp/qr/start", methods=["POST"])
@jwt_required()
def start_qr_session() -> tuple[Response, int]:
    """Start a WhatsApp QR session via the Node.js microservice."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    user_id = data.get("userId")
    plubot_id = data.get("plubotId")

    if not user_id or not plubot_id:
        return jsonify({"error": "userId and plubotId are required"}), 400

    try:
        # Call Node.js microservice to create session
        response = requests.post(
            f"{WHATSAPP_SERVICE_URL}/api/sessions/create",
            json={"userId": user_id, "plubotId": plubot_id},
            headers={"X-API-Key": WHATSAPP_API_KEY},
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()

            # Store connection in database
            connection = db.session.query(WhatsAppConnection).filter_by(
                plubot_id=plubot_id
            ).first()

            if not connection:
                connection = WhatsAppConnection(plubot_id=plubot_id)
                db.session.add(connection)

            connection.status = "initializing"
            db.session.commit()

            return jsonify(result), 200
        return jsonify({"error": "Failed to create session"}), response.status_code

    except requests.exceptions.RequestException:
        logger.exception("Error calling WhatsApp microservice")
        return jsonify({"error": "WhatsApp service unavailable"}), 503
    except Exception:
        logger.exception("Error starting QR session")
        return jsonify({"error": "Internal server error"}), 500


@whatsapp_api_bp.route("/whatsapp/qr/status", methods=["GET"])
@jwt_required()
def get_qr_status() -> tuple[Response, int]:
    """Get QR session status from the Node.js microservice."""
    user_id = request.args.get("userId")
    plubot_id = request.args.get("plubotId")

    if not user_id or not plubot_id:
        return jsonify({"error": "userId and plubotId are required"}), 400

    session_id = f"{user_id}-{plubot_id}"

    try:
        # Call Node.js microservice to get status
        response = requests.get(
            f"{WHATSAPP_SERVICE_URL}/api/sessions/{session_id}/status",
            headers={"X-API-Key": WHATSAPP_API_KEY},
            timeout=10
        )

        if response.status_code == 200:
            return jsonify(response.json()), 200
        if response.status_code == 404:
            return jsonify({"error": "Session not found"}), 404
        return jsonify({"error": "Failed to get status"}), response.status_code

    except requests.exceptions.RequestException:
        logger.exception("Error calling WhatsApp microservice")
        return jsonify({"error": "WhatsApp service unavailable"}), 503
    except Exception:
        logger.exception("Error getting QR status")
        return jsonify({"error": "Internal server error"}), 500
