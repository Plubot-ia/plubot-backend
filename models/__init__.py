# plubot-backend/models/__init__.py
from flask_sqlalchemy import SQLAlchemy

# Instancia de SQLAlchemy
db = SQLAlchemy()

# Base para los modelos
Base = db.Model

# Importar modelos para que Flask-Migrate los detecte
from .user import User
from .plubot import Plubot
from .conversation import Conversation
from .flow import Flow
from .flow_edge import FlowEdge
from .template import Template
from .message_quota import MessageQuota
from .knowledge_item import KnowledgeItem  # Añadir esta línea