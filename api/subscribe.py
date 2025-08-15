import logging

from flask import Blueprint, Response, jsonify, request
from flask.blueprints import BlueprintSetupState
from flask_mail import Mail, Message

subscribe_bp = Blueprint("subscribe", __name__)
logger = logging.getLogger(__name__)
mail = Mail()

@subscribe_bp.record
def setup(state: BlueprintSetupState) -> None:
    mail.init_app(state.app)

@subscribe_bp.route("", methods=["POST"])
def subscribe() -> Response:
    email: str | None = request.form.get("email")
    if not email:
        return jsonify({"success": False, "message": "El correo es requerido"}), 400

    try:
        msg = Message(
            subject="Bienvenido a nuestro boletín",
            recipients=[email],  # Correo del usuario
            bcc=["info@plubot.com"],  # Copia oculta a info@plubot.com
            body=(
                "Gracias por suscribirte al boletín de Plubot. "
                "Recibirás nuestras últimas noticias y actualizaciones.\n\n"
                "Saludos,\nEl equipo de Plubot"
            ),
        )
        mail.send(msg)
        logger.info("Correo de suscripción enviado a %s", email)
        return jsonify({"success": True, "message": "Suscripción exitosa"}), 200
    except Exception:
        logger.exception("Error al enviar correo de suscripción")
        return jsonify({"success": False, "message": "Error al suscribirte"}), 500
