from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from config.settings import get_session
from models.chatbot import Chatbot
from services.twilio_service import twilio_client, TWILIO_PHONE, validate_whatsapp_number
import logging
import re

whatsapp_bp = Blueprint('whatsapp', __name__)
logger = logging.getLogger(__name__)

@whatsapp_bp.route('/connect', methods=['POST', 'OPTIONS'])
@jwt_required()
def connect_whatsapp():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200

    user_id = get_jwt_identity()
    data = request.get_json()
    chatbot_id = data.get('chatbot_id')
    phone_number = data.get('phone_number')

    if not chatbot_id or not phone_number:
        return jsonify({'status': 'error', 'message': 'Faltan chatbot_id o phone_number'}), 400

    if not re.match(r'^\+\d{10,15}$', phone_number):
        return jsonify({'status': 'error', 'message': 'El número debe tener formato internacional, ej. +1234567890'}), 400

    with get_session() as session:
        chatbot = session.query(Chatbot).filter_by(id=chatbot_id, user_id=user_id).first()
        if not chatbot:
            return jsonify({'status': 'error', 'message': 'Chatbot no encontrado o no tienes permiso'}), 404

        if not validate_whatsapp_number(phone_number):
            return jsonify({'status': 'error', 'message': 'El número no está registrado en Twilio. Regístralo primero.'}), 400

        try:
            message = twilio_client.messages.create(
                body="¡Hola! Soy Plubot. Responde 'VERIFICAR' para conectar tu chatbot. Si necesitas ayuda, visita https://www.plubot.com/support.",
                from_=f'whatsapp:{TWILIO_PHONE}',
                to=f'whatsapp:{phone_number}'
            )
            logger.info(f"Mensaje enviado a {phone_number}: {message.sid}")
            chatbot.whatsapp_number = phone_number
            session.commit()
            return jsonify({'status': 'success', 'message': f'Verifica tu número {phone_number} respondiendo "VERIFICAR" en WhatsApp.'}), 200
        except Exception as e:
            logger.error(f"Error en /connect-whatsapp: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Error: {str(e)}'}), 500