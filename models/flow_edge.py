from sqlalchemy import Column, Integer, Text, ForeignKey, String, DateTime, Boolean, JSON, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from models import Base
from datetime import datetime
import uuid

class FlowEdge(Base):
    __tablename__ = 'flow_edges'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chatbot_id = Column(Integer, ForeignKey('plubots.id', ondelete='CASCADE'), nullable=False)
    source_flow_id = Column(Integer, ForeignKey('flows.id', ondelete='CASCADE'), nullable=False)
    target_flow_id = Column(Integer, ForeignKey('flows.id', ondelete='CASCADE'), nullable=False)
    
    # Campos funcionales (separados claramente)
    condition = Column(Text, default="")  # Condición lógica
    label = Column(String(255), nullable=True)  # Etiqueta visible
    
    # Campos técnicos para UI
    edge_type = Column(String(50), default="default")
    frontend_id = Column(String(100), nullable=True, index=True)  # ID usado en el frontend
    source_handle = Column(String(50), nullable=True)  # Handle de origen
    target_handle = Column(String(50), nullable=True)  # Handle de destino
    
    # Estilos y metadatos
    style = Column(JSON, nullable=True)  # Estilos como JSON
    edge_metadata = Column(JSON, nullable=True)  # Metadatos adicionales
    
    # Campos de auditoría
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)  # Soft delete
    
    # Relaciones
    source_node = relationship("Flow", foreign_keys=[source_flow_id], back_populates="outgoing_edges")
    target_node = relationship("Flow", foreign_keys=[target_flow_id], back_populates="incoming_edges")
    
    # Índices para optimizar consultas
    __table_args__ = (
        Index('idx_flow_edge_chatbot', chatbot_id),
        Index('idx_flow_edge_source_target', chatbot_id, source_flow_id, target_flow_id),
        Index('idx_flow_edge_frontend_id', chatbot_id, frontend_id),
    )
    
    def __repr__(self):
        return f'<FlowEdge {self.id}: {self.source_flow_id} -> {self.target_flow_id}>'