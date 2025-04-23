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
def call_grok(messages, max_tokens=150):
    if len(messages) > 4:
        messages = [messages[0]] + messages[-3:]

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
    payload = {"model": "grok-2-1212", "messages": messages, "temperature": 0.5, "max_tokens": max_tokens}
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