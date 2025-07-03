"""Define el modelo de datos para una Conversación en la base de datos."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .plubot import Plubot


class Conversation(Base):
    """Representa un único mensaje dentro de una conversación con un Plubot."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatbot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plubots.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # p. ej., 'user' o 'assistant'
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relación bidireccional con Plubot
    plubot: Mapped[Plubot] = relationship("Plubot", back_populates="conversations")

    def __repr__(self) -> str:
        """Representación en string del objeto Conversation."""
        return f"<Conversation {self.id} from user {self.user_id}>"
