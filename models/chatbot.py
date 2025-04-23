from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from models import Base
from datetime import datetime

class Chatbot(Base):
    __tablename__ = 'chatbots'
    
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

    def __repr__(self):
        return f'<Chatbot {self.name}>'