"""Define el modelo de datos para un Flow, un nodo en el flujo de conversación."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from .conversation_state import ConversationState
    from .flow_edge import FlowEdge


class Flow(Base):
    """Representa un único nodo (o paso) en un flujo de conversación de un Plubot."""

    __tablename__ = "flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatbot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plubots.id", ondelete="CASCADE"), nullable=False
    )

    # Campos de contenido
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    bot_response: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    intent: Mapped[str | None] = mapped_column(String)
    condition: Mapped[str] = mapped_column(Text, default="")
    actions: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)

    # Campos de posición
    position_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_y: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Campos para mejorar la persistencia
    frontend_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    node_type: Mapped[str] = mapped_column(String(50), default="message")
    node_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Campos de auditoría
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relaciones
    outgoing_edges: Mapped[list[FlowEdge]] = relationship(
        foreign_keys="FlowEdge.source_flow_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[list[FlowEdge]] = relationship(
        foreign_keys="FlowEdge.target_flow_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
    )
    conversation_states: Mapped[list[ConversationState]] = relationship(
        back_populates="current_node"
    )

    # Índices para optimizar consultas
    __table_args__ = (
        Index("idx_flow_chatbot_frontend", chatbot_id, frontend_id),
        Index("idx_flow_position", chatbot_id, position),
        Index("idx_flow_coordinates", chatbot_id, position_x, position_y),
    )

    def __repr__(self) -> str:
        """Representación en string del objeto Flow."""
        return f"<Flow {self.id}: {self.user_message[:20]}...>"
