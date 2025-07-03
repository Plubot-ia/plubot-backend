import io
import logging
import os

from celery import Celery
import PyPDF2
import requests

from config.settings import get_session
from models.plubot import Plubot

logger = logging.getLogger(__name__)

# Configuración de Celery
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery(
    "tasks",
    broker=REDIS_URL,
    backend=REDIS_URL.replace("/0", "/1"),
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    broker_pool_limit=3,
    result_expires=3600,
    broker_transport_options={
        "max_retries": 5,
        "interval_start": 2,
        "interval_step": 2,
        "interval_max": 30,
    },
    result_backend_transport_options={
        "retry_policy": {
            "max_retries": 5,
            "interval_start": 2,
            "interval_step": 2,
            "interval_max": 30,
        },
    },
)


def extract_text_from_pdf(file_stream: bytes) -> str:
    """Extrae texto de un stream de bytes de un archivo PDF."""
    text = ""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_stream))
        for page in reader.pages:
            text += page.extract_text() or ""
    except PyPDF2.errors.PdfReadError:
        logger.exception("Error al procesar el archivo PDF.")
        return ""
    else:
        return text


@celery_app.task
def process_pdf_async(chatbot_id: str, pdf_url: str) -> None:
    """Descarga y procesa un archivo PDF de forma asíncrona."""
    with get_session() as session:
        try:
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Error al descargar el PDF desde la URL: %s", pdf_url)
            return

        pdf_content = extract_text_from_pdf(response.content)
        plubot = session.query(Plubot).filter_by(id=chatbot_id).first()
        if plubot:
            plubot.pdf_content = pdf_content
            session.commit()
            logger.info("PDF procesado y guardado para plubot %s", chatbot_id)
        else:
            logger.warning("No se encontró el plubot con id %s", chatbot_id)
