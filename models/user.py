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
    
    # Nuevos campos para el perfil
    profile_picture = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    preferences = Column(JSON, nullable=True)
    
    # Campos de gamificación
    level = Column(Integer, default=1)
    plucoins = Column(Integer, default=0)  # Revertido a plucoins
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    plubots = relationship('Chatbot', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.email}>'