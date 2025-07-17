# plubot-backend/api/actions_api.py
import asyncio
import logging
from typing import Any

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from services.discord_action_service import send_discord_message_adhoc

actions_bp = Blueprint("actions_api", __name__, url_prefix="/api/actions")
logger = logging.getLogger(__name__)


@actions_bp.route("/discord/send_message", methods=["POST"])
@jwt_required()
def send_discord_node_message() -> Response:
    """Envía un mensaje a Discord a través de un nodo de acción."""
    user_id = get_jwt_identity()
    data: dict[str, Any] | None = request.json

    if not data:
        return jsonify(error="Payload JSON vacío o inválido."), 400

    bot_token = data.get("token")
    channel_id = data.get("channel_id")
    message_content = data.get("message")

    if not all((bot_token, channel_id, message_content)):
        missing = ", ".join(
            field
            for field in ("token", "channel_id", "message")
            if not data.get(field)
        )
        logger.warning(
            "Usuario %s intentó enviar mensaje con campos faltantes: %s",
            user_id,
            missing,
        )
        return jsonify(error=f"Faltan campos requeridos: {missing}."), 400

    logger.info(
        "Usuario %s enviando mensaje a Discord canal %s", user_id, channel_id
    )

    try:
        success, message = asyncio.run(
            send_discord_message_adhoc(bot_token, channel_id, message_content)
        )

        if success:
            logger.info(
                "Mensaje a Discord enviado por usuario %s al canal %s.",
                user_id,
                channel_id,
            )
            return jsonify(status="success", message=message), 200

        logger.error(
            "Error enviando mensaje a Discord por usuario %s al canal %s: %s",
            user_id,
            channel_id,
            message,
        )
        # Errores de cliente (token, permisos) devuelven 400
        if "Token inválido" in message or "no encontrado" in message:
            return jsonify(status="error", message=message), 400
        return jsonify(status="error", message=message), 500

    except Exception:
        logger.exception(
            "Excepción crítica en send_discord_node_message para usuario %s", user_id
        )
        return jsonify(status="error", message="Error interno del servidor."), 500

# Podrías añadir más endpoints de acciones aquí en el futuro
# ej. @actions_bp.route('/twitter/post_tweet', methods=['POST'])
# @jwt_required()
# def post_twitter_node_action():
#     pass
