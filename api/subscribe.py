from flask import Blueprint, jsonify, request
from flask_mail import Mail, Message
import logging

subscribe_bp = Blueprint('subscribe', __name__)
logger = logging.getLogger(__name__)
mail = Mail()

@subscribe_bp.record
def setup(state):
    mail.init_app(state.app)

@subscribe_bp.route('', methods=['POST'])
def subscribe():
    email = request.form.get('email')
    if not email:
        return jsonify({'success': False, 'message': 'El correo es requerido'}), 400

    try:
        msg = Message(
            subject="Bienvenido a nuestro boletín",
            recipients=[email],
            body="Gracias por suscribirte al boletín de Plubot. Recibirás nuestras últimas noticias y actualizaciones.\n\nSaludos,\nEl equipo de Plubot"
        )
        mail.send(msg)
        logger.info(f"Correo de suscripción enviado a {email}")
        return jsonify({'success': True, 'message': 'Suscripción exitosa'}), 200
    except Exception as e:
        logger.error(f"Error al enviar correo de suscripción: {str(e)}")
        return jsonify({'success': False, 'message': f'Error al suscribirte: {str(e)}'}), 500