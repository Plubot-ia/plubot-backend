"""Inicialización de la base de datos y registro de modelos de la aplicación.

Este paquete contiene todas las definiciones de modelos de SQLAlchemy para la aplicación Plubot.
La instancia `db` se crea aquí y se importa en toda la aplicación para interactuar
con la base de datos. Todos los modelos se importan para que Flask-Migrate pueda
detectar cambios en el esquema.
"""
# ruff: noqa: E402

from flask_sqlalchemy import SQLAlchemy

db: SQLAlchemy = SQLAlchemy()
Base = db.Model

# Importar modelos para que Flask-Migrate los detecte y para exponerlos
from .conversation import Conversation
from .conversation_state import ConversationState
from .discord_integration import DiscordIntegration
from .flow import Flow
from .flow_edge import FlowEdge
from .knowledge_item import KnowledgeItem
from .message_quota import MessageQuota
from .plubot import Plubot
from .template import Template
from .user import User
from .whatsapp_connection import WhatsAppConnection

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
    "Template",
    "User",
    "WhatsAppConnection",
    "db",
]
