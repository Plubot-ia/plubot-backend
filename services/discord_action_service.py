# plubot-backend/services/discord_action_service.py
import logging
from typing import cast

import discord

logger = logging.getLogger(__name__)


async def _get_channel_from_client(
    client: discord.Client, channel_id: int
) -> tuple[discord.abc.Messageable | None, str | None]:
    """Obtiene y valida un canal de Discord a partir de un cliente y un ID."""
    channel = client.get_channel(channel_id)
    error_message: str | None = None

    if not channel:
        try:
            logger.info("Canal %s no en caché, intentando fetch_channel.", channel_id)
            channel = await client.fetch_channel(channel_id)
        except discord.NotFound:
            logger.exception("Canal de Discord %s no encontrado.", channel_id)
            error_message = f"Canal de Discord {channel_id} no encontrado."
        except discord.Forbidden:
            logger.exception(
                "El bot no tiene permisos para acceder al canal %s.", channel_id
            )
            error_message = f"Sin permisos para acceder al canal {channel_id}."
        except Exception:
            logger.exception(
                "Error inesperado al hacer fetch_channel para el canal %s.", channel_id
            )
            error_message = "Error al obtener el canal."

    # Después de intentar obtener el canal, validar errores o si es 'Messageable'.
    if not error_message:
        if not channel:
            error_message = (
                f"Canal {channel_id} no encontrado por una razón desconocida."
            )
        elif not isinstance(channel, discord.abc.Messageable):
            logger.error("El ID %s no corresponde a un canal de texto.", channel_id)
            error_message = (
                f"El ID {channel_id} no es un canal donde se puedan enviar mensajes."
            )

    # Si hubo un error en cualquier punto, el canal final es inválido.
    final_channel = (
        channel
        if not error_message and isinstance(channel, discord.abc.Messageable)
        else None
    )
    return final_channel, error_message


async def send_discord_message_adhoc(
    token: str, channel_id_str: str, message_content: str
) -> tuple[bool, str]:
    """Envía un mensaje a un canal de Discord específico de forma ad-hoc.

    Crea un cliente temporal, envía el mensaje y se desconecta de forma segura.

    Args:
        token: El token del bot de Discord a utilizar.
        channel_id_str: El ID del canal de Discord (como string).
        message_content: El contenido del mensaje a enviar.

    Returns:
        Una tupla (bool, str) que indica el éxito y un mensaje descriptivo.
    """
    if not all([token, channel_id_str, message_content]):
        return False, "Token, ID de canal y contenido del mensaje son requeridos."

    try:
        channel_id = int(channel_id_str)
    except ValueError:
        logger.exception(
            "ID de canal inválido: %s. Debe ser un número.", channel_id_str
        )
        return False, f"ID de canal inválido: {channel_id_str}. No es un número."

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    success = False
    message = "Error inesperado al enviar el mensaje."

    try:
        logger.info("Conectando al bot de Discord para envío ad-hoc.")
        await client.login(token)
        logger.info("Bot conectado exitosamente para envío ad-hoc.")

        channel, error_message = await _get_channel_from_client(client, channel_id)
        if error_message:
            message = error_message
        else:
            channel = cast("discord.abc.Messageable", channel)
            await channel.send(message_content)
            logger.info(
                "Mensaje enviado a canal %s: '%s...'",
                channel_id,
                message_content[:50],
            )
            success = True
            message = "Mensaje enviado exitosamente."

    except discord.LoginFailure:
        logger.exception("Fallo de login en Discord. Token inválido.")
        message = "Token de Discord inválido o incorrecto."
    except discord.Forbidden as e:
        details = getattr(e, "text", str(e))
        logger.exception("Error de permisos de Discord al enviar mensaje.")
        message = (
            f"El bot no tiene permisos para enviar mensajes al canal {channel_id}. "
            f"Detalles: {details}"
        )
    except discord.HTTPException as e:
        details = getattr(e, "text", str(e))
        logger.exception("Error HTTP de Discord al enviar mensaje.")
        message = f"Error de comunicación con Discord: {details}"
    except Exception:
        logger.exception("Error inesperado al enviar mensaje de Discord.")
        # El mensaje de error por defecto ya está establecido.

    finally:
        if client.is_ready():
            logger.info("Cerrando conexión del bot de Discord (ad-hoc).")
            await client.close()
        elif client.ws:
            logger.info("Cerrando websocket de Discord no listo (ad-hoc).")
            await client.close()

    return success, message

