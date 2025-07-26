import logging

from flask import Blueprint, Response, jsonify, request
from flask.blueprints import BlueprintSetupState
from flask_mail import Mail, Message

contact_bp = Blueprint("contact", __name__)
logger = logging.getLogger(__name__)
mail = Mail()


@contact_bp.record
def setup(state: BlueprintSetupState) -> None:
    """Inicializa la extensión Flask-Mail con la app Flask."""
    mail.init_app(state.app)


@contact_bp.route("", methods=["POST"])
def contacto() -> Response:
    """Maneja el envío de formularios de contacto."""
    name = request.form.get("nombre")
    email = request.form.get("email")
    message_content = request.form.get("message")

    if not all((name, email, message_content)):
        return jsonify({"success": False, "message": "Faltan datos requeridos"}), 400

    logger.info("Recibido formulario de contacto de %s (%s)", name, email)

    try:
        # Mensaje para el equipo de Plubot
        msg_to_admin = Message(
            subject=f"Nuevo mensaje de contacto de {name}",
            recipients=["info@plubot.com"],
            body=f"Nombre: {name}\nCorreo: {email}\nMensaje: {message_content}",
        )
        mail.send(msg_to_admin)
        logger.info("Correo de contacto enviado a info@plubot.com")

        # Mensaje de confirmación para el usuario
        confirmation_body = (
            f"Hola {name},\n\nGracias por tu mensaje. "
            "Nos pondremos en contacto contigo pronto.\n\n"
            "Saludos,\nEl equipo de Plubot"
        )
        msg_to_user = Message(
            subject="Gracias por contactarnos",
            recipients=[email],
            body=confirmation_body,
        )
        mail.send(msg_to_user)
        logger.info("Correo de confirmación enviado a %s", email)

        return jsonify({"success": True, "message": "Mensaje enviado con éxito"}), 200
    except Exception:
        logger.exception("Error al procesar y enviar correos de contacto.")
        return (
            jsonify(
                {"success": False, "message": "Error interno al enviar el mensaje."}
            ),
            500,
        )
