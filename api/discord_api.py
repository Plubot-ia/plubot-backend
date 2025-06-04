# plubot-backend/api/discord_api.py
from flask import Blueprint, jsonify, request, current_app
from models import db, User  # Import db and User model
import logging

# Asumiendo que tienes modelos y db configurados en tu app Flask
# from ..models import User, PlubotStats, db # Ajusta según tu estructura
# from ..services.user_service import get_or_create_user_by_discord_id # Ejemplo de servicio

logger = logging.getLogger(__name__)

discord_bp = Blueprint('discord_api', __name__, url_prefix='/api/discord')

# --- Rutas de API para Discord ---

@discord_bp.route('/status', methods=['GET'])
def get_discord_api_status():
    """Endpoint para que el bot de Discord verifique la salud de esta API."""
    logger.info("Solicitud de estado recibida desde el bot de Discord.")
    # Aquí podrías añadir más verificaciones, como conexión a la BD
    # status_db = "ok" if db.engine.connectable else "error"
    return jsonify(
        message="API de Discord para Plubot operativa.", 
        backend_status="ok",
        # database_status=status_db 
    ), 200

@discord_bp.route('/user_xp', methods=['POST'])
def update_user_xp():
    """
    Actualiza el XP de un usuario basado en su actividad en Discord.
    Espera un JSON con: discord_user_id, discord_username, xp_to_add, guild_id, channel_id
    """
    data = request.json
    if not data:
        return jsonify(error="Payload JSON vacío o inválido."), 400

    discord_user_id = data.get('discord_user_id')
    discord_username = data.get('discord_username') # Útil para logs o crear perfil
    xp_to_add = data.get('xp_to_add')
    # guild_id = data.get('guild_id') # Podrías usarlo para XP específico por servidor
    # channel_id = data.get('channel_id') # Podrías usarlo para XP específico por canal

    if not all([discord_user_id, isinstance(xp_to_add, int)]):
        logger.warning(f"Intento de actualizar XP con datos inválidos: {data}")
        return jsonify(error="Faltan 'discord_user_id' o 'xp_to_add' (debe ser int)."), 400

    logger.info(f"Solicitud para actualizar {xp_to_add} XP para Discord ID: {discord_user_id} ({discord_username})")

    # --- Lógica de Negocio Real (con Asunciones) ---
    # Aquí integrarías con tus modelos y servicios de Plubot
    try:
        # ASUNCIÓN: El modelo User tiene campos 'discord_id' y 'discord_username'.
        # Estos campos deben ser añadidos al modelo y una migración de BD aplicada.
        user = User.query.filter_by(discord_id=discord_user_id).first()

        new_user_created = False
        if not user:
            # LÓGICA DE CREACIÓN DE USUARIO (Placeholder):
            # Esto es simplificado. Necesitarás una estrategia para manejar nuevos usuarios desde Discord.
            # Por ejemplo, ¿cómo se asigna el email y password? ¿Se crea una cuenta Plubot completa?
            # ¿O se crea un perfil ligero esperando vinculación?
            logger.info(f"Usuario con Discord ID {discord_user_id} no encontrado. Creando nuevo usuario (placeholder).")
            user = User(
                discord_id=discord_user_id,
                discord_username=discord_username,
                email=f"{discord_user_id}@discord.placeholder.com", # Placeholder Email - REQUIERE REVISIÓN
                password="!DiscordUserPlaceholderPassword!",      # Placeholder Password - REQUIERE REVISIÓN
                name=discord_username, # Usar el nombre de Discord como nombre inicial
                plucoins=0,
                level=1
            )
            db.session.add(user)
            new_user_created = True
            # Considerar hacer un flush para obtener el ID del usuario si es necesario antes del commit completo
            # db.session.flush()

        # Actualizar Plucoins (XP)
        user.plucoins = (user.plucoins or 0) + xp_to_add
        
        # Lógica de Niveles (ejemplo)
        # Puedes hacer esto más sofisticado, ej. leyendo la curva de XP de una config.
        current_level = user.level or 1
        xp_for_next_level = current_level * 100  # Ejemplo: Nivel 1->100 XP, Nivel 2->200 XP para el *siguiente* nivel
        new_level_achieved = None

        while user.plucoins >= xp_for_next_level:
            user.level += 1
            new_level_achieved = user.level # Guarda el último nivel alcanzado en este update
            # Si quieres que el XP se 'consuma' al subir de nivel:
            # user.plucoins -= xp_for_next_level 
            # Y luego recalcular xp_for_next_level para el nuevo nivel actual para ver si sube múltiples niveles
            # xp_for_next_level = user.level * 100 
            # Si el XP es acumulativo y no se consume, simplemente verifica contra el umbral del siguiente nivel.
            # Para este ejemplo, asumimos XP acumulativo y el umbral del siguiente nivel aumenta.
            xp_for_next_level = user.level * 100 # Actualiza el umbral para el *próximo* posible nivel

        db.session.commit()

        logger.info(f"Usuario {user.discord_username} (ID: {user.id}, DiscordID: {user.discord_id}) actualizado. Plucoins: {user.plucoins}, Nivel: {user.level}")
        
        response_message = f"XP actualizado para {user.discord_username}."
        if new_user_created:
            response_message = f"Perfil de Plubot creado para {user.discord_username} y XP actualizado."
        if new_level_achieved:
            response_message += f" ¡Felicidades, has alcanzado el Nivel {new_level_achieved}!"

        return jsonify(
            message=response_message,
            discord_user_id=user.discord_id,
            plubot_user_id=user.id,
            xp_added=xp_to_add,
            new_xp_total=user.plucoins,
            current_level=user.level,
            new_level_achieved=new_level_achieved
        ), 200

    except Exception as e:
        # db.session.rollback() # Si usas transacciones
        logger.error(f"Error al actualizar XP para {discord_user_id}: {e}", exc_info=True)
        return jsonify(error="Error interno al procesar la actualización de XP."), 500

# Podrías añadir más endpoints aquí, por ejemplo:
# @discord_bp.route('/user/<discord_user_id>/plubot_info', methods=['GET'])
# def get_user_plubot_info(discord_user_id):
#    # Lógica para obtener datos del Plubot de un usuario específico
#    pass

# @discord_bp.route('/command/train_plubot', methods=['POST'])
# def handle_train_command():
#    # Lógica para procesar un comando de entrenamiento desde Discord
#    # data = request.json (discord_user_id, plubot_id_o_nombre, tema_entrenamiento, etc.)
#    pass
