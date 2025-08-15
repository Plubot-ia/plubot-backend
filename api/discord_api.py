# plubot-backend/api/discord_api.py
import logging

from flask import Blueprint, Response, jsonify, request

from models import User, db

logger = logging.getLogger(__name__)

discord_bp = Blueprint("discord_api", __name__, url_prefix="/api/discord")


@discord_bp.route("/status", methods=["GET"])
def get_discord_api_status() -> Response:
    """Endpoint para que el bot de Discord verifique la salud de esta API."""
    logger.info("Solicitud de estado recibida desde el bot de Discord.")
    return jsonify(
        message="API de Discord para Plubot operativa.",
        backend_status="ok",
    ), 200


@discord_bp.route("/user_xp", methods=["POST"])
def update_user_xp() -> Response:
    """Actualiza el XP de un usuario basado en su actividad en Discord."""
    data = request.json
    if not data:
        return jsonify(error="Payload JSON vacío o inválido."), 400

    discord_user_id = data.get("discord_user_id")
    discord_username = data.get("discord_username")
    xp_to_add = data.get("xp_to_add")

    if not all([discord_user_id, isinstance(xp_to_add, int)]):
        logger.warning(
            "Intento de actualizar XP con datos inválidos: %s", data
        )
        return jsonify(
            error="Faltan 'discord_user_id' o 'xp_to_add' (debe ser int)."
        ), 400

    logger.info(
        "Solicitud para actualizar %s XP para Discord ID: %s (%s)",
        xp_to_add,
        discord_user_id,
        discord_username,
    )

    try:
        user = User.query.filter_by(discord_id=discord_user_id).first()

        new_user_created = False
        if not user:
            logger.info(
                "Usuario con Discord ID %s no encontrado. Creando nuevo usuario.",
                discord_user_id,
            )
            # CRITICAL: La creación de usuarios es un placeholder.
            # Se necesita una estrategia robusta para manejar emails y contraseñas.
            user = User(
                discord_id=discord_user_id,
                discord_username=discord_username,
                email=f"{discord_user_id}@discord.placeholder.com",
                password="!DiscordUserPlaceholderPassword!",  # noqa: S106
                name=discord_username,
                plucoins=0,
                level=1,
            )
            db.session.add(user)
            new_user_created = True

        user.plucoins = (user.plucoins or 0) + xp_to_add

        # Lógica de Niveles (ejemplo simplificado)
        current_level = user.level or 1
        xp_for_next_level = current_level * 100
        new_level_achieved = None

        while user.plucoins >= xp_for_next_level:
            user.level += 1
            new_level_achieved = user.level
            xp_for_next_level = user.level * 100

        db.session.commit()

        logger.info(
            "Usuario %s (ID: %s, DiscordID: %s) actualizado. Plucoins: %s, Nivel: %s",
            user.discord_username,
            user.id,
            user.discord_id,
            user.plucoins,
            user.level,
        )

        response_message = f"XP actualizado para {user.discord_username}."
        if new_user_created:
            response_message = (
                f"Perfil de Plubot creado para {user.discord_username} y XP actualizado."
            )
        if new_level_achieved:
            response_message += (
                f" ¡Felicidades, has alcanzado el Nivel {new_level_achieved}!"
            )

        return jsonify(
            message=response_message,
            discord_user_id=user.discord_id,
            plubot_user_id=user.id,
            xp_added=xp_to_add,
            new_xp_total=user.plucoins,
            current_level=user.level,
            new_level_achieved=new_level_achieved,
        ), 200

    except Exception:
        db.session.rollback()
        logger.exception(
            "Error al actualizar XP para el usuario con Discord ID: %s", discord_user_id
        )
        return jsonify(error="Error interno al procesar la actualización de XP."), 500
