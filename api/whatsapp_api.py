from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required
from twilio.twiml.messaging_response import MessagingResponse
from services import whatsapp_service
from models import db, WhatsappConnection
import logging

whatsapp_api_bp = Blueprint('whatsapp_api', __name__)
logger = logging.getLogger(__name__)

@whatsapp_api_bp.route('/whatsapp/connect', methods=['POST'])
@jwt_required()
def connect_to_twilio():
    """Establishes the connection of a plubot with the configured Twilio number."""
    data = request.get_json()
    plubot_id = data.get('plubotId')
    if not plubot_id:
        return jsonify({'status': 'error', 'message': 'plubotId es requerido'}), 400

    twilio_phone_number = current_app.config.get('TWILIO_PHONE_NUMBER')
    if not twilio_phone_number:
        logger.error("TWILIO_PHONE_NUMBER is not configured on the server.")
        return jsonify({'status': 'error', 'message': 'La integración con Twilio no está configurada en el servidor.'}), 500

    clean_phone_number = twilio_phone_number.replace('whatsapp:', '')

    try:
        connection = WhatsappConnection.query.filter_by(plubot_id=plubot_id).first()
        if not connection:
            connection = WhatsappConnection(plubot_id=plubot_id)
            db.session.add(connection)
        
        connection.status = 'connected'
        connection.whatsapp_number = clean_phone_number
        db.session.commit()

        logger.info(f"Plubot {plubot_id} successfully connected to Twilio number {clean_phone_number}")
        return jsonify({'status': 'success', 'message': 'Conectado exitosamente a Twilio.'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error connecting plubot {plubot_id} to Twilio: {e}")
        return jsonify({'status': 'error', 'message': 'Error interno al conectar con Twilio.'}), 500

@jwt_required()
def get_status(plubot_id):
    # Validación de propiedad del plubot
    service = WhatsAppService()
    status = service.get_connection_status(plubot_id)
    return jsonify(status), 200

@whatsapp_api_bp.route('/disconnect', methods=['POST'])
@jwt_required()
def disconnect_whatsapp():
    data = request.get_json()
    plubot_id = data.get('plubotId')
    # Validación de propiedad del plubot

    service = WhatsAppService()
    response, status_code = service.disconnect_plubot(plubot_id)
    return jsonify(response), status_code

@whatsapp_api_bp.route('/webhook', methods=['POST'])
def whatsapp_webhook():
    """
    Endpoint para recibir webhooks de la API de WhatsApp (ej. Whapi.Cloud).
    Estos webhooks suelen enviar datos en formato JSON.
    """
    data = request.get_json()
    service = WhatsAppService()
    service.handle_incoming_message(data)
    
    # Se responde con un 200 OK para confirmar la recepción.
    return jsonify({'status': 'received'}), 200
