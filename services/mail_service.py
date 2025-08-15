# plubot-backend/services/mail_service.py
from flask import current_app
from flask_mail import Mail, Message

mail = Mail()

def send_email(recipient: str, subject: str, body: str) -> None:
    """Envía un correo electrónico usando Flask-Mail."""
    try:
        msg = Message(
            subject=subject,
            recipients=[recipient],
            body=body,
            sender=current_app.config["MAIL_DEFAULT_SENDER"],
        )
        mail.send(msg)
        current_app.logger.info("Correo enviado a %s con asunto: %s", recipient, subject)
    except Exception:
        current_app.logger.exception("Error al enviar correo a %s", recipient)
        raise
