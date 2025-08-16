"""Inicialización de la base de datos y registro de modelos de la aplicación.

Este paquete contiene todas las definiciones de modelos de SQLAlchemy para la aplicación Plubot.
La instancia `db` se crea aquí y se importa en toda la aplicación para interactuar
con la base de datos. Todos los modelos se importan para que Flask-Migrate pueda
detectar cambios en el esquema.
"""
# ruff: noqa: E402

from flask_sqlalchemy import SQLAlchemy

from .base import Base

# Inicializa SQLAlchemy con los metadatos de nuestra Base declarativa personalizada
# para que Flask-SQLAlchemy y Alembic puedan trabajar con ella.
db: SQLAlchemy = SQLAlchemy(metadata=Base.metadata)

# Importar modelos para que Flask-Migrate los detecte y para exponerlos
from .conversation import Conversation
from .conversation_state import ConversationState
from .discord_integration import DiscordIntegration
from .flow import Flow
from .flow_edge import FlowEdge
from .knowledge_item import KnowledgeItem
from .message_quota import MessageQuota
from .plubot import Plubot
from .refresh_token import RefreshToken
from .template import Template
from .token_blocklist import TokenBlocklist
from .user import User
from .whatsapp_connection import WhatsAppConnection
from .whatsapp_business import WhatsAppBusiness
from .whatsapp_webhook_event import WhatsAppWebhookEvent

__all__ = [
    "Base",
    "Conversation",
    "ConversationState",
    "DiscordIntegration",
    "Flow",
    "FlowEdge",
    "KnowledgeItem",
    "MessageQuota",
    "Plubot",
    "RefreshToken",
    "Template",
    "TokenBlocklist",
    "User",
    "WhatsAppConnection",
    "WhatsAppBusiness",
    "WhatsAppWebhookEvent",
    "db",
]
