import logging

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import current_user, jwt_required
import requests

from models import db
from models.discord_integration import DiscordIntegration
from utils.security import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

discord_integrations_bp = Blueprint(
    "discord_integrations_bp", __name__, url_prefix="/api/discord-integrations"
)


def _verify_discord_token(integration: DiscordIntegration) -> None:
    """Verifies the Discord bot token by making a request to the Discord API."""
    if not integration or not integration.bot_token_encrypted:
        logger.warning(
            (
                "_verify_discord_token: Attempted to verify an integration without a token"
                " or invalid integration object. ID: %s"
            ),
            integration.id if integration else "N/A",
        )
        return

    try:
        decrypted_token = decrypt_token(integration.bot_token_encrypted)
    except Exception:
        logger.exception(
            "_verify_discord_token: Failed to decrypt token for integration ID %s.",
            integration.id,
        )
        integration.status = "verification_error"
        integration.last_error_message = "Failed to decrypt token."
        db.session.commit()
        return

    headers = {"Authorization": f"Bot {decrypted_token}"}
    verify_url = "https://discord.com/api/v10/users/@me"

    try:
        response = requests.get(verify_url, headers=headers, timeout=10)
        if response.status_code == 200:
            integration.status = "active"
            integration.last_error_message = None
            logger.info(
                "_verify_discord_token: Token for integration ID %s verified successfully.",
                integration.id,
            )
        elif response.status_code == 401:
            integration.status = "invalid_token"
            integration.last_error_message = "Token is invalid or unauthorized."
            logger.warning(
                "_verify_discord_token: Token for integration ID %s is invalid (401).",
                integration.id,
            )
        else:
            integration.status = "verification_error"
            integration.last_error_message = (
                f"Discord API returned status {response.status_code}"
            )
            logger.error(
                (
                "_verify_discord_token: Discord API error for integration ID %s. "
                "Status: %s, Response: %s"
            ),
                integration.id,
                response.status_code,
                response.text[:200],
            )
    except requests.exceptions.Timeout:
        integration.status = "verification_error"
        integration.last_error_message = "Verification timed out."
        logger.exception(
            "_verify_discord_token: Timeout while verifying token for integration ID %s.",
            integration.id,
        )
    except requests.exceptions.RequestException:
        integration.status = "verification_error"
        integration.last_error_message = "Network error during verification."
        logger.exception(
            "_verify_discord_token: Network error for integration ID %s.", integration.id
        )
    except Exception:
        integration.status = "verification_error"
        integration.last_error_message = (
            "An unexpected error occurred during verification."
        )
        logger.exception(
            "_verify_discord_token: Unexpected error for integration ID %s.",
            integration.id,
        )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "_verify_discord_token: Failed to commit status update for integration ID %s.",
            integration.id,
        )


@discord_integrations_bp.route("/", methods=["POST"])
@jwt_required()
def create_discord_integration() -> Response:
    """Crea una nueva integración de Discord para el usuario autenticado."""
    data = request.json
    if not data:
        return jsonify(error="Payload JSON vacío o inválido."), 400

    integration_name = data.get("integration_name")
    bot_token = data.get("bot_token")

    if not integration_name or not bot_token:
        return jsonify(error="integration_name y bot_token son requeridos."), 400

    try:
        user_id = current_user.id if hasattr(current_user, "id") else current_user
        encrypted_token = encrypt_token(bot_token)

        new_integration = DiscordIntegration(
            user_id=user_id,
            integration_name=integration_name,
            bot_token_encrypted=encrypted_token,
            guild_id=data.get("guild_id"),
            default_channel_id=data.get("default_channel_id"),
            status="pending_verification",
        )

        db.session.add(new_integration)
        db.session.commit()

        _verify_discord_token(new_integration)

        logger.info(
            "Nueva integración de Discord creada con ID: %s para el usuario ID: %s",
            new_integration.id,
            user_id,
        )

        return (
            jsonify(
                {
                    "message": (
                        "Integración de Discord creada exitosamente. "
                        "La verificación del token está en proceso."
                    ),
                    "id": new_integration.id,
                    "status": new_integration.status,
                }
            ),
            201,
        )

    except Exception:
        db.session.rollback()
        logger.exception("Error al crear la integración de Discord.")
        return jsonify(error="Error interno del servidor al crear la integración."), 500


@discord_integrations_bp.route("/", methods=["GET"])
@jwt_required()
def get_discord_integrations() -> Response:
    """Obtiene todas las integraciones de Discord para el usuario autenticado."""
    try:
        user_id = current_user.id if hasattr(current_user, "id") else current_user
        integrations = DiscordIntegration.query.filter_by(user_id=user_id).all()

        return jsonify([integration.to_dict() for integration in integrations]), 200
    except Exception:
        logger.exception("Error al obtener las integraciones de Discord.")
        return jsonify(error="Error interno del servidor."), 500


@discord_integrations_bp.route("/<int:integration_id>", methods=["GET"])
@jwt_required()
def get_discord_integration_detail(integration_id: int) -> Response:
    """Obtiene los detalles de una integración de Discord específica por su ID."""
    try:
        user_id = current_user.id if hasattr(current_user, "id") else current_user
        integration = DiscordIntegration.query.filter_by(
            id=integration_id, user_id=user_id
        ).first()

        if not integration:
            return (
                jsonify(
                    error="Integración de Discord no encontrada o no pertenece al usuario."
                ),
                404,
            )

        return jsonify(integration.to_dict()), 200
    except Exception:
        logger.exception(
            "Error al obtener detalles de la integración de Discord %s.", integration_id
        )
        return (
            jsonify(
                error="Error interno del servidor al obtener detalles de la integración."
            ),
            500,
        )


@discord_integrations_bp.route("/<int:integration_id>", methods=["PUT"])
@jwt_required()
def update_discord_integration(integration_id: int) -> Response:
    """Actualiza una integración de Discord existente."""
    data = request.json
    if not data:
        return jsonify(error="Payload JSON vacío o inválido."), 400

    try:
        user_id = current_user.id if hasattr(current_user, "id") else current_user
        integration = DiscordIntegration.query.filter_by(
            id=integration_id, user_id=user_id
        ).first()

        if not integration:
            return (
                jsonify(
                    error="Integración de Discord no encontrada o no pertenece al usuario."
                ),
                404,
            )

        if "integration_name" in data:
            integration.integration_name = data["integration_name"]
        if data.get("bot_token"):
            try:
                integration.bot_token_encrypted = encrypt_token(data["bot_token"])
            except Exception:
                logger.exception(
                    "Error al cifrar el token durante la actualización para la integración %s.",
                    integration_id,
                )
                return (
                    jsonify(
                        error="Error de configuración del servidor al procesar el token."
                    ),
                    500,
                )
        if "guild_id" in data:
            integration.guild_id = data["guild_id"]
        if "default_channel_id" in data:
            integration.default_channel_id = data["default_channel_id"]

        token_updated = "bot_token" in data and data["bot_token"]

        db.session.commit()

        if token_updated:
            logger.info(
                "Token actualizado para la integración de Discord ID: %s. Iniciando verificación.",
                integration_id,
            )
            _verify_discord_token(integration)
        logger.info(
            "Integración de Discord ID: %s actualizada para el usuario ID: %s",
            integration_id,
            user_id,
        )

        return (
            jsonify(
                {
                    "message": "Integración de Discord actualizada exitosamente.",
                    "id": integration.id,
                    "integration_name": integration.integration_name,
                    "guild_id": integration.guild_id,
                    "default_channel_id": integration.default_channel_id,
                    "status": integration.status,
                    "updated_at": integration.updated_at.isoformat(),
                }
            ),
            200,
        )

    except Exception:
        db.session.rollback()
        logger.exception(
            "Error al actualizar la integración de Discord %s.", integration_id
        )
        return (
            jsonify(error="Error interno del servidor al actualizar la integración."),
            500,
        )


@discord_integrations_bp.route("/<int:integration_id>", methods=["DELETE"])
@jwt_required()
def delete_discord_integration(integration_id: int) -> Response:
    """Elimina una integración de Discord existente."""
    try:
        user_id = current_user.id if hasattr(current_user, "id") else current_user
        integration = DiscordIntegration.query.filter_by(
            id=integration_id, user_id=user_id
        ).first()

        if not integration:
            return (
                jsonify(
                    error="Integración de Discord no encontrada o no pertenece al usuario."
                ),
                404,
            )

        db.session.delete(integration)
        db.session.commit()
        logger.info(
            "Integración de Discord ID: %s eliminada para el usuario ID: %s",
            integration_id,
            user_id,
        )

        return jsonify(message="Integración de Discord eliminada exitosamente."), 200

    except Exception:
        db.session.rollback()
        logger.exception(
            "Error al eliminar la integración de Discord %s.", integration_id
        )
        return (
            jsonify(error="Error interno del servidor al eliminar la integración."),
            500,
        )
