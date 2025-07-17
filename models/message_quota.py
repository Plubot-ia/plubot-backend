"""Define el modelo de datos para la cuota de mensajes de un usuario."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from .user import User


class MessageQuota(Base):
    """Almacena la cuota de mensajes consumidos por un usuario en un mes específico."""

    __tablename__ = "message_quotas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # Formato: YYYY-MM
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free", nullable=False)

    # Campos de auditoría
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relación bidireccional con el usuario
    user: Mapped[User] = relationship("User", back_populates="message_quotas")

    __table_args__ = (UniqueConstraint("user_id", "month", name="_user_month_uc"),)

    def __repr__(self) -> str:
        """Representación en string del objeto MessageQuota."""
        return f"<MessageQuota {self.user_id} - {self.month}: {self.message_count}>"
