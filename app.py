from datetime import UTC, datetime
import logging
import os
from typing import Any

import certifi
from extensions import db, jwt, limiter, mail, migrate

# Force restart - Clear SQLAlchemy metadata cache
# Deploy timestamp: 2024-08-16 15:00:00 - FORCE METADATA CLEAR
from flask import Flask, Response, jsonify, redirect, request
from flask_cors import CORS
from flask_jwt_extended.exceptions import NoAuthorizationError
from jwt.exceptions import ExpiredSignatureError, InvalidSignatureError
from werkzeug.exceptions import Unauthorized

from api import api_bp
from api.actions_api import actions_bp
from api.discord_integrations_api import discord_integrations_bp
from api.flow_api import flow_bp
from api.grok import grok_bp
from api.integrations import integrations_bp
from api.opinion import opinion_bp
from api.whatsapp_api import whatsapp_api_bp
from api.whatsapp_business_api import whatsapp_business_bp
from api.whatsapp_migration_api import whatsapp_migration_bp
from config.settings import load_config
from models.token_blocklist import TokenBlocklist
from models.user import User
from utils.logging import setup_logging
from utils.templates import load_initial_templates


def create_app() -> Flask:
    """Crea y configura una instancia de la aplicación Flask (Application Factory)."""
    setup_logging()
    logger = logging.getLogger(__name__)

    # Import all models to register them with SQLAlchemy
    from models import __all__  # noqa: F401
    from models.whatsapp_business import (  # noqa: F401
        WhatsAppBusiness,
        WhatsAppMessage,
        WhatsAppWebhookEvent,
    )

    app = Flask(__name__, instance_relative_config=True)
    load_config(app)

    register_extensions(app)
    register_blueprints(app)
    register_error_handlers(app)
    register_shell_context(app)
    register_commands(app)
    configure_cors(app)

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

    return app


def register_extensions(app: Flask) -> None:
    """Inicializa las extensiones de Flask con la aplicación."""
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)

    # Configuración de Limiter con manejo de SSL para Redis
    redis_url = app.config.get("REDIS_URL")
    if redis_url:
        app.config["RATELIMIT_STORAGE_URI"] = redis_url
        if redis_url.startswith("rediss://"):
            app.config["RATELIMIT_STORAGE_OPTIONS"] = {
                "ssl_cert_reqs": "required",
                "ssl_ca_certs": certifi.where(),
            }
    limiter.init_app(app)

    # Callbacks de JWT
    @jwt.token_in_blocklist_loader
    def check_if_token_in_blocklist(_jwt_header: dict, jwt_payload: dict) -> bool:
        jti = jwt_payload["jti"]
        token = db.session.query(TokenBlocklist.id).filter_by(jti=jti).scalar()
        return token is not None

    @jwt.user_lookup_loader
    def user_lookup_callback(
        _jwt_header: dict[str, Any], jwt_data: dict[str, Any]
    ) -> User | None:
        identity = jwt_data["sub"]
        user = db.session.get(User, identity)
        if not user:
            return None
        if user.password_changed_at:
            token_issued_at = datetime.fromtimestamp(jwt_data["iat"], tz=UTC)
            if token_issued_at < user.password_changed_at.replace(tzinfo=UTC):
                return None
        return user


def register_blueprints(app: Flask) -> None:
    """Registra los blueprints en la aplicación."""
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(grok_bp, url_prefix="/api")
    app.register_blueprint(actions_bp)
    app.register_blueprint(integrations_bp, url_prefix="/api/integrations")
    app.register_blueprint(opinion_bp, url_prefix="/api/opinion")
    app.register_blueprint(flow_bp, url_prefix="/api/flow")
    app.register_blueprint(discord_integrations_bp)
    app.register_blueprint(whatsapp_api_bp, url_prefix="/api")  # WhatsApp Web.js API
    app.register_blueprint(whatsapp_business_bp, url_prefix="/api")  # New WhatsApp Business API
    app.register_blueprint(whatsapp_migration_bp)  # WhatsApp Migration API

    # Rutas de conveniencia y catch-all
    @app.route("/create", methods=["GET", "POST"])
    def create() -> tuple[Response, int]:
        message = {
            "status": "info",
            "message": "Por favor usa el frontend en https://plubot.com/create",
        }
        return jsonify(message), 200

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def catch_all(path: str) -> tuple[Response, int]:
        if path.startswith("api/"):
            if "verify_email" in path:
                frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
                return redirect(f"{frontend_url}/login?message=verified")
            return (
                jsonify({"status": "error", "message": f"API route not found: {path}"}),
                404,
            )
        message = {
            "status": "error",
            "message": "Este es el backend de Plubot. Usa el frontend en https://plubot.com",
        }
        return jsonify(message), 404


def register_error_handlers(app: Flask) -> None:
    """Registra los manejadores de errores."""

    @jwt.unauthorized_loader
    def unauthorized_response() -> tuple[Response, int]:
        return redirect("https://plubot.com/login"), 302

    @app.errorhandler(NoAuthorizationError)
    @app.errorhandler(Unauthorized)
    @app.errorhandler(InvalidSignatureError)
    @app.errorhandler(ExpiredSignatureError)
    def handle_auth_error(e: Exception) -> tuple[Response, int]:
        logging.getLogger(__name__).warning("Authentication error: %s", e)
        return jsonify({"status": "error", "message": "No autorizado"}), 401


def register_shell_context(app: Flask) -> None:
    """Registra el contexto para el shell de Flask."""

    def shell_context() -> dict[str, Any]:
        return {"db": db, "User": User}

    app.shell_context_processor(shell_context)


def register_commands(app: Flask) -> None:
    """Registra comandos de Click para Flask."""

    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Crea las tablas de la base de datos."""
        with app.app_context():
            db.create_all()
            load_initial_templates()
        print("Base de datos inicializada.")  # noqa: T201


def configure_cors(app: Flask) -> None:
    """Configura CORS para la aplicación."""
    if app.config.get("ENV") == "development":
        origins = "*"
        methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
        allow_headers = ["Content-Type", "Authorization", "X-Requested-With", "Accept"]
    else:
        origins = [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://192.168.0.213:5173",
            "https://www.plubot.com",
            "https://plubot.com",
            "https://plubot-frontend.vercel.app",
            "https://staging.plubot.com",
        ]
        methods = ["GET", "POST", "OPTIONS", "PUT", "DELETE", "PATCH"]
        allow_headers = ["Content-Type", "Authorization"]

    CORS(
        app,
        resources={r"/*": {"origins": origins}},
        supports_credentials=True,
        methods=methods,
        allow_headers=allow_headers,
        expose_headers=["Content-Type", "Authorization"],
    )


# Create app instance for Gunicorn
# Force restart - 2024-08-17 01:05:00
app = create_app()
