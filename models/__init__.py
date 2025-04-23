from flask_sqlalchemy import SQLAlchemy

# Instancia de SQLAlchemy
db = SQLAlchemy()

# Base para los modelos
Base = db.Model

# Importar modelos para que Flask-Migrate los detecte
from .user import User
from .chatbot import Chatbot