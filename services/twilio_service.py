import logging
import os

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

logger = logging.getLogger(__name__)

# Configuración de Twilio
_TWILIO_SID = os.getenv("TWILIO_SID")
_TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
_TWILIO_PHONE = os.getenv("TWILIO_PHONE")

_MISSING_TWILIO_CREDENTIALS_ERROR = (
    "Faltan credenciales de Twilio en las variables de entorno."
)

if not all([_TWILIO_SID, _TWILIO_TOKEN, _TWILIO_PHONE]):
    raise ValueError(_MISSING_TWILIO_CREDENTIALS_ERROR)

twilio_client = Client(_TWILIO_SID, _TWILIO_TOKEN)


def send_whatsapp_message(to_number: str, body: str) -> str | None:
    """Envía un mensaje de WhatsApp usando Twilio.

    Args:
        to_number: El número del destinatario en formato E.164.
        body: El contenido del mensaje.

    Returns:
        El SID del mensaje si fue exitoso, None en caso de error.
    """
    try:
        message = twilio_client.messages.create(
            body=body, from_=f"whatsapp:{_TWILIO_PHONE}", to=to_number
        )
        logger.info("Mensaje de WhatsApp enviado a %s (SID: %s)", to_number, message.sid)
    except TwilioRestException:
        logger.exception("Error al enviar mensaje de WhatsApp a %s", to_number)
        return None
    else:
        return message.sid


def validate_whatsapp_number(number: str) -> bool:
    """Valida si un número de WhatsApp existe en la cuenta de Twilio."""
    if not number.startswith("+"):
        number = f"+{number}"

    try:
        # La llamada a la API es la única parte que necesita manejo de excepciones
        phone_numbers = twilio_client.api.accounts(
            _TWILIO_SID
        ).incoming_phone_numbers.list()
    except TwilioRestException:
        logger.exception("Error al validar número de WhatsApp con Twilio para %s", number)
        return False
    else:
        # La lógica de validación se ejecuta solo si la llamada a la API fue exitosa
        for phone in phone_numbers:
            if phone.phone_number == number:
                logger.info("Número %s encontrado en la cuenta Twilio.", number)
                return True

        logger.warning("Número %s no está registrado en la cuenta Twilio.", number)
        return False
