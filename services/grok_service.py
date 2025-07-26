import json
import logging

from ratelimit import limits
import redis
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

logger = logging.getLogger(__name__)


class _RedisManager:
    """Manages a singleton Redis client instance to avoid using globals."""

    _client: redis.Redis | None = None

    def get_client(self) -> redis.Redis | None:
        """Return a Redis client instance, creating it if it doesn't exist.

        If the connection fails, it returns None and logs the error.
        """
        if self._client is None:
            if not settings.REDIS_URL:
                logger.warning("Redis URL not configured. Cache service is disabled.")
                return None
            try:
                client = redis.from_url(settings.REDIS_URL, decode_responses=True)
                client.ping()
                self._client = client
                logger.info("Successfully connected to Redis for caching.")
            except redis.exceptions.ConnectionError:
                logger.exception(
                    "Could not connect to Redis, caching will be disabled."
                )
                return None
        return self._client


_redis_manager = _RedisManager()
get_redis_client = _redis_manager.get_client


def get_cached_response(cache_key: str) -> str | None:
    """Get a response from the Redis cache."""
    redis_client = get_redis_client()
    if not redis_client:
        return None
    try:
        return redis_client.get(cache_key)
    except redis.exceptions.RedisError:
        logger.exception("Error getting from Redis cache.")
        return None


def cache_response(cache_key: str, response: str) -> None:
    """Store a response in the Redis cache."""
    redis_client = get_redis_client()
    if not redis_client:
        return
    try:
        # Cache for 1 hour
        redis_client.setex(cache_key, 3600, response)
    except redis.exceptions.RedisError:
        logger.exception("Error writing to Redis cache.")


@limits(calls=50, period=60)
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def analyze_emotion(text_to_analyze: str) -> str:
    """Analyze the text to detect a predominant emotion.

    Uses a specific prompt and a language model to classify the text
    into one of the six basic emotions: 'joy', 'sadness', 'anger', 'fear',
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

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text_to_analyze},
    ]

    emotion = call_grok(messages, max_tokens=10, temperature=0.3)

    valid_emotions = {"joy", "sadness", "anger", "fear", "surprise", "disgust"}
    cleaned_emotion = "".join(e for e in emotion if e.isalnum()).lower()

    if cleaned_emotion in valid_emotions:
        return cleaned_emotion

    return "joy"  # Safe fallback


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def call_grok(messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
    """Call the Grok API, using a Redis cache if available."""
    if len(messages) > 10:
        messages = [messages[0], *messages[-9:]]

    cache_key = json.dumps(messages)
    cached_response = get_cached_response(cache_key)
    if cached_response:
        return cached_response

    url = "https://api.x.ai/v1/chat/completions"
    payload = {
        "model": "grok-3-latest",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {settings.XAI_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        logger.exception("Error connecting to xAI API.")
        return "Error al conectar con la IA. Intenta de nuevo más tarde."
    else:
        grok_response = response.json()["choices"][0]["message"]["content"]
        cache_response(cache_key, grok_response)
        return grok_response
