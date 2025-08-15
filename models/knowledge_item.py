"""Define el modelo de datos para un item de la base de conocimiento."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from .plubot import Plubot


class KnowledgeItem(Base):
    """Representa una única entrada en la base de conocimiento de un Plubot."""

    __tablename__ = "knowledge_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plubot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plubots.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="General")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Campos de auditoría
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relación bidireccional con Plubot
    plubot: Mapped[Plubot] = relationship("Plubot")

    def __repr__(self) -> str:
        """Representación en string del objeto KnowledgeItem."""
        return f'<KnowledgeItem {self.id}: "{self.question[:30]}...">'
