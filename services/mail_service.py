# plubot-backend/services/mail_service.py
from flask_mail import Mail, Message
from flask import current_app

mail = Mail()

def send_email(recipient, subject, body):
    """
    Envía un correo electrónico usando Flask-Mail.
    """
    try:
        msg = Message(
            subject=subject,
            recipients=[recipient],
            body=body,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        mail.send(msg)
        current_app.logger.info(f"Correo enviado a {recipient} con asunto: {subject}")
    except Exception as e:
        current_app.logger.error(f"Error al enviar correo: {str(e)}")
        raise