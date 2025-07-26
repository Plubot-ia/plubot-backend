"""Script de prueba para verificar la configuración y el envío de correos SMTP."""

from email.message import EmailMessage
import logging
import os
import smtplib

# --- Configuración del Logger ---
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Configuración SMTP desde variables de entorno ---
MAIL_SERVER = "smtp.zoho.com"
MAIL_PORT = 587
MAIL_USERNAME = "info@plubot.com"
MAIL_PASSWORD = os.getenv("SMTP_PASSWORD")
RECIPIENT_EMAIL = os.getenv("SMTP_RECIPIENT", "test@example.com")


def send_test_email() -> None:
    """Configura y envía un correo de prueba."""
    if not MAIL_PASSWORD:
        logger.error("La variable de entorno SMTP_PASSWORD no está configurada.")
        return

    # --- Crear mensaje de prueba ---
    msg = EmailMessage()
    msg.set_content("Este es un correo de prueba desde Plubot.")
    msg["Subject"] = "Correo de Prueba"
    msg["From"] = MAIL_USERNAME
    msg["To"] = RECIPIENT_EMAIL

    # --- Conectar y enviar ---
    try:
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.send_message(msg)
        logger.info("Correo de prueba enviado exitosamente a %s", RECIPIENT_EMAIL)
    except smtplib.SMTPException:
        logger.exception("Error de SMTP al enviar correo")
    except OSError:
        logger.exception("Error de red al conectar con el servidor")


if __name__ == "__main__":
    send_test_email()
