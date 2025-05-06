from flask import Blueprint, jsonify, request, redirect, url_for
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity, create_access_token, set_access_cookies, unset_jwt_cookies, decode_token
from config.settings import get_session
from models.user import User
from models.plubot import Plubot
from models.flow import Flow
from models.flow_edge import FlowEdge  # Agregar esta línea
from utils.validators import LoginModel, RegisterModel
import bcrypt
from flask_mail import Mail, Message
from datetime import timedelta
import logging
import boto3
import os
import json
from werkzeug.utils import secure_filename

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)
mail = Mail()

# Configuración de S3 para fotos de perfil
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)
BUCKET_NAME = os.getenv('AWS_S3_BUCKET', 'plubot-profile-pics')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@auth_bp.record
def setup(state):
    mail.init_app(state.app)

@auth_bp.route('/register', methods=['POST', 'OPTIONS'])
def register():
    logger.info(f"Recibida solicitud para /api/auth/register con método {request.method}")
    if request.method == 'OPTIONS':
        logger.info("Respondiendo a solicitud OPTIONS para /api/auth/register")
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        data = RegisterModel(**request.form)
        logger.info(f"Datos recibidos: {data.email}")
        with get_session() as session:
            existing_user = session.query(User).filter_by(email=data.email).first()
            if existing_user:
                return jsonify({'status': 'error', 'message': 'El email ya está registrado'}), 400
            hashed_password = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user = User(email=data.email, password=hashed_password, name=data.name, is_verified=False)
            session.add(user)
            session.commit()

            verification_token = create_access_token(identity=str(user.id), expires_delta=timedelta(hours=24))
            verification_link = url_for('api.auth.verify_email', token=verification_token, _external=True)

            msg = Message(
                subject="Verifica tu correo - Plubot",
                recipients=[data.email],
                body=f"Hola,\n\nPor favor verifica tu correo haciendo clic en este enlace: {verification_link}\n\nEste enlace expira en 24 horas.\n\nSaludos,\nEl equipo de Plubot"
            )
            mail.send(msg)
            return jsonify({'status': 'success', 'message': 'Revisa tu correo para verificar tu cuenta.'}), 200
    except Exception as e:
        logger.exception(f"Error en /register: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@auth_bp.route('/verify_email/<token>', methods=['GET'])
def verify_email(token):
    try:
        decoded_token = decode_token(token)
        user_id = decoded_token['sub']
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'status': 'error', 'message': 'Usuario no encontrado.'}), 404
            if user.is_verified:
                return redirect('https://www.plubot.com/login?message=already_verified')
            user.is_verified = True
            session.commit()
            return redirect('https://www.plubot.com/login?message=verified')
    except Exception as e:
        logger.exception(f"Error al verificar correo: {str(e)}")
        return jsonify({'status': 'error', 'message': 'El enlace de verificación es inválido o ha expirado.'}), 400

@auth_bp.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        data = LoginModel(**request.form)
        logger.info(f"Email recibido en login: '{data.email}'")
        logger.info(f"Password recibido: '{data.password}'")
        with get_session() as session:
            user = session.query(User).filter_by(email=data.email).first()
            if not user:
                logger.info(f"No se encontró usuario con email: '{data.email}'")
                return jsonify({'status': 'error', 'message': 'Credenciales inválidas'}), 401
            logger.info(f"Password del usuario en la DB: '{user.password}'")
            if not data.password or not user.password:
                logger.info(f"Password nulo - data.password: {data.password}, user.password: {user.password}")
                return jsonify({'status': 'error', 'message': 'Credenciales inválidas'}), 401
            if not bcrypt.checkpw(data.password.encode('utf-8'), user.password.encode('utf-8')):
                logger.info("Contraseña incorrecta")
                return jsonify({'status': 'error', 'message': 'Credenciales inválidas'}), 401
            if not user.is_verified:
                return jsonify({'status': 'error', 'message': 'Por favor verifica tu correo antes de iniciar sesión.'}), 403
            access_token = create_access_token(identity=str(user.id))
            response = jsonify({
                'status': 'success',
                'message': 'Inicio de sesión exitoso',
                'access_token': access_token
            })
            set_access_cookies(response, access_token)
            return response, 200
    except Exception as e:
        logger.exception(f"Error en /login: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    response = jsonify({'message': 'Sesión cerrada'})
    unset_jwt_cookies(response)
    return response

@auth_bp.route('/forgot_password', methods=['POST', 'OPTIONS'])
def forgot_password():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    email = request.form.get('email')
    if email is None:
        logger.info("No se recibió email en la solicitud (email es None)")
        return jsonify({'status': 'error', 'message': 'Email no proporcionado.'}), 400
    logger.info(f"Email recibido en forgot_password: '{email}' (longitud: {len(email)})")
    logger.info(f"Tipo de email: {type(email)}")
    email = email.strip().lower()
    logger.info(f"Email normalizado: '{email}'")
    with get_session() as session:
        user = session.query(User).filter_by(email=email).first()
        if not user:
            logger.info(f"No se encontró usuario con email: '{email}'")
            all_emails = [u.email for u in session.query(User).all()]
            logger.info(f"Emails en la base de datos: {all_emails}")
            return jsonify({'status': 'error', 'message': 'No se encontró un usuario con ese correo.'}), 400
        token = create_access_token(identity=str(user.id), expires_delta=timedelta(hours=1))
        frontend_url = os.getenv('FRONTEND_URL', 'https://www.plubot.com')
        reset_link = f"{frontend_url}/reset-password/{token}"
        msg = Message(
            subject="Restablecer tu contraseña",
            recipients=[email],
            body=f"Hola,\n\nPara restablecer tu contraseña, haz clic en el siguiente enlace: {reset_link}\n\nSi no solicitaste esto, ignora este correo.\n\nSaludos,\nEl equipo de Plubot"
        )
        mail.send(msg)
        return jsonify({'status': 'success', 'message': 'Se ha enviado un enlace de restablecimiento a tu correo.'}), 200

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST', 'OPTIONS'])
def reset_password(token):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    if request.method == 'GET':
        return jsonify({'status': 'error', 'message': 'Por favor usa el frontend en http://localhost:5173'}), 400
    try:
        logger.info(f"Procesando reset_password para token: {token}")
        user_id = decode_token(token)['sub']
        logger.info(f"User ID decodificado: {user_id}")
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                logger.info(f"No se encontró usuario con ID: {user_id}")
                return jsonify({'status': 'error', 'message': 'Usuario no encontrado.'}), 404
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            logger.info(f"New password recibido: {'****' if new_password else 'None'}")
            logger.info(f"Confirm password recibido: {'****' if confirm_password else 'None'}")
            if not new_password or not confirm_password:
                return jsonify({'status': 'error', 'message': 'Se requieren ambas contraseñas.'}), 400
            if new_password != confirm_password:
                return jsonify({'status': 'error', 'message': 'Las contraseñas no coinciden.'}), 400
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            user.password = hashed_password.decode('utf-8')
            session.commit()
            logger.info(f"Contraseña actualizada para usuario {user.id}")
            return jsonify({'status': 'success', 'message': 'Contraseña restablecida con éxito.'}), 200
    except ExpiredSignatureError:
        logger.info("Token expirado")
        return jsonify({'status': 'error', 'message': 'El enlace ha expirado.'}), 400
    except Exception as e:
        logger.exception(f"Error en /reset_password: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@auth_bp.route('/change_password', methods=['POST', 'OPTIONS'])
@jwt_required()
def change_password():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    user_id = get_jwt_identity()
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    with get_session() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if not user or not bcrypt.checkpw(current_password.encode('utf-8'), user.password.encode('utf-8')):
            return jsonify({'status': 'error', 'message': 'La contraseña actual es incorrecta.'}), 400
        if new_password != confirm_password:
            return jsonify({'status': 'error', 'message': 'Las contraseñas nuevas no coinciden.'}), 400
        user.password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        session.commit()
        msg = Message(
            subject="Tu contraseña ha sido cambiada",
            recipients=[user.email],
            body="Hola,\n\nTu contraseña ha sido cambiada exitosamente.\n\nSi no realizaste este cambio, por favor contáctanos de inmediato.\n\nSaludos,\nEl equipo de Plubot"
        )
        mail.send(msg)
        return jsonify({'status': 'success', 'message': 'Contraseña cambiada con éxito.'}), 200

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    try:
        user_id = get_jwt_identity()
        print(f"Solicitud recibida en /profile, user_id: {user_id}")
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'status': 'error', 'message': 'Usuario no encontrado.'}), 404
            
            chatbots_data = [
                {
                    'id': bot.id,
                    'name': bot.name,
                    'tone': bot.tone,
                    'purpose': bot.purpose,
                    'whatsapp_number': bot.whatsapp_number,
                    'initial_message': bot.initial_message,
                    'business_info': bot.business_info,
                    'pdf_url': bot.pdf_url,
                    'image_url': bot.image_url,
                    'created_at': bot.created_at.isoformat() if bot.created_at else None,
                    'updated_at': bot.updated_at.isoformat() if bot.updated_at else None,
                    'color': bot.color,
                    'powers': bot.powers
                } for bot in user.plubots
            ]

            return jsonify({
                'status': 'success',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': user.name,
                    'profile_picture': user.profile_picture,
                    'bio': user.bio,
                    'preferences': user.preferences,
                    'level': user.level,
                    'plucoins': user.plucoins,
                    'role': user.role,
                    'powers': user.powers,
                    'is_verified': user.is_verified,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'updated_at': user.updated_at.isoformat() if user.updated_at else None,
                    'plubots': chatbots_data
                }
            }), 200
    except Exception as e:
        logger.exception(f"Error en /profile: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Error al obtener los datos del perfil.'}), 500

@auth_bp.route('/profile', methods=['PUT', 'OPTIONS'])
@jwt_required()
def update_profile():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        user_id = get_jwt_identity()
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'status': 'error', 'message': 'Usuario no encontrado.'}), 404

            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and allowed_file(file.filename):
                    try:
                        filename = secure_filename(f"{user_id}_{file.filename}")
                        s3_client.upload_fileobj(file, BUCKET_NAME, filename)
                        user.profile_picture = f"https://{BUCKET_NAME}.s3.amazonaws.com/{filename}"
                    except Exception as e:
                        logger.error(f"Error al subir la foto de perfil: {str(e)}")
                        return jsonify({'status': 'error', 'message': 'Error al subir la foto de perfil'}), 500
                else:
                    return jsonify({'status': 'error', 'message': 'Formato de archivo no permitido'}), 400

            if request.form:
                if 'name' in request.form and request.form['name']:
                    user.name = request.form['name']
                if 'bio' in request.form:
                    user.bio = request.form['bio']
                if 'preferences' in request.form:
                    try:
                        user.preferences = json.loads(request.form['preferences'])
                    except json.JSONDecodeError:
                        return jsonify({'status': 'error', 'message': 'Formato de preferencias inválido'}), 400

            session.commit()
            return jsonify({
                'status': 'success',
                'message': 'Perfil actualizado correctamente',
                'user': {
                    'profile_picture': user.profile_picture,
                    'name': user.name,
                    'bio': user.bio,
                    'preferences': user.preferences
                }
            }), 200
    except Exception as e:
        logger.exception(f"Error en /profile (PUT): {str(e)}")
        return jsonify({'status': 'error', 'message': 'Error al actualizar el perfil'}), 500

@auth_bp.route('/profile/powers', methods

=['POST', 'OPTIONS'])
@jwt_required()
def add_power():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        if not data or 'powerId' not in data:
            return jsonify({'status': 'error', 'message': 'Se requiere el ID del poder'}), 400
        
        power_id = data['powerId']
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'status': 'error', 'message': 'Usuario no encontrado.'}), 404
            
            if user.powers is None:
                user.powers = []
            
            if power_id in user.powers:
                return jsonify({'status': 'error', 'message': 'El poder ya está agregado'}), 400
            
            if len(user.powers) >= 3:
                return jsonify({'status': 'error', 'message': 'Límite de 3 poderes alcanzado'}), 400
            
            updated_powers = user.powers + [power_id]
            user.powers = updated_powers
            session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Poder agregado correctamente',
                'powers': user.powers
            }), 200
    except Exception as e:
        logger.exception(f"Error al agregar poder: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Error al agregar el poder'}), 500

@auth_bp.route('/profile/powers', methods=['DELETE', 'OPTIONS'])
@jwt_required()
def remove_power():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        if not data or 'powerId' not in data:
            return jsonify({'status': 'error', 'message': 'Se requiere el ID del poder'}), 400
        
        power_id = data['powerId']
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'status': 'error', 'message': 'Usuario no encontrado.'}), 404
            
            if user.powers is None:
                user.powers = []
            
            if power_id not in user.powers:
                return jsonify({'status': 'error', 'message': 'El poder no está en la lista'}), 400
            
            updated_powers = [p for p in user.powers if p != power_id]
            user.powers = updated_powers
            session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Poder eliminado correctamente',
                'powers': user.powers
            }), 200
    except Exception as e:
        logger.exception(f"Error al eliminar poder: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Error al eliminar el poder'}), 500

@auth_bp.route('/plubots', methods=['POST', 'OPTIONS'])
@jwt_required()
def create_plubot():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        powers = data.get('powers', '') if isinstance(data.get('powers'), str) else ','.join(data.get('powers', []))
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'status': 'error', 'message': 'Usuario no encontrado.'}), 404
            # Guardar credenciales de Google Sheets en User
            google_sheets_credentials = data.get('powerConfig', {}).get('google-sheets', {}).get('credentials')
            if google_sheets_credentials:
                user.google_sheets_credentials = google_sheets_credentials
            plubot = Plubot(
                name=data['name'],
                tone=data['tone'],
                purpose=data.get('purpose', 'asistir a los clientes'),
                initial_message=data.get('initial_message', '¡Hola! Soy tu Plubot, aquí para ayudarte.'),
                color=data.get('color'),
                powers=powers,
                user_id=user_id
            )
            session.add(plubot)
            session.commit()
            return jsonify({
                'status': 'success',
                'plubot': {
                    'id': plubot.id,
                    'name': plubot.name,
                    'tone': plubot.tone,
                    'color': plubot.color,
                    'powers': plubot.powers,
                    'purpose': plubot.purpose,
                    'initial_message': plubot.initial_message,
                    'created_at': plubot.created_at.isoformat() if plubot.created_at else None,
                    'updated_at': plubot.updated_at.isoformat() if plubot.updated_at else None
                }
            }), 200
    except Exception as e:
        logger.exception(f"Error al crear Plubot: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@auth_bp.route('/profile/plubots', methods=['DELETE', 'OPTIONS'])
@jwt_required()
def delete_plubot():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        if not data or 'plubotId' not in data:
            return jsonify({'status': 'error', 'message': 'Se requiere el ID del Plubot'}), 400
        
        plubot_id = data['plubotId']
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'status': 'error', 'message': 'Usuario no encontrado.'}), 404
            
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                return jsonify({'status': 'error', 'message': 'Plubot no encontrado o no pertenece al usuario.'}), 404
            
            # Eliminar primero los flow_edges asociados a los flujos del Plubot
            flows = session.query(Flow).filter_by(chatbot_id=plubot_id).all()
            flow_ids = [flow.id for flow in flows]
            if flow_ids:
                session.query(FlowEdge).filter(FlowEdge.source_flow_id.in_(flow_ids)).delete(synchronize_session=False)
            
            # Eliminar todos los flujos asociados al Plubot
            session.query(Flow).filter_by(chatbot_id=plubot_id).delete(synchronize_session=False)
            
            # Eliminar el Plubot
            session.delete(plubot)
            session.commit()
            
            # Obtener la lista actualizada de Plubots
            updated_plubots = [
                {
                    'id': bot.id,
                    'name': bot.name,
                    'tone': bot.tone,
                    'purpose': bot.purpose,
                    'whatsapp_number': bot.whatsapp_number,
                    'initial_message': bot.initial_message,
                    'business_info': bot.business_info,
                    'pdf_url': bot.pdf_url,
                    'image_url': bot.image_url,
                    'created_at': bot.created_at.isoformat() if bot.created_at else None,
                    'updated_at': bot.updated_at.isoformat() if bot.updated_at else None,
                    'color': bot.color,
                    'powers': bot.powers
                } for bot in user.plubots
            ]
            
            return jsonify({
                'status': 'success',
                'message': 'Plubot eliminado correctamente',
                'plubots': updated_plubots
            }), 200
    except Exception as e:
        logger.exception(f"Error al eliminar Plubot: {str(e)}")
        if 'ForeignKeyViolation' in str(e):
            return jsonify({
                'status': 'error',
                'message': 'No se puede eliminar este Plubot porque tiene flujos con conexiones activas. Por favor, elimina las conexiones primero o contacta al soporte.'
            }), 400
        return jsonify({'status': 'error', 'message': 'Error al eliminar el Plubot'}), 500