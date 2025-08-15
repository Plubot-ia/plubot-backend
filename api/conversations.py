import logging
from typing import Any

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.orm import Session

from config.settings import get_session
from models.conversation import Conversation
from models.flow import Flow
from models.plubot import Plubot
from services.grok_service import call_grok
from utils.helpers import check_quota, increment_quota

conversations_bp = Blueprint("conversations", __name__)
logger = logging.getLogger(__name__)


def _validate_chat_request(data: dict[str, Any]) -> tuple[Response, int] | None:
    """Valida los datos de la solicitud de chat entrante."""
    if not data or not data.get("message") or not data.get("user_phone"):
        return (
            jsonify(
                {"status": "error", "message": "Falta el mensaje o el número de teléfono"}
            ),
            400,
        )
    return None


def _get_and_validate_plubot(
    session: Session, chatbot_id: int
) -> tuple[Plubot, None] | tuple[None, tuple[Response, int]]:
    """Obtiene y valida el Plubot y la cuota del usuario."""
    plubot = session.query(Plubot).filter_by(id=chatbot_id).first()
    if not plubot:
        return None, (jsonify({"status": "error", "message": "Plubot no encontrado"}), 404)
    if not plubot.is_webchat_enabled:
        return None, (
            jsonify(
                {"status": "error", "message": "El webchat no está habilitado para este Plubot"}
            ),
            403,
        )
    if not check_quota(plubot.user_id, session):
        return None, (
            jsonify(
                {"status": "error", "message": "Has alcanzado el límite de mensajes de este mes."}
            ),
            429,
        )
    increment_quota(plubot.user_id, session)
    return plubot, None


def _determine_bot_response(
    session: Session, plubot: Plubot, user_message: str, history: list[Conversation]
) -> str:
    """Determina la respuesta del bot basada en la lógica de negocio."""
    if not history:
        return plubot.initial_message

    user_msg_lower = user_message.lower()
    for option in plubot.menu_options or []:
        if user_msg_lower == option.get("label", "").lower():
            return f"Has seleccionado {option['label']}. ¿Cómo puedo ayudarte con esto?"

    flows = (
        session.query(Flow).filter_by(chatbot_id=plubot.id).order_by(Flow.position.asc()).all()
    )
    for flow in flows:
        if user_msg_lower == flow.user_message.lower():
            return flow.bot_response  # Simplificado para el ejemplo

    system_message = f"Eres un plubot {plubot.tone} llamado '{plubot.name}'."
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]
    return call_grok(messages, max_tokens=150)


@conversations_bp.route("/<int:chatbot_id>/chat", methods=["POST"])
def chat(chatbot_id: int) -> Response:
    """Procesa un mensaje de chat para un Plubot específico."""
    data = request.get_json()
    if (validation_error := _validate_chat_request(data)):
        return validation_error

    user_message = data.get("message")
    user_phone = data.get("user_phone")

    with get_session() as session:
        plubot, error_response = _get_and_validate_plubot(session, chatbot_id)
        if error_response:
            return error_response

        history = (
            session.query(Conversation)
            .filter_by(chatbot_id=chatbot_id, user_id=user_phone)
            .order_by(Conversation.timestamp.asc())
            .all()
        )

        session.add(
            Conversation(
                chatbot_id=chatbot_id, user_id=user_phone, message=user_message, role="user"
            )
        )
        session.commit()

        response = _determine_bot_response(session, plubot, user_message, history)

        session.add(
            Conversation(
                chatbot_id=chatbot_id, user_id=user_phone, message=response, role="bot"
            )
        )

        plubot.message_count += 1
        if not history:
            plubot.conversation_count += 1
        session.commit()

        return jsonify({"response": response, "buttons": plubot.menu_options or []})


@conversations_bp.route("/<int:chatbot_id>/history", methods=["GET", "OPTIONS"])
@jwt_required()
def conversation_history(chatbot_id: int) -> Response:
    """Obtiene el historial de conversación para un Plubot específico."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    user_id = get_jwt_identity()
    with get_session() as session:
        plubot = (
            session.query(Plubot).filter_by(id=chatbot_id, user_id=user_id).first()
        )
        if not plubot:
            return jsonify(
                {"status": "error", "message": "Plubot no encontrado o no tienes permisos"}
            ), 404

        history = (
            session.query(Conversation)
            .filter_by(chatbot_id=chatbot_id)
            .order_by(Conversation.timestamp.asc())
            .all()
        )
        history_list = [
            {
                "role": conv.role,
                "message": conv.message,
                "timestamp": conv.timestamp.isoformat(),
            }
            for conv in history
        ]
        return jsonify({"status": "success", "history": history_list}), 200
