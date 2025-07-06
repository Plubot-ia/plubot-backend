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

# Cargar el archivo .env desde la carpeta "instance"
dotenv_path = Path(__file__).parent.parent / "instance/.env"
load_dotenv(dotenv_path)

# Constants for error messages
MISSING_SECRET_KEY_ERROR = "No se encontró SECRET_KEY en las variables de entorno."
MISSING_DATABASE_URL_ERROR = "No se encontró DATABASE_URL en las variables de entorno."
MISSING_XAI_API_KEY_ERROR = "No se encontró XAI_API_KEY en las variables de entorno."
MISSING_ENCRYPTION_KEY_ERROR = "No se encontró ENCRYPTION_KEY en las variables de entorno."
OPINION_RECIPIENT_EMAIL_ERROR = (
    "No se encontró OPINION_RECIPIENT_EMAIL en las variables de entorno."
)
MISSING_BACKEND_URL_ERROR = "No se encontró BACKEND_URL en las variables de entorno."
DATABASE_URL_NOT_DEFINED_ERROR = "DATABASE_URL no está definido correctamente en el entorno."

logger = logging.getLogger(__name__)

def load_config(app: "Flask") -> None:
    """Carga las configuraciones de la aplicación y las aplica a Flask."""
    # --- CARGA DE CONFIGURACIONES ---

    # Configuraciones de Flask
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

    # Configuración de la base de datos para SQLAlchemy
    database_url = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["DATABASE_URL"] = database_url

    app.config["REDIS_URL"] = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Configuraciones de JWT
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "super-secret")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]

    # Configuraciones de Flask-Mail
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True") == "True"
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

    # Configuraciones de API
    app.config["XAI_API_KEY"] = os.getenv("XAI_API_KEY")

    # Configuración de la clave de encriptación
    app.config["ENCRYPTION_KEY"] = os.getenv("ENCRYPTION_KEY")

    # Configuración para el endpoint de opiniones
    app.config["OPINION_RECIPIENT_EMAIL"] = os.getenv("OPINION_RECIPIENT_EMAIL")

    # Backend URL for webhooks and other absolute links
    app.config["BACKEND_URL"] = os.getenv("BACKEND_URL")

    # Configuraciones de la API de WhatsApp (Whapi.Cloud)
    app.config["WHATSAPP_API_URL"] = os.getenv("WHATSAPP_API_URL")
    app.config["WHATSAPP_API_KEY"] = os.getenv("WHATSAPP_API_KEY")

    # --- VALIDACIONES ---
    if not app.config["SECRET_KEY"]:
        raise ValueError(MISSING_SECRET_KEY_ERROR)
    if not database_url:
        raise ValueError(MISSING_DATABASE_URL_ERROR)
    if not app.config["XAI_API_KEY"]:
        raise ValueError(MISSING_XAI_API_KEY_ERROR)
    if not app.config["ENCRYPTION_KEY"]:
        raise ValueError(MISSING_ENCRYPTION_KEY_ERROR)
    if not app.config["OPINION_RECIPIENT_EMAIL"]:
        raise ValueError(OPINION_RECIPIENT_EMAIL_ERROR)
    if not app.config["BACKEND_URL"]:
        raise ValueError(MISSING_BACKEND_URL_ERROR)

    whatsapp_url = app.config.get("WHATSAPP_API_URL")
    whatsapp_key = app.config.get("WHATSAPP_API_KEY")
    if not all([whatsapp_url, whatsapp_key]):
        logger.warning(
            "Faltan las credenciales de la API de WhatsApp. La integración no funcionará.",
        )

# Configuración de SQLAlchemy
database_url = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")
if not database_url:
    raise ValueError(DATABASE_URL_NOT_DEFINED_ERROR)
engine = create_engine(database_url)
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
