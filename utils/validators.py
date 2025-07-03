import re

from pydantic import BaseModel, Field, RootModel


class LoginModel(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)

class RegisterModel(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    # Campo opcional, mínimo 1 carácter si se proporciona
    name: str | None = Field(None, min_length=1)


_INVALID_WHATSAPP_FORMAT_ERROR = (
    "El número de WhatsApp debe tener el formato +1234567890"
)


class WhatsAppNumberModel(BaseModel):
    whatsapp_number: str

    @classmethod
    def validate_whatsapp_number(
        cls: type["WhatsAppNumberModel"], value: str
    ) -> str:
        if not re.match(r"^\+\d{10,15}$", value):
            raise ValueError(_INVALID_WHATSAPP_FORMAT_ERROR)
        return value

class FlowModel(BaseModel):
    position: int = Field(..., ge=0)  # Nuevo: posición del flujo (entero no negativo)
    user_message: str = Field(..., min_length=1)
    bot_response: str = Field(..., min_length=1)
    intent: str = Field(default="general", min_length=1)
    condition: str = Field(default="", min_length=0)
    position_x: float | None = None  # Nuevo: coordenada X, opcional
    position_y: float | None = None  # Nuevo: coordenada Y, opcional

class MenuItemModel(BaseModel):
    precio: float = Field(..., gt=0)
    descripcion: str = Field(..., min_length=1)

class MenuModel(RootModel):
    root: dict[str, dict[str, MenuItemModel]]
