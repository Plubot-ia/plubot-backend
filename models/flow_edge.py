"""Define el modelo de datos para un FlowEdge, una conexión entre nodos de flujo."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from .flow import Flow


class FlowEdge(Base):
    """Representa una arista (o conexión) entre dos nodos (Flow) en un flujo."""

    __tablename__ = "flow_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatbot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plubots.id", ondelete="CASCADE"), nullable=False
    )
    source_flow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("flows.id", ondelete="CASCADE"), nullable=False
    )
    target_flow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("flows.id", ondelete="CASCADE"), nullable=False
    )

    # Campos funcionales
    condition: Mapped[str] = mapped_column(Text, default="")
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Campos técnicos para UI
    edge_type: Mapped[str] = mapped_column(String(50), default="default")
    frontend_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_handle: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    target_handle: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    animated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Estilos y metadatos
    style: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    edge_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Campos de auditoría
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relaciones
    source_node: Mapped[Flow] = relationship(
        foreign_keys=[source_flow_id], back_populates="outgoing_edges"
    )
    target_node: Mapped[Flow] = relationship(
        foreign_keys=[target_flow_id], back_populates="incoming_edges"
    )

    # Índices para optimizar consultas
    __table_args__ = (
        Index("idx_flow_edge_chatbot", chatbot_id),
        Index("idx_flow_edge_source_target", chatbot_id, source_flow_id, target_flow_id),
        Index("idx_flow_edge_frontend_id", chatbot_id, frontend_id),
    )

    def __repr__(self) -> str:
        """Representación en string del objeto FlowEdge."""
        return f"<FlowEdge {self.id}: {self.source_flow_id} -> {self.target_flow_id}>"
