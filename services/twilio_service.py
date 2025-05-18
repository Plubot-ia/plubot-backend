from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import os
import logging

logger = logging.getLogger(__name__)

# Configuración de Twilio
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")

if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_PHONE]):
    raise ValueError("Faltan credenciales de Twilio en las variables de entorno.")

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)

def validate_whatsapp_number(number):
    if not number.startswith('+'):
        number = '+' + number
    try:
        phone_numbers = twilio_client.api.accounts(TWILIO_SID).incoming_phone_numbers.list()
        for phone in phone_numbers:
            if phone.phone_number == number:
                logger.info(f"Número {number} encontrado en tu cuenta Twilio.")
                return True
        logger.warning(f"Número {number} no está registrado en tu cuenta Twilio.")
        return False
    except TwilioRestException as e:
        logger.error(f"Error al validar número de WhatsApp con Twilio: {str(e)}")
        return False