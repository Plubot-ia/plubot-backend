# plubot-backend/api/actions_api.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
import asyncio

from services.discord_action_service import send_discord_message_adhoc

actions_bp = Blueprint('actions_api', __name__, url_prefix='/api/actions')
logger = logging.getLogger(__name__)

@actions_bp.route('/discord/send_message', methods=['POST'])
@jwt_required()
def send_discord_node_message():
    """
    Endpoint para ejecutar la acción de enviar un mensaje de un nodo Discord.
    Espera un JSON con: token, channel_id, message.
    """
    user_id = get_jwt_identity()
    data = request.json

    if not data:
        return jsonify(error="Payload JSON vacío o inválido."), 400

    bot_token = data.get('token')
    channel_id = data.get('channel_id')
    message_content = data.get('message')

    if not all([bot_token, channel_id, message_content]):
        missing_fields = []
        if not bot_token: missing_fields.append('token')
        if not channel_id: missing_fields.append('channel_id')
        if not message_content: missing_fields.append('message')
        logger.warning(f"Usuario {user_id} intentó enviar mensaje de Discord con campos faltantes: {', '.join(missing_fields)}")
        return jsonify(error=f"Faltan campos requeridos: {', '.join(missing_fields)}."), 400

    logger.info(f"Usuario {user_id} solicita enviar mensaje vía nodo Discord al canal {channel_id}. Mensaje: '{message_content[:50]}...'" )

    try:
        # Dado que send_discord_message_adhoc es una función async,
        # y Flask por defecto es síncrono, necesitamos ejecutarla en un loop de eventos.
        # Si tu Flask está configurado para ASGI (ej. con Hypercorn + Quart), esto sería más directo.
        # Para un entorno Flask estándar (WSGI), asyncio.run() es una forma de hacerlo.
        # Considerar usar flask-executor o similar para tareas más largas/complejas en producción WSGI.
        
        # Comprobar si ya existe un loop de eventos corriendo (común en entornos como Jupyter o si Flask usa ASGI)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # 'RuntimeError: There is no current event loop...' 
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # Si el loop ya está corriendo (ej. en un servidor ASGI como uvicorn/hypercorn con app Quart/FastAPI)
            # podemos crear una tarea.
            # Sin embargo, en Flask estándar síncrono, esto podría no ser lo ideal.
            # Para Flask síncrono, ejecutarlo directamente con loop.run_until_complete o asyncio.run es más común.
            # Por simplicidad y compatibilidad con un Flask estándar, usaremos asyncio.run() si no hay loop,
            # o lo ejecutaremos en el loop existente si es posible (aunque esto es más complejo de manejar correctamente
            # en un contexto puramente WSGI sin extensiones como flask-async).
            
            # Solución más simple para Flask WSGI: ejecutar en un nuevo loop o usar run_until_complete.
            # Para este caso, vamos a usar una forma que intente ser segura:
            success, message = loop.run_until_complete(send_discord_message_adhoc(bot_token, channel_id, message_content))
        else:
            success, message = asyncio.run(send_discord_message_adhoc(bot_token, channel_id, message_content))

        if success:
            logger.info(f"Mensaje de nodo Discord enviado exitosamente por usuario {user_id} al canal {channel_id}.")
            return jsonify(status="success", message=message), 200
        else:
            logger.error(f"Error al enviar mensaje de nodo Discord por usuario {user_id} al canal {channel_id}: {message}")
            # Devolver un 400 o 500 dependiendo de la naturaleza del error. 
            # Si es un error del usuario (ej. mal token), 400. Si es del sistema, 500.
            # La función send_discord_message_adhoc debería ayudar a discernir esto.
            # Por ahora, un 400 genérico si falla por datos, 500 si es error interno.
            if "Token inválido" in message or "no encontrado" in message or "permisos" in message:
                 return jsonify(status="error", message=message), 400 # Error atribuible a la configuración del usuario
            return jsonify(status="error", message=message), 500 # Error del sistema

    except Exception as e:
        logger.critical(f"Excepción crítica en endpoint send_discord_node_message para usuario {user_id}: {e}", exc_info=True)
        return jsonify(status="error", message=f"Error interno del servidor al procesar la solicitud: {str(e)}"), 500

# Podrías añadir más endpoints de acciones aquí en el futuro
# ej. @actions_bp.route('/twitter/post_tweet', methods=['POST'])
# @jwt_required()
# def post_twitter_node_action():
#     pass
