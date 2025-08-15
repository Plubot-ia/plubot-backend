from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from flask import Flask

# Cargar el archivo .env desde la carpeta "instance" ANTES de definir la config
dotenv_path = Path(__file__).parent.parent / "instance/.env"
load_dotenv(dotenv_path)

logger = logging.getLogger(__name__)


class Settings:
    """Carga y valida las configuraciones de la aplicación desde variables de entorno."""

    # Constants for error messages
    MISSING_SECRET_KEY_ERROR = "No se encontró SECRET_KEY en las variables de entorno."
    MISSING_DATABASE_URL_ERROR = "No se encontró DATABASE_URL en las variables de entorno."
    MISSING_XAI_API_KEY_ERROR = "No se encontró XAI_API_KEY en las variables de entorno."
    MISSING_ENCRYPTION_KEY_ERROR = "No se encontró ENCRYPTION_KEY en las variables de entorno."
    OPINION_RECIPIENT_EMAIL_ERROR = (
        "No se encontró OPINION_RECIPIENT_EMAIL en las variables de entorno."
    )
    MISSING_BACKEND_URL_ERROR = "No se encontró BACKEND_URL en las variables de entorno."

    def __init__(self) -> None:
        # Flask
        self.SECRET_KEY: str | None = os.getenv("SECRET_KEY")

        # Database
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "").replace(
            "postgres://", "postgresql://"
        )

        # Redis
        self.REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        # JWT
        self.JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "super-secret")
        self.JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(hours=1)
        self.JWT_TOKEN_LOCATION: list[str] = ["headers"]

        # Mail
        self.MAIL_SERVER: str | None = os.getenv("MAIL_SERVER")
        self.MAIL_PORT: int = int(os.getenv("MAIL_PORT", "587"))
        self.MAIL_USE_TLS: bool = os.getenv("MAIL_USE_TLS", "True").lower() in (
            "true",
            "1",
            "t",
        )
        self.MAIL_USE_SSL: bool = os.getenv("MAIL_USE_SSL", "False").lower() in (
            "true",
            "1",
            "t",
        )
        self.MAIL_USERNAME: str | None = os.getenv("MAIL_USERNAME")
        self.MAIL_PASSWORD: str | None = os.getenv("MAIL_PASSWORD")
        self.MAIL_DEFAULT_SENDER: str | None = (
            os.getenv("MAIL_DEFAULT_SENDER") or self.MAIL_USERNAME
        )

        # APIs & Keys
        self.XAI_API_KEY: str | None = os.getenv("XAI_API_KEY")
        self.ENCRYPTION_KEY: str | None = os.getenv("ENCRYPTION_KEY")
        self.OPINION_RECIPIENT_EMAIL: str | None = os.getenv("OPINION_RECIPIENT_EMAIL")
        self.BACKEND_URL: str | None = os.getenv("BACKEND_URL")
        self.WHATSAPP_API_URL: str | None = os.getenv("WHATSAPP_API_URL")
        self.WHATSAPP_API_KEY: str | None = os.getenv("WHATSAPP_API_KEY")

        # WhatsApp Business API (Official)
        self.FACEBOOK_APP_ID: str | None = os.getenv("FACEBOOK_APP_ID")
        self.FACEBOOK_APP_SECRET: str | None = os.getenv("FACEBOOK_APP_SECRET")
        self.WHATSAPP_WEBHOOK_VERIFY_TOKEN: str | None = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN")
        self.WHATSAPP_REDIRECT_URI: str | None = os.getenv("WHATSAPP_REDIRECT_URI")
        
        # Twilio
        self.TWILIO_ACCOUNT_SID: str | None = os.getenv("TWILIO_ACCOUNT_SID")
        self.TWILIO_AUTH_TOKEN: str | None = os.getenv("TWILIO_AUTH_TOKEN")
        self.TWILIO_WHATSAPP_NUMBER: str | None = os.getenv("TWILIO_WHATSAPP_NUMBER")

        self._validate()

    def _validate(self) -> None:
        """Valida que las configuraciones críticas existan."""
        if not self.SECRET_KEY:
            raise ValueError(self.MISSING_SECRET_KEY_ERROR)
        if not self.DATABASE_URL:
            raise ValueError(self.MISSING_DATABASE_URL_ERROR)
        if not self.XAI_API_KEY:
            raise ValueError(self.MISSING_XAI_API_KEY_ERROR)
        if not self.ENCRYPTION_KEY:
            raise ValueError(self.MISSING_ENCRYPTION_KEY_ERROR)
        if not self.OPINION_RECIPIENT_EMAIL:
            raise ValueError(self.OPINION_RECIPIENT_EMAIL_ERROR)
        if not self.BACKEND_URL:
            raise ValueError(self.MISSING_BACKEND_URL_ERROR)

        if not all([self.WHATSAPP_API_URL, self.WHATSAPP_API_KEY]):
            logger.warning(
                "Faltan las credenciales de la API de WhatsApp. La integración no funcionará."
            )

        if not all([self.TWILIO_ACCOUNT_SID, self.TWILIO_AUTH_TOKEN, self.TWILIO_WHATSAPP_NUMBER]):
            logger.warning(

                    "Faltan una o más credenciales de Twilio. "
                    "La integración con WhatsApp no funcionará."

            )

        if not all([self.MAIL_SERVER, self.MAIL_USERNAME, self.MAIL_PASSWORD]):
            logger.warning(
                "Faltan variables de config de correo. El envío de correos estará deshabilitado."
            )


# Instancia única y centralizada de la configuración
settings = Settings()


def load_config(app: "Flask") -> None:
    """Carga la configuración desde el objeto settings a la app de Flask."""
    app.config["SECRET_KEY"] = settings.SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["DATABASE_URL"] = settings.DATABASE_URL
    app.config["REDIS_URL"] = settings.REDIS_URL
    app.config["JWT_SECRET_KEY"] = settings.JWT_SECRET_KEY
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = settings.JWT_ACCESS_TOKEN_EXPIRES
    app.config["JWT_TOKEN_LOCATION"] = settings.JWT_TOKEN_LOCATION
    app.config["MAIL_SERVER"] = settings.MAIL_SERVER
    app.config["MAIL_PORT"] = settings.MAIL_PORT
    app.config["MAIL_USE_TLS"] = settings.MAIL_USE_TLS
    app.config["MAIL_USE_SSL"] = settings.MAIL_USE_SSL
    app.config["MAIL_USERNAME"] = settings.MAIL_USERNAME
    app.config["MAIL_PASSWORD"] = settings.MAIL_PASSWORD
    app.config["MAIL_DEFAULT_SENDER"] = settings.MAIL_DEFAULT_SENDER
    app.config["XAI_API_KEY"] = settings.XAI_API_KEY
    app.config["ENCRYPTION_KEY"] = settings.ENCRYPTION_KEY
    app.config["OPINION_RECIPIENT_EMAIL"] = settings.OPINION_RECIPIENT_EMAIL
    app.config["BACKEND_URL"] = settings.BACKEND_URL
    app.config["WHATSAPP_API_URL"] = settings.WHATSAPP_API_URL
    app.config["WHATSAPP_API_KEY"] = settings.WHATSAPP_API_KEY
    
    # WhatsApp Business API (Official)
    app.config["FACEBOOK_APP_ID"] = settings.FACEBOOK_APP_ID
    app.config["FACEBOOK_APP_SECRET"] = settings.FACEBOOK_APP_SECRET
    app.config["WHATSAPP_WEBHOOK_VERIFY_TOKEN"] = settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN
    app.config["WHATSAPP_REDIRECT_URI"] = settings.WHATSAPP_REDIRECT_URI

    # Twilio
    app.config["TWILIO_ACCOUNT_SID"] = settings.TWILIO_ACCOUNT_SID
    app.config["TWILIO_AUTH_TOKEN"] = settings.TWILIO_AUTH_TOKEN
    app.config["TWILIO_WHATSAPP_NUMBER"] = settings.TWILIO_WHATSAPP_NUMBER


# Configuración de SQLAlchemy para uso fuera de Flask (si es necesario)
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


@contextmanager
def get_session() -> Iterator[Session]:
    """Provee una sesión de SQLAlchemy con manejo automático de commit/rollback."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
