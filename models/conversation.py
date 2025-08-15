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


class Conversation(Base):
    """Represents a single message in a conversation with a Plubot."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    chatbot_id = Column(Integer, ForeignKey("plubots.id"), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)  # Corresponds to user_phone
    message = Column(Text, nullable=False)
    role = Column(String(50), nullable=False)  # 'user' or 'bot'
    timestamp = Column(
        DateTime, nullable=False, default=datetime.datetime.utcnow
    )

    plubot = relationship("Plubot", back_populates="conversations")

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, chatbot_id={self.chatbot_id}, role='{self.role}')>"
