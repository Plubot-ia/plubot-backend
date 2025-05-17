from sqlalchemy import Column, Integer, String, Boolean, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from models import Base
from datetime import datetime

class User(Base):
    __tablename__ = 'users'
    
    # Campos existentes
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    name = Column(String, nullable=True)
    role = Column(String, default='user')
    is_verified = Column(Boolean, default=False)
    
    # Campos para autenticación con Google
    google_id = Column(String, unique=True, nullable=True)
    google_refresh_token = Column(String, nullable=True)
    
    # Nuevos campos para el perfil
    profile_picture = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    preferences = Column(JSON, nullable=True)
    
    # Campos de gamificación
    level = Column(Integer, default=1)
    plucoins = Column(Integer, default=0)  # Revertido a plucoins
    
    # Campo para los poderes
    powers = Column(JSON, default=list, nullable=False)  # Lista de IDs de poderes
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Campo para credenciales de Google Sheets
    google_sheets_credentials = Column(Text, nullable=True)  # Para almacenar JSON de credenciales
    
    # Relaciones
    plubots = relationship('Plubot', backref='user', lazy=True)  # Actualizado: usar Plubot

    def __repr__(self):
        return f'<User {self.email}>'