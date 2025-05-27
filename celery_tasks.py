from celery import Celery
import os
import requests
import PyPDF2
import logging
from config.settings import get_session
from models.plubot import Plubot  # Actualizado: importar Plubot desde plubot.py

logger = logging.getLogger(__name__)

# Configuración de Celery
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
celery_app = Celery(
    'tasks',
    broker=REDIS_URL,
    backend=REDIS_URL.replace('/0', '/1')
)
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    broker_pool_limit=3,
    result_expires=3600,
    broker_transport_options={
        'max_retries': 5,
        'interval_start': 2,
        'interval_step': 2,
        'interval_max': 30
    },
    result_backend_transport_options={
        'retry_policy': {
            'max_retries': 5,
            'interval_start': 2,
            'interval_step': 2,
            'interval_max': 30
        }
    }
)

def extract_text_from_pdf(file_stream):
    try:
        reader = PyPDF2.PdfReader(file_stream)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        logger.error(f"Error al extraer texto del PDF: {str(e)}")
        return ""

@celery_app.task
def process_pdf_async(chatbot_id, pdf_url):
    with get_session() as session:
        response = requests.get(pdf_url)
        pdf_content = extract_text_from_pdf(response.content)
        plubot = session.query(Plubot).filter_by(id=chatbot_id).first()  # Actualizado: usar Plubot
        if plubot:
            plubot.pdf_content = pdf_content
            session.commit()
        logger.info(f"PDF procesado para plubot {chatbot_id}")  # Actualizado: mensaje de log