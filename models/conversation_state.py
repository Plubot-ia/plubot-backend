from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from models import Base
from datetime import datetime

class ConversationState(Base):
    __tablename__ = 'conversation_states'

    id = Column(Integer, primary_key=True, autoincrement=True)
    plubot_id = Column(Integer, ForeignKey('plubots.id', ondelete='CASCADE'), nullable=False)
    
    # Identificador del contacto (ej. número de WhatsApp)
    contact_identifier = Column(String(100), nullable=False)
    
    # Nodo actual en el flujo
    current_node_id = Column(Integer, ForeignKey('flows.id'), nullable=False)
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    plubot = relationship("Plubot")
    current_node = relationship("Flow")

    # Índices para optimizar búsquedas
    __table_args__ = (
        Index('idx_conversation_plubot_contact', 'plubot_id', 'contact_identifier', unique=True),
    )

    def __repr__(self):
        return f'<ConversationState {self.id} for contact {self.contact_identifier} at node {self.current_node_id}>'
