"""Define el modelo de datos para una plantilla de flujo."""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Template(Base):
    """Representa una plantilla de flujo predefinida que los usuarios pueden utilizar."""

    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    tone: Mapped[str] = mapped_column(String(50), nullable=False)
    purpose: Mapped[str] = mapped_column(String(100), nullable=False)
    # Almacena la estructura del flujo, probablemente en formato JSON.
    flows: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        """Representación en string del objeto Template."""
        return f"<Template {self.id}: {self.name}>"
