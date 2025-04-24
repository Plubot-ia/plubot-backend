from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from models import Base
from datetime import datetime

class Plubot(Base):
    __tablename__ = 'plubots'  # Actualizado: cambiar el nombre de la tabla a 'plubots'
    
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
    
    # Nuevos campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Nuevos campos para color y powers
    color = Column(String, nullable=True)  # Para almacenar el color en formato hexadecimal, ej. "#00e0ff"
    powers = Column(String, nullable=True)  # Para almacenar los poderes como una cadena separada por comas

    def __repr__(self):
        return f'<Plubot {self.name}>'