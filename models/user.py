"""Define el modelo de datos para un Usuario en la aplicación Plubot."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.refresh_token import RefreshToken

    from .discord_integration import DiscordIntegration
    from .message_quota import MessageQuota
    from .plubot import Plubot


class User(Base):
    """Representa a un usuario del sistema."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="user")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Campos para autenticación con Google
    google_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    google_refresh_token: Mapped[str | None] = mapped_column(String, nullable=True)

    # Nuevos campos para el perfil
    profile_picture: Mapped[str | None] = mapped_column(String, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Campos de Discord
    discord_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    discord_username: Mapped[str | None] = mapped_column(String, nullable=True)

    # Campos de gamificación
    level: Mapped[int] = mapped_column(Integer, default=1)
    plucoins: Mapped[int] = mapped_column(Integer, default=0)

    # Campo para los poderes: se usa una lambda para evitar el antipatrón de
    # default mutable. La regla PIE807 se deshabilita intencionadamente.
    powers: Mapped[list] = mapped_column(JSON, default=lambda: [], nullable=False)  # noqa: PIE807

    # Campos de auditoría
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    # Campo para credenciales de Google Sheets
    google_sheets_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relaciones
    plubots: Mapped[list[Plubot]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    discord_integrations: Mapped[list[DiscordIntegration]] = relationship(
        back_populates="user",
        order_by="DiscordIntegration.id",
        cascade="all, delete-orphan",
    )
    message_quotas: Mapped[list[MessageQuota]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """Representación en string del objeto User."""
        return f"<User {self.email}>"
