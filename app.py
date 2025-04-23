from flask import Flask, jsonify, redirect, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, set_access_cookies
from flask_migrate import Migrate
from flask_mail import Mail
from werkzeug.exceptions import Unauthorized
from flask_jwt_extended.exceptions import NoAuthorizationError
import logging

from config.settings import load_config, get_session
from utils.logging import setup_logging
from utils.templates import load_initial_templates
from api import api_bp
from models import db

# Configuración de logging
setup_logging()
logger = logging.getLogger(__name__)

# Inicialización de la app
app = Flask(__name__)
load_config(app)  # Carga configuraciones de instance/.env, incluyendo MAIL_*

# Inicializar extensiones
db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)
mail = Mail(app)  # Inicializa Mail con configuraciones de instance/.env

# Configuración de CORS
CORS(app, resources={r"/*": {
    "origins": [
        "http://localhost:5173",
        "http://192.168.0.213:5173",
        "https://www.plubot.com",
        "https://plubot-frontend.vercel.app"
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
    return redirect('http://localhost:5173/login'), 302

@app.errorhandler(NoAuthorizationError)
@app.errorhandler(Unauthorized)
def handle_auth_error(e):
    logger.warning(f"Error de autenticación: {str(e)}")
    return jsonify({'status': 'error', 'message': 'No autorizado'}), 401

# Registro del blueprint de la API
app.register_blueprint(api_bp, url_prefix='/api')

@app.route('/create', methods=['GET', 'POST'])
def create():
    return jsonify({'status': 'info', 'message': 'Por favor usa el frontend en http://localhost:5173/create'}), 200

@app.route('/api/chatbots', methods=['GET', 'OPTIONS'])
def list_chatbots():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    from flask_jwt_extended import jwt_required, get_jwt_identity
    user_id = get_jwt_identity()
    from models.chatbot import Chatbot
    with get_session() as session:
        chatbots = session.query(Chatbot).filter_by(user_id=user_id).all()
        chatbots_list = [{
            'id': bot.id,
            'name': bot.name,
            'tone': bot.tone,
            'purpose': bot.purpose,
            'whatsapp_number': bot.whatsapp_number,
            'business_info': bot.business_info,
            'pdf_url': bot.pdf_url,
            'image_url': bot.image_url,
            'initial_message': bot.initial_message,
            'created_at': bot.created_at.isoformat() if bot.created_at else None,
            'updated_at': bot.updated_at.isoformat() if bot.updated_at else None
        } for bot in chatbots]
        return jsonify({'chatbots': chatbots_list}), 200

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    logger.info(f"Solicitud atrapada en catch_all: {request.method} {path}")
    return jsonify({'status': 'error', 'message': 'Por favor usa el frontend en http://localhost:5173'}), 404

# Solo cuando se ejecuta directamente
if __name__ == '__main__':
    with app.app_context():
        load_initial_templates()
    app.run(host='0.0.0.0', port=5000, debug=True)