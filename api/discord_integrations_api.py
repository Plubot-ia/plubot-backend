from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, current_user
from models import db
from models.discord_integration import DiscordIntegration
from models.user import User # To access current_user.id if current_user is a User object
from utils.security import encrypt_token, decrypt_token # For bot token encryption and decryption
import logging
import requests

logger = logging.getLogger(__name__)

discord_integrations_bp = Blueprint('discord_integrations_bp', __name__, url_prefix='/api/discord-integrations')


def _verify_discord_token(integration: DiscordIntegration):
    """
    Verifies the Discord bot token by making a request to the Discord API.
    Updates the integration status based on the verification result.
    """
    if not integration or not integration.bot_token_encrypted:
        logger.warning(f"_verify_discord_token: Attempted to verify an integration without a token or invalid integration object. ID: {integration.id if integration else 'N/A'}")
        return

    try:
        decrypted_token = decrypt_token(integration.bot_token_encrypted)
    except Exception as e:
        logger.error(f"_verify_discord_token: Failed to decrypt token for integration ID {integration.id}. Error: {str(e)}")
        integration.status = 'verification_error' # Or a more specific decryption error status
        integration.last_error_message = f"Failed to decrypt token: {str(e)}"
        db.session.commit()
        return

    headers = {
        "Authorization": f"Bot {decrypted_token}"
    }
    verify_url = "https://discord.com/api/v10/users/@me"

    try:
        response = requests.get(verify_url, headers=headers, timeout=10) # 10 second timeout
        if response.status_code == 200:
            integration.status = 'active'
            integration.last_error_message = None
            logger.info(f"_verify_discord_token: Token for integration ID {integration.id} verified successfully. Status set to active.")
        elif response.status_code == 401:
            integration.status = 'invalid_token'
            integration.last_error_message = "Token is invalid or unauthorized."
            logger.warning(f"_verify_discord_token: Token for integration ID {integration.id} is invalid (401). Status set to invalid_token.")
        else:
            integration.status = 'verification_error'
            integration.last_error_message = f"Discord API returned status {response.status_code}: {response.text[:200]}" # Log part of the response
            logger.error(f"_verify_discord_token: Discord API error for integration ID {integration.id}. Status: {response.status_code}, Response: {response.text[:200]}")
    except requests.exceptions.Timeout:
        integration.status = 'verification_error'
        integration.last_error_message = "Verification timed out. Discord API did not respond in time."
        logger.error(f"_verify_discord_token: Timeout while verifying token for integration ID {integration.id}.")
    except requests.exceptions.RequestException as e:
        integration.status = 'verification_error'
        integration.last_error_message = f"Network error during verification: {str(e)}"
        logger.error(f"_verify_discord_token: Network error for integration ID {integration.id}. Error: {str(e)}")
    except Exception as e:
        integration.status = 'verification_error'
        integration.last_error_message = f"An unexpected error occurred during verification: {str(e)}"
        logger.error(f"_verify_discord_token: Unexpected error for integration ID {integration.id}. Error: {str(e)}")
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"_verify_discord_token: Failed to commit status update for integration ID {integration.id}. Error: {str(e)}")


@discord_integrations_bp.route('/', methods=['POST'])
@jwt_required()
def create_discord_integration():
    """
    Crea una nueva integración de Discord para el usuario autenticado.
    Espera un JSON con: integration_name, bot_token, guild_id (opcional), default_channel_id (opcional)
    """
    data = request.json
    if not data:
        return jsonify(error="Payload JSON vacío o inválido."), 400

    integration_name = data.get('integration_name')
    bot_token = data.get('bot_token') # Raw token, needs encryption
    guild_id = data.get('guild_id')
    default_channel_id = data.get('default_channel_id')

    if not integration_name or not bot_token:
        logger.warning(f"create_discord_integration: Missing mandatory fields. integration_name: '{integration_name}', bot_token is {'present and not empty' if bot_token else 'missing or empty'}.")
        return jsonify(error="Faltan campos obligatorios: integration_name y bot_token."), 400

    try:
        encrypted_bot_token = encrypt_token(bot_token)
    except Exception as e:
        logger.error(f"Error al cifrar el token durante la creación: {str(e)}")
        # Podríamos querer retornar un error específico si la ENCRYPTION_KEY no está configurada
        # o si el token es inválido para cifrar por alguna razón.
        return jsonify(error=f"Error de configuración del servidor al procesar el token: {str(e)}"), 500

    try:
        # Ensure current_user is a User instance or has an 'id' attribute
        # This depends on how flask_jwt_extended is configured with your User model
        user_id = current_user.id if hasattr(current_user, 'id') else current_user # Adjust if current_user is just an ID
        
        new_integration = DiscordIntegration(
            user_id=user_id,
            integration_name=integration_name,
            bot_token_encrypted=encrypted_bot_token,
            guild_id=guild_id,
            default_channel_id=default_channel_id,
            status='pending_verification' # Initial status, bot manager would verify and update
        )
        db.session.add(new_integration)
        db.session.commit() # Commit first to get an ID for new_integration
        logger.info(f"Nueva integración de Discord creada con ID: {new_integration.id} para el usuario ID: {user_id}. Iniciando verificación del token.")
        _verify_discord_token(new_integration) # Verify token and update status
        # The status in the response will reflect the post-verification status
        return jsonify(
            message="Integración de Discord creada exitosamente.", 
            integration_id=new_integration.id,
            integration_name=new_integration.integration_name,
            status=new_integration.status
        ), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al crear la integración de Discord: {str(e)}")
        return jsonify(error=f"Error interno del servidor al crear la integración: {str(e)}"), 500


@discord_integrations_bp.route('/', methods=['GET'])
@jwt_required()
def get_discord_integrations():
    """
    Obtiene todas las integraciones de Discord para el usuario autenticado.
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user
        integrations = DiscordIntegration.query.filter_by(user_id=user_id).order_by(DiscordIntegration.created_at.desc()).all()
        
        output = []
        for integration in integrations:
            output.append({
                'id': integration.id,
                'integration_name': integration.integration_name,
                'guild_id': integration.guild_id,
                'default_channel_id': integration.default_channel_id,
                'status': integration.status,
                'created_at': integration.created_at.isoformat(),
                'updated_at': integration.updated_at.isoformat()
            })
        
        return jsonify(integrations=output), 200

    except Exception as e:
        logger.error(f"Error al obtener las integraciones de Discord: {str(e)}")
        return jsonify(error=f"Error interno del servidor al obtener las integraciones: {str(e)}"), 500


@discord_integrations_bp.route('/<int:integration_id>', methods=['GET'])
@jwt_required()
def get_discord_integration_detail(integration_id):
    """
    Obtiene los detalles de una integración de Discord específica por su ID.
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user
        integration = DiscordIntegration.query.filter_by(id=integration_id, user_id=user_id).first()

        if not integration:
            return jsonify(error="Integración de Discord no encontrada o no pertenece al usuario."), 404

        response_data = {
            'id': integration.id,
            'integration_name': integration.integration_name,
            'guild_id': integration.guild_id,
            'default_channel_id': integration.default_channel_id,
            'status': integration.status,
            'last_error_message': integration.last_error_message,
            'created_at': integration.created_at.isoformat(),
            'updated_at': integration.updated_at.isoformat()
        }

        # Intentar desencriptar y añadir el bot_token
        if integration.bot_token_encrypted:
            try:
                decrypted_token = decrypt_token(integration.bot_token_encrypted)
                response_data['bot_token'] = decrypted_token
            except Exception as e:
                logger.error(f"Error al desencriptar el token para la integración {integration_id} (usuario {user_id}): {str(e)}")
                response_data['bot_token'] = None # O podrías omitir la clave
                response_data['token_error'] = "Error al procesar el token."
        else:
            response_data['bot_token'] = None # No hay token encriptado para empezar

        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Error al obtener detalles de la integración de Discord {integration_id}: {str(e)}")
        return jsonify(error=f"Error interno del servidor al obtener detalles de la integración: {str(e)}"), 500


@discord_integrations_bp.route('/<int:integration_id>', methods=['PUT'])
@jwt_required()
def update_discord_integration(integration_id):
    """
    Actualiza una integración de Discord existente.
    """
    data = request.json
    if not data:
        return jsonify(error="Payload JSON vacío o inválido."), 400

    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user
        integration = DiscordIntegration.query.filter_by(id=integration_id, user_id=user_id).first()

        if not integration:
            return jsonify(error="Integración de Discord no encontrada o no pertenece al usuario."), 404

        # Campos actualizables
        if 'integration_name' in data:
            integration.integration_name = data['integration_name']
        if 'bot_token' in data and data['bot_token']:
            try:
                integration.bot_token_encrypted = encrypt_token(data['bot_token'])
            except Exception as e:
                logger.error(f"Error al cifrar el token durante la actualización para la integración {integration_id}: {str(e)}")
                return jsonify(error=f"Error de configuración del servidor al procesar el token: {str(e)}"), 500
        if 'guild_id' in data:
            integration.guild_id = data['guild_id']
        if 'default_channel_id' in data:
            integration.default_channel_id = data['default_channel_id']
        # El estado (status) podría ser manejado por un proceso separado (ej. el bot manager)
        # o permitir ciertos cambios de estado aquí si tiene sentido.
        # if 'status' in data:
        #     integration.status = data['status']

        token_updated = 'bot_token' in data and data['bot_token']

        db.session.commit()
        
        if token_updated:
            logger.info(f"Token actualizado para la integración de Discord ID: {integration_id}. Iniciando verificación del nuevo token.")
            _verify_discord_token(integration) # Verify new token and update status
        logger.info(f"Integración de Discord ID: {integration_id} actualizada para el usuario ID: {user_id}")
        
        return jsonify({
            'message': 'Integración de Discord actualizada exitosamente.',
            'id': integration.id,
            'integration_name': integration.integration_name,
            'guild_id': integration.guild_id,
            'default_channel_id': integration.default_channel_id,
            'status': integration.status,
            'updated_at': integration.updated_at.isoformat()
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al actualizar la integración de Discord {integration_id}: {str(e)}")
        return jsonify(error=f"Error interno del servidor al actualizar la integración: {str(e)}"), 500


@discord_integrations_bp.route('/<int:integration_id>', methods=['DELETE'])
@jwt_required()
def delete_discord_integration(integration_id):
    """
    Elimina una integración de Discord existente.
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user
        integration = DiscordIntegration.query.filter_by(id=integration_id, user_id=user_id).first()

        if not integration:
            return jsonify(error="Integración de Discord no encontrada o no pertenece al usuario."), 404

        db.session.delete(integration)
        db.session.commit()
        logger.info(f"Integración de Discord ID: {integration_id} eliminada para el usuario ID: {user_id}")
        
        return jsonify(message='Integración de Discord eliminada exitosamente.'), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al eliminar la integración de Discord {integration_id}: {str(e)}")
        return jsonify(error=f"Error interno del servidor al eliminar la integración: {str(e)}"), 500
