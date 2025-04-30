from flask import Flask, jsonify, redirect, request
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

# Configuración de logging
setup_logging()
logger = logging.getLogger(__name__)

# Inicialización de la app
app = Flask(__name__)
load_config(app)

# Inicializar extensiones
db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)
mail = Mail(app)

# Configuración de CORS
CORS(app, resources={r"/*": {
    "origins": [
        "http://localhost:5173",
        "http://192.168.0.213:5173",
        "https://www.plubot.com",
        "https://plubot.com",  # Añadido para producción
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
from api.integrations import integrations_bp
app.register_blueprint(integrations_bp, url_prefix='/api/integrations')

@app.route('/create', methods=['GET', 'POST'])
def create():
    return jsonify({'status': 'info', 'message': 'Por favor usa el frontend en https://plubot.com/create'}), 200

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
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