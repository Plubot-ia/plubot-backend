import logging
from threading import Thread

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
        data = request.get_json()
        nombre: str = data.get("nombre", "Anónimo").strip()
        opinion: str = data.get("opinion", "").strip()

        # Validar que la opinión no esté vacía
        if not opinion:
            logger.warning("Intento de enviar opinión vacía")
            return jsonify({"status": "error", "message": "La opinión es requerida"}), 400

        # Preparar el contenido del correo
        subject = f"Nueva opinión de {nombre}"
        body = f"Nombre: {nombre}\nOpinión: {opinion}"

        # Ejecutar el envío de correo en un hilo separado para no bloquear la respuesta
        app = current_app._get_current_object()  # Obtener la instancia de la app para el contexto del hilo
        thread = Thread(target=send_email_async, args=[app, subject, body])
        thread.start()

        logger.info("Respuesta inmediata enviada para la opinión de %s. El correo se está procesando.", nombre)
        return jsonify({
            "status": "success",
            "message": "¡Tu opinión ha sido enviada al Pluniverse! Gracias por ayudarnos a mejorar."
        }), 200

    except Exception:
        logger.exception("Error al procesar la opinión")
        return jsonify({"status": "error", "message": "Error al enviar la opinión"}), 500


def send_email_async(app, subject, body):
    """Función para enviar correo en un hilo para no bloquear la app."""
    with app.app_context():
        try:
            send_email(
                recipient=current_app.config["OPINION_RECIPIENT_EMAIL"],
                subject=subject,
                body=body
            )
            logger.info("Correo de opinión enviado exitosamente en segundo plano.")
        except Exception:
            logger.exception("Error al enviar correo de opinión en segundo plano.")
