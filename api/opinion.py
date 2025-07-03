import logging

from flask import Blueprint, Response, current_app, jsonify, request

from services.mail_service import send_email

opinion_bp = Blueprint("opinion", __name__)
logger = logging.getLogger(__name__)

@opinion_bp.route("/", methods=["POST"])
def submit_opinion() -> Response:
    """Endpoint para recibir opiniones desde el formulario de TuOpinion.jsx.

    Recibe nombre (opcional) y opinion (requerida), y envía un correo con los datos.
    """
    try:
        data = request.form
        nombre: str = data.get("nombre", "Anónimo").strip()
        opinion: str = data.get("opinion", "").strip()

        # Validar que la opinión no esté vacía
        if not opinion:
            logger.warning("Intento de enviar opinión vacía")
            return jsonify({"status": "error", "message": "La opinión es requerida"}), 400

        # Preparar el contenido del correo
        subject = f"Nueva opinión de {nombre}"
        body = f"Nombre: {nombre}\nOpinión: {opinion}"

        # Enviar el correo usando mail_service
        send_email(
            recipient=current_app.config["OPINION_RECIPIENT_EMAIL"],
            subject=subject,
            body=body
        )

        logger.info("Opinión enviada exitosamente de %s", nombre)
        return jsonify({
            "status": "success",
            "message": "¡Tu opinión ha sido enviada al Pluniverse! Gracias por ayudarnos a mejorar."
        }), 200

    except Exception:
        logger.exception("Error al procesar la opinión")
        return jsonify({"status": "error", "message": "Error al enviar la opinión"}), 500
