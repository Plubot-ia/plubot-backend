import json
import logging
import os
from typing import Any

from ratelimit import limits, sleep_and_retry
import redis
from redis.backoff import ExponentialBackoff
from redis.connection import ConnectionPool
from redis.retry import Retry
import requests

logger = logging.getLogger(__name__)

# Configuración de Redis: la librería gestiona la reconexión con el pool.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def get_redis_client() -> redis.Redis | None:
    """Inicializa y devuelve un cliente de Redis si la URL está configurada."""
    if not REDIS_URL:
        logger.warning(
            "La URL de Redis no está configurada. El servicio de caché estará deshabilitado."
        )
        return None
    try:
        # Configurar reintentos con backoff exponencial
        retry_strategy = Retry(ExponentialBackoff(cap=10, base=1), retries=5)

        # Crear un pool de conexiones desde la URL, ignorando la verificación SSL
        redis_pool = ConnectionPool.from_url(
            REDIS_URL,
            decode_responses=True,
            max_connections=20,
            retry=retry_strategy,
            retry_on_timeout=True,
            health_check_interval=30,
            socket_timeout=10,
            socket_connect_timeout=10,
            ssl_cert_reqs=None,  # Ignorar verificación SSL para desarrollo en macOS
        )

        # Crear el cliente desde el pool de conexiones
        client = redis.Redis(connection_pool=redis_pool)
        client.ping()  # Verificar conexión al inicializar
    except redis.exceptions.ConnectionError:
        logger.exception("No se pudo establecer la conexión inicial con Redis.")
        return None
    else:
        logger.info("Conexión con Redis establecida correctamente.")
        return client


redis_client = get_redis_client()


@sleep_and_retry
@limits(calls=50, period=60)
def detect_emotion(text_to_analyze: str) -> str:
    """Analiza el texto para detectar una emoción predominante.

    Utiliza un prompt específico y un modelo de lenguaje para clasificar el texto
    en una de las seis emociones básicas: 'joy', 'sadness', 'anger', 'fear',
    'surprise', 'disgust'.
    """
    system_prompt = (
        "Eres una IA experta en detección de emociones. Tu tarea es analizar el "
        "texto proporcionado e identificar la emoción predominante. Debes elegir "
        "una de las siguientes seis emociones: 'joy', 'sadness', 'anger', 'fear', "
        "'surprise', 'disgust'. No añadas texto extra, explicaciones ni "
        "puntuación. Tu respuesta debe ser una única palabra en minúsculas de la "
        "lista. Por ejemplo: `sadness`."
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text_to_analyze},
    ]

    emotion = call_grok(messages, max_tokens=10, temperature=0.3)

    valid_emotions = {"joy", "sadness", "anger", "fear", "surprise", "disgust"}
    cleaned_emotion = "".join(e for e in emotion if e.isalnum()).lower()

    if cleaned_emotion in valid_emotions:
        return cleaned_emotion

    return "joy"  # Fallback seguro


def call_grok(
    messages: list[dict[str, str]],
    max_tokens: int = 150,
    temperature: float = 0.5,
) -> str:
    """Llama a la API de Grok, utilizando una caché de Redis si está disponible."""
    if len(messages) > 10:
        messages = [messages[0], *messages[-9:]]

    cache_key = json.dumps(messages)

    # 1. Intentar recuperar desde la caché de Redis
    if redis_client:
        try:
            cached_result = redis_client.get(cache_key)
            if cached_result:
                logger.info("Respuesta obtenida desde caché de Redis.")
                return str(cached_result)
        except redis.exceptions.ConnectionError:
            logger.exception("Error al leer desde Redis. Se llamará a la API.")

    # 2. Si no está en caché, llamar a la API de xAI
    url = "https://api.x.ai/v1/chat/completions"
    api_key = os.getenv("XAI_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload: dict[str, Any] = {
        "model": "grok-3",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException:
        logger.exception("Error al conectar con la API de xAI.")
        return "Error al conectar con la IA. Intenta de nuevo más tarde."

    # 3. Intentar guardar el resultado en la caché de Redis
    if redis_client:
        try:
            redis_client.setex(cache_key, 3600, result)
            logger.info("Respuesta guardada en caché de Redis.")
        except redis.exceptions.ConnectionError:
            logger.exception("No se pudo guardar la respuesta en Redis.")

    return result
