from flask import Blueprint, jsonify, request, Response
from config.settings import get_session
from models.plubot import Plubot  # Actualizado: importar Plubot desde plubot.py
from models.conversation import Conversation
from models.flow import Flow
from utils.helpers import check_quota, increment_quota, summarize_history
from services.grok_service import call_grok
from services.twilio_service import twilio_client, TWILIO_PHONE
from twilio.twiml.messaging_response import MessagingResponse
import logging

webhook_bp = Blueprint('webhook', __name__)
logger = logging.getLogger(__name__)

@webhook_bp.route('/<int:chatbot_id>', methods=['POST'])
def webhook(chatbot_id):
    data = request.form.to_dict()
    from_number = data.get('From', '')
    user_message = data.get('Body', '').strip()

    if not from_number or not user_message:
        logger.warning("Mensaje o número de origen no proporcionado")
        return jsonify({'status': 'error', 'message': 'Falta el número o el mensaje'}), 400

    with get_session() as session:
        plubot = session.query(Plubot).filter_by(id=chatbot_id).first()  # Actualizado: usar Plubot
        if not plubot:
            logger.warning(f"Plubot {chatbot_id} no encontrado")  # Actualizado: mensaje de log
            return jsonify({'status': 'error', 'message': 'Plubot no encontrado'}), 404

        if not plubot.whatsapp_number:
            logger.warning(f"Plubot {chatbot_id} no tiene número de WhatsApp configurado")  # Actualizado: mensaje de log
            return Response(status=404)

        if plubot.whatsapp_number != from_number.replace('whatsapp:', ''):
            logger.warning(f"Número no coincide: {from_number}")
            return jsonify({'status': 'error', 'message': 'Número de WhatsApp no coincide'}), 403

        user_id = from_number

        if user_message.lower() == 'verificar':
            plubot.is_verified = True  # Actualizado: usar plubot
            session.commit()
            twilio_client.messages.create(
                body="¡Número verificado! Tu plubot está listo para usar.",  # Actualizado: mensaje
                from_=f'whatsapp:{TWILIO_PHONE}',
                to=from_number
            )
            return jsonify({'status': 'success', 'message': 'Verificado'}), 200

        if not check_quota(plubot.user_id, session):
            twilio_response = MessagingResponse()
            twilio_response.message("Has alcanzado el límite de mensajes de este mes. Actualiza tu plan para continuar.")
            return Response(str(twilio_response), mimetype='text/xml')

        increment_quota(plubot.user_id, session)

        conversation = Conversation(
            chatbot_id=chatbot_id,
            user_id=user_id,
            message=user_message,
            role='user'
        )
        session.add(conversation)
        session.commit()

        history = session.query(Conversation).filter_by(chatbot_id=chatbot_id, user_id=user_id).order_by(Conversation.timestamp.asc()).all()
        flows = session.query(Flow).filter_by(chatbot_id=chatbot_id).order_by(Flow.position.asc()).all()

        user_msg_lower = user_message.lower()
        response = None
        for flow in flows:
            if user_msg_lower == flow.user_message.lower():
                response = flow.bot_response
                break

        if not response:
            messages = [
                {"role": "system", "content": f"Eres un plubot {plubot.tone} llamado '{plubot.name}'. Tu propósito es {plubot.purpose}."},  # Actualizado: usar plubot
                {"role": "user", "content": f"Historial: {summarize_history(history)}\nMensaje: {user_message}"}
            ]
            if plubot.business_info:
                messages[0]["content"] += f"\nNegocio: {plubot.business_info}"
            if plubot.pdf_content:
                messages[0]["content"] += f"\nContenido del PDF: {plubot.pdf_content}"
            response = call_grok(messages, max_tokens=150)

        bot_conversation = Conversation(
            chatbot_id=chatbot_id,
            user_id=user_id,
            message=response,
            role='bot'
        )
        session.add(bot_conversation)
        session.commit()

        twilio_response = MessagingResponse()
        twilio_response.message(response)
        return Response(str(twilio_response), mimetype='text/xml')