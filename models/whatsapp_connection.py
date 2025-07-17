"""Define el modelo de datos para la conexión con WhatsApp."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from .plubot import Plubot


class WhatsAppConnection(Base):
    """Representa el estado de la conexión de un Plubot con WhatsApp."""

    __tablename__ = "whatsapp_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plubot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plubots.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="disconnected")
    whatsapp_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    qr_code_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Campos de auditoría
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relación uno a uno con Plubot
    plubot: Mapped[Plubot] = relationship(
        "Plubot", back_populates="whatsapp_connection", uselist=False
    )

    def __repr__(self) -> str:
        """Representación en string del objeto WhatsAppConnection."""
        return f"<WhatsAppConnection {self.id} for Plubot {self.plubot_id} ({self.status})>"
