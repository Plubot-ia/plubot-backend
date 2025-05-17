from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Float, DateTime, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from models import Base
from datetime import datetime
import uuid

class Flow(Base):
    __tablename__ = 'flows'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chatbot_id = Column(Integer, ForeignKey('plubots.id', ondelete='CASCADE'), nullable=False)
    
    # Campos de contenido
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    position = Column(Integer, nullable=False)  # Mantener para compatibilidad
    intent = Column(String)
    condition = Column(Text, default="")
    actions = Column(JSON, nullable=True)
    
    # Campos de posición
    position_x = Column(Float, nullable=True)
    position_y = Column(Float, nullable=True)
    
    # Campos para mejorar la persistencia
    frontend_id = Column(String(100), nullable=True, index=True)  # ID usado en el frontend
    node_type = Column(String(50), default="message")  # Tipo de nodo
    node_metadata = Column(JSON, nullable=True)  # Metadatos adicionales
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)  # Soft delete
    
    # Relaciones
    outgoing_edges = relationship("FlowEdge", foreign_keys="FlowEdge.source_flow_id", 
                                 back_populates="source_node", cascade="all, delete-orphan")
    incoming_edges = relationship("FlowEdge", foreign_keys="FlowEdge.target_flow_id", 
                                back_populates="target_node", cascade="all, delete-orphan")
    
    # Índices para optimizar consultas
    __table_args__ = (
        Index('idx_flow_chatbot_frontend', chatbot_id, frontend_id),
        Index('idx_flow_position', chatbot_id, position),
        Index('idx_flow_coordinates', chatbot_id, position_x, position_y),
    )
    
    def __repr__(self):
        return f'<Flow {self.id}: {self.user_message[:20]}...>'