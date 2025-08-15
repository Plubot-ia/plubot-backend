import re

from pydantic import BaseModel, Field, RootModel, field_validator
from pydantic.functional_validators import ModelWrapValidatorHandler
from pydantic_core import PydanticCustomError

_VALIDATION_ERROR_TYPE = "value_error"

class LoginModel(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)

def validate_password_strength(password: str, handler: ModelWrapValidatorHandler) -> str:
    """Valida la fortaleza de la contraseña y devuelve un error serializable."""
    errors = []
    if len(password) < 8:
        errors.append("debe tener al menos 8 caracteres")
    if not re.search(r"[A-Z]", password):
        errors.append("debe contener al menos una mayúscula")
    if not re.search(r"[0-9]", password):
        errors.append("debe contener al menos un número")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("debe contener al menos un carácter especial")

    if errors:
        error_message = f"La contraseña no es segura: {', '.join(errors)}."
        # Usamos PydanticCustomError para crear un error que SÍ es serializable a JSON.
        # Esto evita el TypeError en el backend.
        raise PydanticCustomError(
            _VALIDATION_ERROR_TYPE,
            error_message
        )

    # Si la contraseña es válida, la pasamos al siguiente validador o la retornamos.
    return handler(password)


class RegisterModel(BaseModel):
    email: str = Field(..., min_length=5)
    password: str
    name: str | None = Field(None, min_length=1)

    @field_validator("password", mode="wrap")
    @classmethod
    def validate_password(cls, password: str, handler: ModelWrapValidatorHandler) -> str:
        return validate_password_strength(password, handler)


class PasswordModel(BaseModel):
    """Modelo para validar una única contraseña."""
    password: str

    @field_validator("password", mode="wrap")
    @classmethod
    def validate_password(cls, password: str, handler: ModelWrapValidatorHandler) -> str:
        return validate_password_strength(password, handler)


_INVALID_WHATSAPP_FORMAT_ERROR = (
    "El número de WhatsApp debe tener el formato +1234567890"
)


class WhatsAppNumberModel(BaseModel):
    whatsapp_number: str

    @field_validator("whatsapp_number")
    @classmethod
    def validate_whatsapp_number(cls, v: str) -> str:
        """Valida que el número de WhatsApp tenga el formato correcto."""
        if not re.match(r"^\+\d{10,15}$", v):
            raise PydanticCustomError(_VALIDATION_ERROR_TYPE, _INVALID_WHATSAPP_FORMAT_ERROR)
        return v

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
