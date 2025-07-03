"""Define el modelo de datos para la integración con Discord."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .user import User


class DiscordIntegration(Base):
    """Representa una integración de un Plubot con un servidor de Discord."""

    __tablename__ = "discord_integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    integration_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # TODO: Implementar un sistema de cifrado real para este campo.
    bot_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    guild_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_channel_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="inactive")
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relación bidireccional con el usuario
    user: Mapped[User] = relationship(back_populates="discord_integrations")

    def __repr__(self) -> str:
        """Representación en string del objeto DiscordIntegration."""
        return f"<DiscordIntegration {self.id} - {self.integration_name}>"
