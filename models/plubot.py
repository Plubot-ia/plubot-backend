"""Define el modelo de datos para un Plubot, el chatbot personalizado."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from .conversation import Conversation
    from .conversation_state import ConversationState
    from .user import User
    from .whatsapp_connection import WhatsAppConnection


class Plubot(Base):
    """Representa un chatbot configurable asociado a un usuario."""

    __tablename__ = "plubots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tone: Mapped[str] = mapped_column(String, nullable=False)
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    initial_message: Mapped[str] = mapped_column(Text, nullable=False)
    whatsapp_number: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    business_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String, nullable=True)
    pdf_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Campos de auditoría
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Campos existentes actualizados
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    powers: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)

    # Nuevos campos para Plubot Despierto
    plan_type: Mapped[str | None] = mapped_column(String, nullable=True, default="free")
    avatar: Mapped[str | None] = mapped_column(String, nullable=True)
    menu_options: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    response_limit: Mapped[int | None] = mapped_column(Integer, nullable=True, default=100)
    conversation_count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    message_count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    is_webchat_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    power_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)

    # Nuevos campos para embebido
    public_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    embed_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    is_embeddable: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    embed_domains: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    qr_code_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relaciones
    user: Mapped[User] = relationship(back_populates="plubots")
    whatsapp_connection: Mapped[WhatsAppConnection | None] = relationship(
        back_populates="plubot", uselist=False, cascade="all, delete-orphan"
    )
    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation", back_populates="plubot", cascade="all, delete-orphan"
    )
    conversation_states: Mapped[list[ConversationState]] = relationship(
        back_populates="plubot", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """Representación en string del objeto Plubot."""
        return f"<Plubot {self.name}>"
