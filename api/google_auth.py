from flask import Blueprint, jsonify, request, redirect, url_for, current_app, session
from google.oauth2 import id_token
from google.auth.transport import requests
import os
import json
import logging
from config.settings import get_session
from models.user import User
from flask_jwt_extended import create_access_token
import secrets
import string

google_auth_bp = Blueprint('google_auth', __name__)
logger = logging.getLogger(__name__)

# Configuración de Google OAuth
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://www.plubot.com')

# Determinar si estamos en producción o desarrollo
IS_PRODUCTION = os.getenv('FLASK_ENV', 'production') == 'production'

def generate_random_password(length=16):
    """Genera una contraseña aleatoria segura"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

@google_auth_bp.route('/google/login', methods=['GET'])
def get_google_auth_url():
    """Devuelve la URL para iniciar el flujo de autenticación con Google"""
    try:
        # Verificar que las credenciales de Google estén configuradas
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            logger.error("Credenciales de Google OAuth no configuradas")
            return jsonify({
                'status': 'error',
                'message': 'Servicio de autenticación con Google no disponible'
            }), 500
        
        # Generar un estado para prevenir ataques CSRF
        state = secrets.token_urlsafe(16)
        session['google_auth_state'] = state
        
        # Construir la URL de autorización de Google
        # Usar una URL fija para evitar problemas de redirect_uri_mismatch
        redirect_uri = f"{FRONTEND_URL}/auth/google/callback"
        
        # Imprimir la URL de redirección para depuración
        logger.info(f"URL de redirección para Google OAuth: {redirect_uri}")
        
        # Configurar los scopes necesarios
        scopes = [
            'openid',
            'email',
            'profile',
        ]
        scope_string = '%20'.join(scopes)
        
        # Construir la URL completa
        auth_url = f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={GOOGLE_CLIENT_ID}&redirect_uri={redirect_uri}&scope={scope_string}&state={state}&prompt=select_account"
        
        return jsonify({
            'status': 'success',
            'authUrl': auth_url
        })
    except Exception as e:
        logger.exception(f"Error al generar URL de autenticación con Google: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Error al generar URL de autenticación'
        }), 500

@google_auth_bp.route('/google/callback', methods=['GET'])
def google_callback():
    """Maneja la respuesta de Google después de la autenticación"""
    # Capturar errores de autenticación
    error = request.args.get('error')
    if error:
        error_description = request.args.get('error_description', 'Error desconocido')
        logger.error(f"Error de autenticación de Google: {error} - {error_description}")
        return jsonify({
            'status': 'error',
            'message': error_description or f'Error: {error}',
            'redirect_url': f"{FRONTEND_URL}/login?error={error}&error_description={error_description}"
        }), 400
    
    # Verificar el estado para prevenir ataques CSRF
    state = request.args.get('state')
    stored_state = session.get('google_auth_state')
    if not state or state != stored_state:
        logger.error("Estado inválido en la respuesta de Google")
        return jsonify({
            'status': 'error',
            'message': 'Estado inválido en la respuesta de Google',
            'redirect_url': f"{FRONTEND_URL}/login?error=invalid_state"
        }), 400
    
    # Obtener el código de autorización
    code = request.args.get('code')
    if not code:
        logger.error("No se recibió código de autorización de Google")
        return jsonify({
            'status': 'error',
            'message': 'No se recibió código de autorización',
            'redirect_url': f"{FRONTEND_URL}/login?error=no_code"
        }), 400
    
    try:
        logger.info(f"Procesando código de autorización de Google: {code[:10]}...")
        
        # Intercambiar el código por un token de acceso
        # Usar la misma URL de redirección que se usó para la autorización
        redirect_uri = f"{FRONTEND_URL}/auth/google/callback"
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            'code': code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        # Hacer la solicitud para obtener el token
        import requests as req
        token_response = req.post(token_url, data=token_data)
        token_json = token_response.json()
        
        if 'error' in token_json:
            logger.error(f"Error al obtener token de Google: {token_json['error']}")
            return jsonify({
                'status': 'error',
                'message': f"Error al obtener token: {token_json.get('error_description', token_json['error'])}",
                'redirect_url': f"{FRONTEND_URL}/login?error=token_error&error_description={token_json.get('error_description', '')}"
            }), 400
        
        # Verificar el token ID
        id_info = id_token.verify_oauth2_token(
            token_json['id_token'], 
            requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        
        # Extraer información del usuario
        email = id_info.get('email')
        name = id_info.get('name')
        picture = id_info.get('picture')
        google_id = id_info.get('sub')  # ID único de Google
        
        if not email:
            logger.error("No se pudo obtener el email del usuario de Google")
            return jsonify({
                'status': 'error',
                'message': 'No se pudo obtener el email del usuario',
                'redirect_url': f"{FRONTEND_URL}/login?error=no_email"
            }), 400
        
        logger.info(f"Información de usuario de Google obtenida: {email}, {name}")
        
        # Verificar si el usuario ya existe en la base de datos
        with get_session() as session:
            user = session.query(User).filter_by(email=email).first()
            
            if user:
                # Usuario existente, actualizar información si es necesario
                logger.info(f"Usuario existente encontrado: {user.id}, {user.email}")
                if not user.google_id:
                    user.google_id = google_id
                    user.profile_picture = picture
                    session.commit()
                    logger.info(f"Actualizada información de Google para usuario: {user.id}")
            else:
                # Crear nuevo usuario
                logger.info(f"Creando nuevo usuario con email: {email}")
                random_password = generate_random_password()
                user = User(
                    email=email,
                    name=name or email.split('@')[0],
                    password=random_password,  # Contraseña aleatoria que el usuario no necesitará
                    is_verified=True,  # El email ya está verificado por Google
                    google_id=google_id,
                    profile_picture=picture
                )
                session.add(user)
                session.commit()
                logger.info(f"Nuevo usuario creado con ID: {user.id}")
            
            # Crear token JWT para el usuario
            access_token = create_access_token(identity=str(user.id))
            logger.info(f"Token JWT creado para usuario: {user.id}")
            
            # Devolver respuesta JSON con el token y la URL de redirección
            return jsonify({
                'status': 'success',
                'message': 'Autenticación con Google exitosa',
                'access_token': access_token,
                'redirect_url': f"{FRONTEND_URL}/auth/google/success?token={access_token}"
            })
            
    except Exception as e:
        logger.exception(f"Error en el proceso de autenticación con Google: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error en el proceso de autenticación: {str(e)}',
            'redirect_url': f"{FRONTEND_URL}/login?error=auth_error"
        }), 500

@google_auth_bp.route('/google/success', methods=['POST'])
def google_auth_success():
    """Endpoint para verificar y procesar el token después de la redirección"""
    try:
        token = request.json.get('token')
        if not token:
            return jsonify({'status': 'error', 'message': 'Token no proporcionado'}), 400
        
        # Aquí podrías hacer verificaciones adicionales si es necesario
        # Por ejemplo, verificar que el token sea válido
        
        # Obtener información del usuario a partir del token
        from flask_jwt_extended import decode_token
        try:
            user_id = decode_token(token)['sub']
            # Obtener datos del usuario
            with get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return jsonify({'status': 'error', 'message': 'Usuario no encontrado'}), 404
                
                # Devolver información del usuario junto con el token
                return jsonify({
                    'status': 'success',
                    'access_token': token,
                    'user': {
                        'id': user.id,
                        'name': user.name,
                        'email': user.email,
                        'profile_picture': user.profile_picture,
                        'is_verified': user.is_verified,
                        'role': user.role
                    },
                    'message': 'Autenticación con Google exitosa'
                })
        except Exception as e:
            logger.exception(f"Error al decodificar token: {str(e)}")
            return jsonify({'status': 'error', 'message': 'Token inválido'}), 401
    except Exception as e:
        logger.exception(f"Error al procesar token de Google: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
