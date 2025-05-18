from flask import Blueprint, jsonify, request
from flask_mail import Mail, Message
import logging

contact_bp = Blueprint('contact', __name__)
logger = logging.getLogger(__name__)
mail = Mail()

@contact_bp.record
def setup(state):
    mail.init_app(state.app)

@contact_bp.route('', methods=['POST'])
def contacto():
    name = request.form.get('nombre')
    email = request.form.get('email')
    message_content = request.form.get('message')

    if not all([name, email, message_content]):
        return jsonify({'success': False, 'message': 'Faltan datos requeridos'}), 400

    logger.info(f"Recibido formulario: nombre={name}, email={email}, mensaje={message_content}")

    try:
        msg = Message(
            subject=f"Nuevo mensaje de contacto de {name}",
            recipients=['info@plubot.com'],
            body=f"Nombre: {name}\nCorreo: {email}\nMensaje: {message_content}"
        )
        mail.send(msg)
        logger.info("Correo enviado a info@plubot.com")

        confirmation_msg = Message(
            subject="Gracias por contactarnos",
            recipients=[email],
            body=f"Hola {name},\n\nGracias por tu mensaje. Nos pondremos en contacto contigo pronto.\n\nSaludos,\nEl equipo de Plubot"
        )
        mail.send(confirmation_msg)
        logger.info(f"Correo de confirmación enviado a {email}")

        return jsonify({'success': True, 'message': 'Mensaje enviado con éxito'}), 200
    except Exception as e:
        logger.error(f"Error al enviar correo: {str(e)}")
        return jsonify({'success': False, 'message': f'Error al enviar el mensaje: {str(e)}'}), 500