from pydantic import BaseModel, Field, ValidationError, RootModel
from typing import Optional
import re

class LoginModel(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)

class RegisterModel(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    name: Optional[str] = Field(None, min_length=1)  # Campo opcional, mínimo 1 carácter si se proporciona

class WhatsAppNumberModel(BaseModel):
    whatsapp_number: str

    @classmethod
    def validate_whatsapp_number(cls, value):
        if not re.match(r'^\+\d{10,15}$', value):
            raise ValueError('El número de WhatsApp debe tener el formato +1234567890')
        return value

class FlowModel(BaseModel):
    position: int = Field(..., ge=0)  # Nuevo: posición del flujo (entero no negativo)
    user_message: str = Field(..., min_length=1)
    bot_response: str = Field(..., min_length=1)
    intent: str = Field(default="general", min_length=1)
    condition: str = Field(default="", min_length=0)
    position_x: Optional[float] = None  # Nuevo: coordenada X, opcional
    position_y: Optional[float] = None  # Nuevo: coordenada Y, opcional

class MenuItemModel(BaseModel):
    precio: float = Field(..., gt=0)
    descripcion: str = Field(..., min_length=1)

class MenuModel(RootModel):
    root: dict[str, dict[str, MenuItemModel]]