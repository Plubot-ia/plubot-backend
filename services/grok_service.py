import requests
import json
import time
import redis
import logging
from config.settings import get_session
from ratelimit import limits, sleep_and_retry
from redis.connection import ConnectionPool
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
import os

logger = logging.getLogger(__name__)

# Configuración de Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
retry = Retry(ExponentialBackoff(cap=10, base=1), retries=5)
redis_pool = ConnectionPool.from_url(
    REDIS_URL,
    decode_responses=True,
    max_connections=10,
    retry=retry,
    retry_on_timeout=True,
    health_check_interval=30,
    socket_timeout=10,
    socket_connect_timeout=10
)
redis_client = redis.Redis(
    connection_pool=redis_pool,
    socket_timeout=10,
    socket_connect_timeout=10,
    retry=retry
)

def ensure_redis_connection(max_attempts=3):
    global redis_client
    for attempt in range(max_attempts):
        try:
            redis_client.ping()
            logger.info("Conexión a Redis establecida correctamente")
            return True
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Intento {attempt + 1}/{max_attempts} - Redis no disponible: {str(e)}")
            time.sleep(2 ** attempt)
            try:
                redis_client = redis.Redis(
                    connection_pool=redis_pool,
                    socket_timeout=10,
                    socket_connect_timeout=10,
                    retry=retry,
                    ssl=True
                )
                redis_client.ping()
                logger.info("Reconexión a Redis exitosa")
                return True
            except redis.exceptions.ConnectionError:
                continue
    logger.error("Redis no disponible tras varios intentos")
    redis_client = None
    return False

@sleep_and_retry
@limits(calls=50, period=60)
def detect_emotion(text_to_analyze):
    """
    Analiza el texto para detectar una emoción predominante de una lista predefinida.
    Devuelve una única cadena de texto con la emoción.
    """
    system_prompt = (
        "Eres una IA experta en detección de emociones. Tu tarea es analizar el texto proporcionado e "
        "identificar la emoción predominante. Debes elegir una de las siguientes seis emociones: "
        "'joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust'."
        "No añadas texto extra, explicaciones ni puntuación. Tu respuesta debe ser una única palabra "
        "en minúsculas de la lista. Por ejemplo: `sadness`."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text_to_analyze}
    ]

    # Call the existing grok service with a very low max_tokens, as we expect a single word.
    # A slightly higher temperature might help in ambiguous cases.
    emotion = call_grok(messages, max_tokens=10, temperature=0.3)

    # Clean up the response to ensure it's just the emotion word
    valid_emotions = ['joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust']
    cleaned_emotion = ''.join(e for e in emotion if e.isalnum()).lower()

    if cleaned_emotion in valid_emotions:
        return cleaned_emotion
    else:
        # Fallback in case the model returns something unexpected
        return 'joy' 


def call_grok(messages, max_tokens=150, temperature=0.5):
    if len(messages) > 10:
        messages = [messages[0]] + messages[-9:]

    cache_key = json.dumps(messages)
    result = None

    if redis_client and ensure_redis_connection():
        try:
            result = redis_client.get(cache_key)
            if result:
                logger.info("Respuesta obtenida desde caché")
                return result
        except redis.exceptions.ConnectionError as e:
            logger.warning(f"Error al leer desde Redis: {str(e)}")

    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {os.getenv('XAI_API_KEY')}", "Content-Type": "application/json"}
    payload = {"model": "grok-3", "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()['choices'][0]['message']['content']

        if redis_client and ensure_redis_connection():
            try:
                redis_client.setex(cache_key, 3600, result)
                logger.info("Respuesta guardada en caché")
            except redis.exceptions.ConnectionError as e:
                logger.warning(f"Error al guardar en Redis: {str(e)}")

        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al conectar con xAI: {str(e)}")
        return "Error al conectar con la IA. Intenta de nuevo más tarde."