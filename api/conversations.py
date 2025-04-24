from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from config.settings import get_session
from models.plubot import Plubot  # Actualizado: importar Plubot desde plubot.py
from models.conversation import Conversation
from models.flow import Flow
from utils.helpers import check_quota, increment_quota, summarize_history
from services.grok_service import call_grok
import logging

conversations_bp = Blueprint('conversations', __name__)
logger = logging.getLogger(__name__)

@conversations_bp.route('/<int:chatbot_id>/chat', methods=['POST'])
def chat(chatbot_id):
    data = request.get_json()
    user_message = data.get('message')
    user_phone = data.get('user_phone')

    if not user_message or not user_phone:
        return jsonify({'status': 'error', 'message': 'Falta el mensaje o el número de teléfono'}), 400

    with get_session() as session:
        plubot = session.query(Plubot).filter_by(id=chatbot_id).first()  # Actualizado: usar Plubot
        if not plubot:
            return jsonify({'status': 'error', 'message': 'Plubot no encontrado'}), 404

        user_id = user_phone
        if not check_quota(plubot.user_id, session):
            return jsonify({'status': 'error', 'message': 'Has alcanzado el límite de mensajes de este mes.'}), 429

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
                # Manejar acciones (payment_link, schedule_link)
                actions = []  # Asumimos que Flow tiene un campo actions; ajustar según modelo
                if hasattr(flow, 'actions') and flow.actions:
                    for action in flow.actions:
                        if action['type'] == 'payment_link':
                            amount = float(action['value'])
                            payment_url = f"https://example.com/pay?amount={amount}"  # Reemplazar con Stripe
                            response += f"\nPaga aquí: {payment_url}"
                        elif action['type'] == 'schedule_link':
                            response += f"\nAgenda una cita: {action['value']}"
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
        return jsonify({'response': response})

@conversations_bp.route('/<int:chatbot_id>/history', methods=['GET', 'OPTIONS'])
@jwt_required()
def conversation_history(chatbot_id):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200

    user_id = get_jwt_identity()
    with get_session() as session:
        plubot = session.query(Plubot).filter_by(id=chatbot_id, user_id=user_id).first()  # Actualizado: usar Plubot
        if not plubot:
            return jsonify({'status': 'error', 'message': 'Plubot no encontrado o no tienes permisos'}), 404

        history = session.query(Conversation).filter_by(chatbot_id=chatbot_id).order_by(Conversation.timestamp.asc()).all()
        history_list = [{'role': conv.role, 'message': conv.message, 'timestamp': conv.timestamp.isoformat()} for conv in history]
        return jsonify({'status': 'success', 'history': history_list}), 200