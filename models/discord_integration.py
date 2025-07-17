from __future__ import annotations

import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .base import Base


class DiscordIntegration(Base):
    __tablename__ = "discord_integrations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    integration_name = Column(String(255), nullable=False)
    bot_token_encrypted = Column(Text, nullable=False)
    guild_id = Column(String(255), nullable=True)
    default_channel_id = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="pending_verification", index=True)
    last_error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    user = relationship("User", back_populates="discord_integrations")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "integration_name": self.integration_name,
            "guild_id": self.guild_id,
            "default_channel_id": self.default_channel_id,
            "status": self.status,
            "last_error_message": self.last_error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"<DiscordIntegration(id={self.id}, "
            f"name='{self.integration_name}', status='{self.status}')>"
        )
