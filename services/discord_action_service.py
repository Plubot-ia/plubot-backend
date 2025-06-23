# plubot-backend/services/discord_action_service.py
import discord
import logging
import asyncio

logger = logging.getLogger(__name__)

async def send_discord_message_adhoc(token: str, channel_id_str: str, message_content: str):
    """
    Envia un mensaje a un canal de Discord específico utilizando un token de bot proporcionado.
    Esta función crea un cliente temporal, envía el mensaje y luego se desconecta.

    Args:
        token: El token del bot de Discord a utilizar.
        channel_id_str: El ID del canal de Discord (como string) al que enviar el mensaje.
        message_content: El contenido del mensaje a enviar.

    Returns:
        Una tupla (bool, str) indicando éxito/fracaso y un mensaje descriptivo.
    """
    if not all([token, channel_id_str, message_content]):
        return False, "Token, ID de canal y contenido del mensaje son requeridos."

    try:
        channel_id = int(channel_id_str)
    except ValueError:
        logger.error(f"ID de canal inválido: {channel_id_str}. Debe ser un número.")
        return False, f"ID de canal inválido: {channel_id_str}. Debe ser un número."

    # Es importante definir los intents mínimos necesarios. Para enviar mensajes, default puede ser suficiente.
    # Si se requieren más, como leer miembros para menciones, se deben añadir.
    intents = discord.Intents.default()
    # Si necesitas verificar si el bot puede enviar mensajes (opcional, pero buena práctica):
    # intents.guilds = True # Para fetch_channel en algunos casos o para verificar permisos.

    client = discord.Client(intents=intents)

    try:
        logger.info(f"Intentando conectar al bot de Discord para envío ad-hoc.")
        # El timeout para login es interno de discord.py, pero podemos envolver la operación si es necesario.
        await client.login(token)
        logger.info(f"Bot conectado exitosamente para envío ad-hoc.")

        channel = client.get_channel(channel_id)
        if not channel:
            # Si get_channel falla (puede ser por caché o intents), intentar fetch_channel
            try:
                logger.info(f"Canal {channel_id} no encontrado con get_channel, intentando fetch_channel.")
                channel = await client.fetch_channel(channel_id)
            except discord.NotFound:
                logger.error(f"Canal de Discord {channel_id} no encontrado.")
                return False, f"Canal de Discord {channel_id} no encontrado."
            except discord.Forbidden:
                logger.error(f"El bot no tiene permisos para acceder al canal {channel_id}.")
                return False, f"El bot no tiene permisos para acceder al canal {channel_id}."
            except Exception as e:
                logger.error(f"Error inesperado al hacer fetch_channel {channel_id}: {e}", exc_info=True)
                return False, f"Error al obtener el canal: {str(e)}"
        
        if not isinstance(channel, discord.abc.Messageable):
            logger.error(f"El ID {channel_id} no corresponde a un canal donde se puedan enviar mensajes.")
            return False, f"El ID {channel_id} no corresponde a un canal donde se puedan enviar mensajes."

        logger.info(f"Enviando mensaje al canal {channel_id}: '{message_content[:50]}...'" )
        await channel.send(message_content)
        logger.info(f"Mensaje enviado exitosamente al canal {channel_id}.")
        return True, "Mensaje enviado exitosamente."

    except discord.LoginFailure:
        logger.error("Fallo de inicio de sesión en Discord. Verifica el token del bot proporcionado.")
        return False, "Token de Discord inválido o incorrecto."
    except discord.Forbidden as e:
        logger.error(f"Error de permisos de Discord al enviar mensaje: {e}", exc_info=True)
        # Esto podría ocurrir si el bot no tiene permiso para 'Send Messages' en el canal.
        return False, f"El bot no tiene los permisos necesarios para enviar mensajes al canal {channel_id}. Detalles: {e.text if hasattr(e, 'text') else str(e)}"
    except discord.HTTPException as e:
        logger.error(f"Error HTTP de Discord al enviar mensaje: {e}", exc_info=True)
        return False, f"Error de comunicación con Discord: {e.text if hasattr(e, 'text') else str(e)}"
    except Exception as e:
        logger.error(f"Error inesperado al enviar mensaje de Discord: {e}", exc_info=True)
        return False, f"Error inesperado: {str(e)}"
    finally:
        if client.is_ready(): # Solo cerrar si está listo/conectado
            logger.info("Cerrando conexión del bot de Discord para envío ad-hoc.")
            await client.close()
        elif client.ws:
            logger.info("Cliente de Discord no estaba listo pero tenía websocket, intentando cerrar.")
            await client.close() # Intentar cerrar de todas formas si hay un websocket

# Ejemplo de cómo se podría llamar (para pruebas locales, no parte del servicio Flask directamente así):
# async def main_test():
#     test_token = "TU_TOKEN_DE_PRUEBA_AQUI"
#     test_channel_id = "TU_ID_DE_CANAL_DE_PRUEBA_AQUI"
#     test_message = "Hola desde el servicio de envío ad-hoc de Plubot!"
#     if test_token == "TU_TOKEN_DE_PRUEBA_AQUI" or test_channel_id == "TU_ID_DE_CANAL_DE_PRUEBA_AQUI":
#         print("Por favor, configura test_token y test_channel_id para probar.")
#         return
#     success, message = await send_discord_message_adhoc(test_token, test_channel_id, test_message)
#     print(f"Resultado: {'Éxito' if success else 'Fallo'} - Mensaje: {message}")

# if __name__ == '__main__':
#     logging.basicConfig(level=logging.INFO)
#     asyncio.run(main_test())
