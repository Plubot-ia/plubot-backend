from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from flask import Flask, jsonify, redirect, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_jwt_extended.exceptions import NoAuthorizationError
from flask_mail import Mail
from flask_migrate import Migrate
from jwt.exceptions import ExpiredSignatureError, InvalidSignatureError
from werkzeug.exceptions import Unauthorized

if TYPE_CHECKING:
    from flask.wrappers import Response

# ==============================================================================
# 1. Inicialización y Configuración Centralizada
# ==============================================================================
# Es CRÍTICO cargar la configuración ANTES de importar los blueprints de la app
# que dependen de las variables de entorno.

from utils.logging import setup_logging

setup_logging()  # Configurar logging primero para ver todo el proceso
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Cargar la configuración desde config/settings.py, que a su vez carga instance/.env
from config.settings import load_config

load_config(app)

# ==============================================================================
# 2. Imports de la Aplicación (Ahora es seguro importarlos)
# ==============================================================================
from api import api_bp
from api.actions_api import actions_bp
from api.discord_api import discord_bp
from api.discord_integrations_api import discord_integrations_bp
from api.flow_api import flow_bp
from api.grok import grok_bp
from api.integrations import integrations_bp
from api.opinion import opinion_bp
from api.whatsapp_api import whatsapp_api_bp
from api.google_auth import google_auth_bp
from models import db
from models.user import User
from utils.templates import load_initial_templates

# ==============================================================================
# 3. Inicialización de Extensiones de Flask
# ==============================================================================
db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)
mail = Mail(app)


@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header: dict[str, Any], jwt_data: dict[str, Any]) -> User | None:
    """Look up user in the database and verify they still exist."""
    identity = jwt_data["sub"]
    user = db.session.get(User, identity)
    if not user:
        logger.warning("User lookup failed for identity: %s. User not found.", identity)
        return None
    return user


# Configuración de CORS
if app.config.get("ENV") == "development":
    # Configuración permisiva para desarrollo
    origins = "*"
    methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    allow_headers = [
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
    ]
else:
    # Configuración estricta para producción
    origins = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://192.168.0.213:5173",
        "https://www.plubot.com",
        "https://plubot.com",
        "https://plubot-frontend.vercel.app",
        "https://staging.plubot.com",
    ]
    methods = ["GET", "POST", "OPTIONS", "PUT", "DELETE"]
    allow_headers = ["Content-Type", "Authorization"]

CORS(
    app,
    resources={r"/*": {"origins": origins}},
    supports_credentials=True,
    methods=methods,
    allow_headers=allow_headers,
    expose_headers=["Content-Type", "Authorization"],
)

if app.config.get("ENV") == "development":

    @app.before_request
    def log_request_info() -> None:
        """Log all requests in development."""
        logger.info(
            "Request: %s %s Headers: %s",
            request.method,
            request.path,
            dict(request.headers),
        )


# Manejo de errores de autenticación
@jwt.unauthorized_loader
def unauthorized_response(callback: str) -> tuple[Response, int]:
    """Handle unauthorized access."""
    logger.info("Unauthorized access detected, redirecting to login. Callback: %s", callback)
    return redirect("https://plubot.com/login"), 302


@app.errorhandler(NoAuthorizationError)
@app.errorhandler(Unauthorized)
@app.errorhandler(InvalidSignatureError)
@app.errorhandler(ExpiredSignatureError)
def handle_auth_error(e: Exception) -> tuple[Response, int]:
    """Handle authentication errors."""
    logger.warning("Authentication error: %s", e)
    return jsonify({"status": "error", "message": "No autorizado"}), 401


# Registro de blueprints
app.register_blueprint(api_bp, url_prefix="/api")
app.register_blueprint(grok_bp, url_prefix="/api")
app.register_blueprint(actions_bp)
app.register_blueprint(integrations_bp, url_prefix="/api/integrations")
app.register_blueprint(opinion_bp, url_prefix="/api/opinion")
app.register_blueprint(flow_bp, url_prefix="/api/flow")
app.register_blueprint(discord_integrations_bp)
app.register_blueprint(whatsapp_api_bp, url_prefix="/api")
app.register_blueprint(google_auth_bp, url_prefix="/api")


@app.route("/create", methods=["GET", "POST"])
def create() -> tuple[Response, int]:
    """Redirect create endpoint to frontend."""
    message = {"status": "info", "message": "Por favor usa el frontend en https://plubot.com/create"}
    return jsonify(message), 200


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path: str) -> tuple[Response, int]:
    """Catch all other routes."""
    if path.startswith("api/"):
        if "verify_email" in path:
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
            return redirect(f"{frontend_url}/login?message=verified")

        logger.warning("API route not found: %s %s", request.method, path)
        return jsonify({"status": "error", "message": f"API route not found: {path}"}), 404

    logger.info("Catch-all route triggered: %s %s", request.method, path)
    message = {
        "status": "error",
        "message": "Este es el backend de Plubot. Usa el frontend en https://plubot.com",
    }
    return jsonify(message), 404


# Solo cuando se ejecuta directamente
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        load_initial_templates()
        logger.info(
            "XAI_API_KEY: %s", "set" if app.config.get("XAI_API_KEY") else "not set"
        )
        logger.info(
            "REDIS_URL: %s", "set" if app.config.get("REDIS_URL") else "not set"
        )
    # S104: Binding to all interfaces is intentional for development/containerized environments.
    # S201: Debug mode is intentional for development.
    app.run(host="0.0.0.0", port=5000, debug=True)  # noqa: S104, S201
