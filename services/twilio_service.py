import logging

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from config.settings import settings

logger = logging.getLogger(__name__)


class _TwilioManager:
    """Manages a singleton Twilio client instance to avoid using globals."""

    _client: Client | None = None

    def get_client(self) -> Client | None:
        """Return a Twilio client instance, creating it if it doesn't exist."""
        if self._client is None:
            if not all(
                [
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN,
                    settings.TWILIO_WHATSAPP_NUMBER,
                ]
            ):
                logger.critical(
                    "Faltan credenciales de Twilio. La integración no funcionará."
                )
                return None
            self._client = Client(
                settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN
            )
        return self._client


_twilio_manager = _TwilioManager()
get_twilio_client = _twilio_manager.get_client


def send_whatsapp_message(to_number: str, body: str) -> str | None:
    """Send a WhatsApp message using Twilio.

    Args:
        to_number: The recipient's number in E.164 format.
        body: The message content.

    Returns:
        The message SID if successful, None otherwise.
    """
    client = get_twilio_client()
    if not client:
        return None

    try:
        from_number = settings.TWILIO_WHATSAPP_NUMBER
        message = client.messages.create(
            body=body, from_=f"whatsapp:{from_number}", to=to_number
        )
    except TwilioRestException:
        logger.exception("Error sending WhatsApp message to %s", to_number)
        return None
    else:
        logger.info("WhatsApp message sent to %s (SID: %s)", to_number, message.sid)
        return message.sid


def validate_whatsapp_number(number: str) -> bool:
    """Validate if a WhatsApp number exists in the Twilio account."""
    if not number.startswith("+"):
        number = f"+{number}"

    client = get_twilio_client()
    if not client:
        return False

    try:
        phone_numbers = client.api.accounts(
            settings.TWILIO_ACCOUNT_SID
        ).incoming_phone_numbers.list()
    except TwilioRestException:
        logger.exception("Error validating WhatsApp number with Twilio for %s", number)
        return False
    else:
        for phone in phone_numbers:
            if phone.phone_number == number:
                logger.info("Number %s found in Twilio account.", number)
                return True

        logger.warning("Number %s is not registered in the Twilio account.", number)
        return False
