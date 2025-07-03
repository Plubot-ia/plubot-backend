import logging
from typing import Any

from flask import Blueprint, Response, jsonify, request
from twilio.twiml.messaging_response import MessagingResponse

from config.settings import get_session
from models.conversation import Conversation
from models.flow import Flow
from models.plubot import Plubot
from services.grok_service import call_grok
from services.twilio_service import send_whatsapp_message
from utils.helpers import check_quota, increment_quota, summarize_history

webhook_bp = Blueprint("webhook", __name__)
logger = logging.getLogger(__name__)


def _build_system_prompt(plubot: Plubot) -> str:
    """Construye el prompt del sistema para el modelo de IA."""
    prompt = (
        f"Eres un plubot {plubot.tone} llamado '{plubot.name}'. "
        f"Tu propósito es {plubot.purpose}."
    )
    if plubot.business_info:
        prompt += f"\nNegocio: {plubot.business_info}"
    if plubot.pdf_content:
        prompt += f"\nContenido del PDF: {plubot.pdf_content}"
    return prompt


@webhook_bp.route("/<int:chatbot_id>", methods=["POST"])
def webhook(chatbot_id: int) -> Response:
    """Maneja los webhooks de Twilio para los mensajes de WhatsApp entrantes."""
    data = request.form.to_dict()
    from_number = data.get("From", "")
    user_message = data.get("Body", "").strip()

    if not from_number or not user_message:
        logger.warning("Mensaje o número de origen no proporcionado")
        return jsonify({"status": "error", "message": "Falta el número o el mensaje"}), 400

    with get_session() as session:
        plubot = session.query(Plubot).filter_by(id=chatbot_id).first()
        if not plubot:
            logger.warning("Plubot %s no encontrado", chatbot_id)
            return jsonify({"status": "error", "message": "Plubot no encontrado"}), 404

        if not plubot.whatsapp_number:
            logger.warning("Plubot %s no tiene número de WhatsApp configurado", chatbot_id)
            return Response(status=404)

        if plubot.whatsapp_number != from_number.replace("whatsapp:", ""):
            logger.warning("Número no coincide: %s", from_number)
            return jsonify({"status": "error", "message": "Número de WhatsApp no coincide"}), 403

        user_id = from_number

        if user_message.lower() == "verificar":
            plubot.is_verified = True
            session.commit()
            send_whatsapp_message(
                to_number=from_number,
                body="¡Número verificado! Tu plubot está listo para usar.",
            )
            return jsonify({"status": "success", "message": "Verificado"}), 200

        if not check_quota(plubot.user_id, session):
            twilio_response = MessagingResponse()
            message = (
                "Has alcanzado el límite de mensajes de este mes. "
                "Actualiza tu plan para continuar."
            )
            twilio_response.message(message)
            return Response(str(twilio_response), mimetype="text/xml")

        increment_quota(plubot.user_id, session)

        conversation = Conversation(
            chatbot_id=chatbot_id, user_id=user_id, message=user_message, role="user"
        )
        session.add(conversation)
        session.commit()

        history_query = session.query(Conversation).filter_by(
            chatbot_id=chatbot_id, user_id=user_id
        )
        history = history_query.order_by(Conversation.timestamp.asc()).all()
        flows = (
            session.query(Flow)
            .filter_by(chatbot_id=chatbot_id)
            .order_by(Flow.position.asc())
            .all()
        )

        user_msg_lower = user_message.lower()
        response_text = None
        for flow in flows:
            if user_msg_lower == flow.user_message.lower():
                response_text = flow.bot_response
                break

        if not response_text:
            system_prompt = _build_system_prompt(plubot)
            user_prompt = (
                f"Historial: {summarize_history(history)}\nMensaje: {user_message}"
            )
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            response_text = call_grok(messages, max_tokens=150)

        bot_conversation = Conversation(
            chatbot_id=chatbot_id, user_id=user_id, message=response_text, role="bot"
        )
        session.add(bot_conversation)
        session.commit()

        twilio_response = MessagingResponse()
        twilio_response.message(response_text)
        return Response(str(twilio_response), mimetype="text/xml")
