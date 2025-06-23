from flask import Flask, request, jsonify, redirect # Added request, jsonify, redirect
from api.discord_api import discord_bp  # Added for Plubot Discord integration, jsonify, redirect, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, set_access_cookies
from flask_migrate import Migrate
from flask_mail import Mail
from werkzeug.exceptions import Unauthorized
from flask_jwt_extended.exceptions import NoAuthorizationError
from jwt.exceptions import InvalidSignatureError, ExpiredSignatureError
import logging

from config.settings import load_config, get_session
from utils.logging import setup_logging
from utils.templates import load_initial_templates
from api import api_bp
from models import db
from api.grok import grok_bp
from api.actions_api import actions_bp # Importar el nuevo blueprint de acciones
from api.integrations import integrations_bp
from api.opinion import opinion_bp
from api.flow_api import flow_bp  # Nuevo blueprint para la API de flujos optimizada
from api.discord_integrations_api import discord_integrations_bp # For user-managed Discord bot integrations
from api.whatsapp_api import whatsapp_api_bp # For QR-based WhatsApp integration

# Configuración de logging
setup_logging()
logger = logging.getLogger(__name__)

# Inicialización de la app
app = Flask(__name__)

# Register Plubot Discord API blueprint
app.register_blueprint(discord_bp)
load_config(app)

# Inicializar extensiones
db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)
mail = Mail(app)

# Import User model for JWT user lookup
from models.user import User

@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    """
    This callback is called when refreshing a token or when `fresh_jwt_required` or `jwt_required` is used.
    It will look up the user in the database and verify that the user still exists.
    """
    identity = jwt_data["sub"]
    user = db.session.get(User, identity) # Updated to use Session.get
    if not user:
        # You could log this event or raise an exception if a user is not found
        logger.warning(f"User lookup failed for identity: {identity}. User not found.")
        return None # Or raise UserNotFoundError() if you have a custom exception
    return user

# Configuración de CORS
if app.config.get('ENV') == 'development':
    # Configuración más permisiva para desarrollo
    CORS(app, resources={"/*": {
        "origins": "*",  # Permitir todos los orígenes en desarrollo
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "Accept"],
        "supports_credentials": True,
        "expose_headers": ["Content-Type", "Authorization"]
    }})
    
    # Log de todas las peticiones en desarrollo
    @app.before_request
    def log_request_info():
        logger.info(f'Request: {request.method} {request.path} Headers: {dict(request.headers)}')
else:
    # Configuración de producción
    CORS(app, resources={"/*": {
        "origins": [
            "http://localhost:5173",
            "http://192.168.0.213:5173",
            "https://www.plubot.com",
            "https://plubot.com",
            "https://plubot-frontend.vercel.app",
            "https://staging.plubot.com"
        ],
        "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True,
        "expose_headers": ["Content-Type", "Authorization"]
    }})

# Manejo de errores de autenticación
@jwt.unauthorized_loader
def unauthorized_response(callback):
    logger.info("Acceso no autorizado detectado")
    return redirect('https://plubot.com/login'), 302

@app.errorhandler(NoAuthorizationError)
@app.errorhandler(Unauthorized)
@app.errorhandler(InvalidSignatureError)
@app.errorhandler(ExpiredSignatureError)
def handle_auth_error(e):
    logger.warning(f"Error de autenticación: {str(e)}")
    return jsonify({'status': 'error', 'message': 'No autorizado'}), 401

# Registro de blueprints
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(grok_bp, url_prefix='/api')
app.register_blueprint(actions_bp) 
app.register_blueprint(integrations_bp, url_prefix='/api/integrations')
app.register_blueprint(opinion_bp, url_prefix='/api/opinion')
app.register_blueprint(flow_bp, url_prefix='/api/flow')  # Nuevo endpoint optimizado para flujos  # Nuevo registro
app.register_blueprint(discord_integrations_bp) # Registered with url_prefix in its definition
app.register_blueprint(whatsapp_api_bp, url_prefix='/api') # New WhatsApp API

@app.route('/create', methods=['GET', 'POST'])
def create():
    return jsonify({'status': 'info', 'message': 'Por favor usa el frontend en https://plubot.com/create'}), 200

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    # No capturar rutas que comiencen con /api
    if path.startswith('api/'):
        # Verificar si es una ruta de verificación de correo electrónico
        if 'verify_email' in path:
            # Obtener la URL base del frontend desde la configuración o usar una predeterminada
            frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
            # Extraer el token de la ruta
            token = path.split('/')[-1]
            # Redirigir al frontend con el token
            return redirect(f"{frontend_url}/login?message=verified")
        
        logger.warning(f"Ruta de API no encontrada: {request.method} {path}")
        return jsonify({'status': 'error', 'message': f'Ruta de API no encontrada: {path}'}), 404
    
    logger.info(f"Solicitud atrapada en catch_all: {request.method} {path}")
    return jsonify({'status': 'error', 'message': 'Este es el backend de Plubot. Usa el frontend en https://plubot.com'}), 404

# Solo cuando se ejecuta directamente
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        load_initial_templates()
        logger.info(f"XAI_API_KEY: {'set' if app.config.get('XAI_API_KEY') else 'not set'}")
        logger.info(f"REDIS_URL: {'set' if app.config.get('REDIS_URL') else 'not set'}")
    app.run(host='0.0.0.0', port=5000, debug=True)