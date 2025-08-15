"""Define el modelo de datos para el estado de una conversación."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from .flow import Flow
    from .plubot import Plubot


class ConversationState(Base):
    """Almacena el estado actual de una conversación para un contacto específico."""

    __tablename__ = "conversation_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plubot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plubots.id", ondelete="CASCADE"), nullable=False
    )

    contact_identifier: Mapped[str] = mapped_column(String(100), nullable=False)

    current_node_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("flows.id", ondelete="CASCADE"), nullable=False
    )

    # Campos de auditoría
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relaciones
    plubot: Mapped[Plubot] = relationship(back_populates="conversation_states")
    current_node: Mapped[Flow] = relationship(back_populates="conversation_states")

    # Índices para optimizar búsquedas
    __table_args__ = (
        Index(
            "idx_conversation_plubot_contact",
            "plubot_id",
            "contact_identifier",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        """Representación en string del objeto."""
        return f"<ConversationState {self.id} for contact {self.contact_identifier}>"
