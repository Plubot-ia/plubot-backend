from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Boolean
from models import Base
from sqlalchemy.orm import relationship
from datetime import datetime

class Plubot(Base):
    __tablename__ = 'plubots'
    
    # Campos existentes
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    tone = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    initial_message = Column(Text, nullable=False)
    whatsapp_number = Column(String, unique=True, nullable=True)
    business_info = Column(Text, nullable=True)
    pdf_url = Column(String, nullable=True)
    pdf_content = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Campos existentes actualizados
    color = Column(String, nullable=True)  # Para almacenar el color en formato hexadecimal, ej. "#00e0ff"
    powers = Column(JSON, nullable=True, default=list)  # Lista de poderes en JSON
    
    # Nuevos campos para Plubot Despierto
    plan_type = Column(String, nullable=True, default='free')  # 'free' o 'premium'
    avatar = Column(String, nullable=True)  # URL o nombre del avatar
    menu_options = Column(JSON, nullable=True, default=list)  # Hasta 3 botones: [{label: str, action: str}]
    response_limit = Column(Integer, nullable=True, default=100)  # Límite de 100 respuestas/mes
    conversation_count = Column(Integer, nullable=True, default=0)  # Estadísticas básicas
    message_count = Column(Integer, nullable=True, default=0)  # Estadísticas básicas
    is_webchat_enabled = Column(Boolean, nullable=True, default=True)  # Solo chat web
    power_config = Column(JSON, nullable=True, default=dict)  # Configuración de poderes
    
    # Nuevos campos para embebido
    public_id = Column(String, unique=True, nullable=True)  # ID público para acceso al chatbot embebido
    embed_config = Column(JSON, nullable=True, default=dict)  # Configuración de embebido (tema, posición, etc.)
    is_embeddable = Column(Boolean, nullable=True, default=True)  # Si se permite embeber el chatbot
    embed_domains = Column(JSON, nullable=True, default=list)  # Dominios permitidos para embeber
    qr_code_url = Column(String, nullable=True)  # URL del código QR generado

    # Relación con la conexión de WhatsApp
    whatsapp_connection = relationship('WhatsappConnection', back_populates='plubot', uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Plubot {self.name}>'