"""API endpoints para la integración con WhatsApp Business API."""
from datetime import UTC, datetime
import logging

from extensions import db
from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from models.plubot import Plubot
from models.whatsapp_business import WhatsAppBusiness
from services.whatsapp_business_service import WhatsAppBusinessService

logger = logging.getLogger(__name__)

whatsapp_business_bp = Blueprint("whatsapp_business", __name__)

def get_whatsapp_service() -> WhatsAppBusinessService:
    """Obtiene una instancia del servicio de WhatsApp Business."""
    return WhatsAppBusinessService()

@whatsapp_business_bp.route("/wa/status/<int:plubot_id>", methods=["GET"])
@jwt_required()
def get_whatsapp_status(plubot_id: int) -> tuple[Response, int]:
    """Obtiene el estado de conexión de WhatsApp para un Plubot."""
    try:
        user_id = get_jwt_identity()

        # Verificar que el Plubot pertenece al usuario
        plubot = db.session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
        if not plubot:
            return jsonify({"status": "error", "message": "Plubot no encontrado"}), 404

        # Obtener información de WhatsApp Business si existe
        whatsapp = db.session.query(WhatsAppBusiness).filter_by(plubot_id=plubot_id).first()

        if not whatsapp:
            return jsonify({
                "status": "success",
                "data": {
                    "is_active": False,
                    "message": "No hay cuenta de WhatsApp conectada"
                }
            }), 200

        # Verificar si el token sigue siendo válido
        service = get_whatsapp_service()
        is_valid = service.verify_token(whatsapp.access_token) if whatsapp.access_token else False

        return jsonify({
            "status": "success",
            "data": {
                "is_active": whatsapp.is_active and is_valid,
                "phone_number": whatsapp.phone_number,
                "business_name": whatsapp.business_name,
                "waba_id": whatsapp.waba_id
            }
        }), 200

    except Exception:
        logger.exception("Error obteniendo información")
        return jsonify({"status": "error", "message": "Error interno"}), 500

@whatsapp_business_bp.route("/wa/connect/<int:plubot_id>", methods=["POST"])
@jwt_required()
def connect_whatsapp(plubot_id: int) -> tuple[Response, int]:
    """Inicia el proceso de conexión con WhatsApp Business."""
    try:
        user_id = get_jwt_identity()

        # Verificar que el Plubot pertenece al usuario
        plubot = db.session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
        if not plubot:
            return jsonify({"status": "error", "message": "Plubot no encontrado"}), 404

        # Generar URL de OAuth
        service = get_whatsapp_service()
        oauth_url = service.get_oauth_url(plubot_id)

        return jsonify({
            "status": "success",
            "oauth_url": oauth_url
        }), 200

    except Exception:
        logger.exception("Error actualizando información de WhatsApp")
        return jsonify({"status": "error", "message": "Error interno"}), 500

@whatsapp_business_bp.route("/wa/callback", methods=["GET"])
def whatsapp_callback() -> tuple[Response, int]:
    """Callback de OAuth para WhatsApp Business."""
    try:
        code = request.args.get("code")
        state = request.args.get("state")  # plubot_id

        if not code or not state:
            return jsonify({"status": "error", "message": "Parámetros faltantes"}), 400

        service = get_whatsapp_service()
        result = service.exchange_token(code, int(state))

        if result:
            return jsonify({
                "status": "success",
                "message": "WhatsApp conectado exitosamente"
            }), 200
        return jsonify({
            "status": "error",
            "message": "Error al conectar WhatsApp"
        }), 500

    except Exception:
        logger.exception("Error en exchange_token endpoint")
        return jsonify({"status": "error", "message": "Error interno"}), 500


@whatsapp_business_bp.route("/wa/oauth-callback", methods=["POST"])
def oauth_callback() -> tuple[Response, int]:
    """Procesa el callback de OAuth de Facebook/WhatsApp."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data received"}), 400

        code = data.get("code")
        plubot_id = data.get("plubot_id")
        error = data.get("error")

        # Si Facebook devolvió un error
        if error:
            error_description = data.get("error_description", "Unknown error")
            return jsonify({
                "error": f"Facebook OAuth error: {error_description}"
            }), 400

        if not code or not plubot_id:
            return jsonify({"error": "Missing code or plubot_id"}), 400

        logger.info("Webhook recibido: %s", request.method)

        # Intercambiar código por token
        service = WhatsAppBusinessService()
        success = service.exchange_token(code, plubot_id)

        if success:
            logger.info("Verificación recibida: mode=%s, token=%s", "mode", "token")
            return jsonify({"message": "WhatsApp Business connected successfully"}), 200
        logger.error("Fallo al intercambiar token para Plubot %s", plubot_id)
        return jsonify({"error": "Failed to exchange token"}), 500

    except Exception:
        logger.exception("Error enviando mensaje de WhatsApp Business")
        db.session.rollback()
        return jsonify({"error": "Error interno"}), 500

@whatsapp_business_bp.route("/wa/configure/<int:plubot_id>", methods=["POST"])
@jwt_required()
def configure_whatsapp(plubot_id: int) -> tuple[Response, int]:
    """Configura manualmente los IDs de WhatsApp Business."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        # Verificar que el Plubot pertenece al usuario
        plubot = db.session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
        if not plubot:
            return jsonify({"status": "error", "message": "Plubot no encontrado"}), 404

        # Obtener la conexión de WhatsApp
        whatsapp = db.session.query(WhatsAppBusiness).filter_by(plubot_id=plubot_id).first()
        if not whatsapp:
            return jsonify({"status": "error", "message": "No hay conexión de WhatsApp"}), 404

        # Actualizar los campos proporcionados
        if "phone_number_id" in data:
            whatsapp.phone_number_id = data["phone_number_id"]
        if "waba_id" in data:
            whatsapp.waba_id = data["waba_id"]
        if "phone_number" in data:
            whatsapp.phone_number = data["phone_number"]
        if "business_name" in data:
            whatsapp.business_name = data["business_name"]

        whatsapp.updated_at = datetime.now(UTC)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Configuración actualizada exitosamente",
            "data": {
                "phone_number_id": whatsapp.phone_number_id,
                "waba_id": whatsapp.waba_id,
                "phone_number": whatsapp.phone_number,
                "business_name": whatsapp.business_name
            }
        }), 200

    except Exception:
        logger.exception("Error desconectando WhatsApp Business")
        db.session.rollback()
        return jsonify({"status": "error", "message": "Error interno"}), 500

@whatsapp_business_bp.route("/wa/disconnect/<int:plubot_id>", methods=["POST"])
@jwt_required()
def disconnect_whatsapp(plubot_id: int) -> tuple[Response, int]:
    """Desconecta WhatsApp Business de un Plubot."""
    try:
        user_id = get_jwt_identity()

        # Verificar que el Plubot pertenece al usuario
        plubot = db.session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
        if not plubot:
            return jsonify({"status": "error", "message": "Plubot no encontrado"}), 404

        service = get_whatsapp_service()
        if service.disconnect(plubot_id):
            return jsonify({
                "status": "success",
                "message": "WhatsApp desconectado exitosamente"
            }), 200
        return jsonify({
            "status": "error",
            "message": "Error al desconectar WhatsApp"
        }), 500

    except Exception:
        logger.exception("Error desconectando WhatsApp")
        return jsonify({"status": "error", "message": "Error interno"}), 500

@whatsapp_business_bp.route("/wa/send/<int:plubot_id>", methods=["POST"])
@jwt_required()
def send_whatsapp_message(plubot_id: int) -> tuple[Response, int]:
    """Envía un mensaje de WhatsApp."""
    try:
        data = request.get_json()
        to = data.get("to")
        message = data.get("message")

        service = get_whatsapp_service()
        result = service.send_message(plubot_id, to, message)

        if result:
            return jsonify({"status": "success", "message_id": result}), 200
        return jsonify({"status": "error", "message": "Error enviando mensaje"}), 500

    except Exception:
        logger.exception("Error enviando mensaje")
        return jsonify({"status": "error", "message": "Error interno"}), 500

@whatsapp_business_bp.route("/wa/webhook", methods=["GET", "POST"])
def whatsapp_webhook() -> tuple[Response, int]:
    """Webhook para recibir mensajes de WhatsApp."""
    # Verificación del webhook (GET)
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        service = get_whatsapp_service()
        verified_challenge = service.verify_webhook(mode, token, challenge)

        if verified_challenge:
            return verified_challenge, 200

        return jsonify({"status": "error"}), 403

    # Recepción de mensajes (POST)
    try:
        data = request.get_json()

        if not data:
            return jsonify({"status": "error"}), 400

        service = get_whatsapp_service()
        service.process_webhook(data)

        return jsonify({"status": "success"}), 200

    except Exception:
        logger.exception("Error procesando webhook de WhatsApp")
        return jsonify({"status": "error"}), 500
