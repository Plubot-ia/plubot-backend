import logging
import re

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from config.settings import get_session
from models.plubot import Plubot
from services.twilio_service import send_whatsapp_message, validate_whatsapp_number

whatsapp_bp = Blueprint("whatsapp", __name__)
logger = logging.getLogger(__name__)


@whatsapp_bp.route("/connect", methods=["POST", "OPTIONS"])
@jwt_required()
def connect_whatsapp() -> tuple[Response, int]:
    """Conecta un número de WhatsApp a un Plubot y envía un mensaje de verificación."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    user_id = get_jwt_identity()
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

    chatbot_id = data.get("chatbot_id")
    phone_number = data.get("phone_number")

    if not chatbot_id or not phone_number:
        return (
            jsonify({"status": "error", "message": "Faltan chatbot_id o phone_number"}),
            400,
        )

    if not re.match(r"^\+\d{10,15}$", phone_number):
        message = "El número debe tener formato internacional, ej. +1234567890"
        return jsonify({"status": "error", "message": message}), 400

    with get_session() as session:
        plubot = (
            session.query(Plubot).filter_by(id=chatbot_id, user_id=user_id).first()
        )
        if not plubot:
            message = "Plubot no encontrado o no tienes permiso"
            return jsonify({"status": "error", "message": message}), 404

        if not validate_whatsapp_number(phone_number):
            message = "El número no está registrado en Twilio. Regístralo primero."
            return jsonify({"status": "error", "message": message}), 400

        verification_body = (
            "¡Hola! Soy Plubot. Responde 'VERIFICAR' para conectar tu plubot. "
            "Si necesitas ayuda, visita https://www.plubot.com/support."
        )
        message_sid = send_whatsapp_message(
            to_number=f"whatsapp:{phone_number}",
            body=verification_body,
        )

        if not message_sid:
            # El error ya fue logueado por la función de servicio
            message = "No se pudo enviar el mensaje de verificación a través de Twilio."
            return jsonify({"status": "error", "message": message}), 500

        logger.info(
            "Mensaje de verificación enviado a %s: %s", phone_number, message_sid
        )
        plubot.whatsapp_number = phone_number
        session.commit()
        success_message = (
            f'Verifica tu número {phone_number} respondiendo "VERIFICAR" en WhatsApp.'
        )
        return jsonify({"status": "success", "message": success_message}), 200
