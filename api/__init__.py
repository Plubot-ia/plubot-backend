"""Initializes the API blueprint and registers all sub-blueprints."""

from flask import Blueprint

from .actions_api import actions_bp
from .auth import auth_bp
from .contact import contact_bp
from .conversations import conversations_bp
from .google_auth import google_auth_bp
from .plubots import plubots_bp
from .quotas import quotas_bp
from .subscribe import subscribe_bp
from .templates import templates_bp
from .webhook import webhook_bp
from .whatsapp import whatsapp_bp

api_bp = Blueprint("api", __name__)

# Register blueprints with their explicit prefixes
api_bp.register_blueprint(actions_bp)  # Prefix is defined in the blueprint
api_bp.register_blueprint(auth_bp, url_prefix="/auth")
api_bp.register_blueprint(contact_bp, url_prefix="/contact")
api_bp.register_blueprint(conversations_bp, url_prefix="/conversations")
api_bp.register_blueprint(google_auth_bp, url_prefix="/auth/google")
api_bp.register_blueprint(plubots_bp, url_prefix="/plubots")
api_bp.register_blueprint(quotas_bp, url_prefix="/quotas")
api_bp.register_blueprint(subscribe_bp, url_prefix="/subscribe")
api_bp.register_blueprint(templates_bp, url_prefix="/templates")
api_bp.register_blueprint(webhook_bp, url_prefix="/webhook")
api_bp.register_blueprint(whatsapp_bp, url_prefix="/whatsapp")
