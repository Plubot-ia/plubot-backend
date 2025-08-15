"""Servicio de caché para mejorar el rendimiento del sistema.

Este módulo proporciona funciones para almacenar y recuperar datos en caché,
reduciendo la carga en la base de datos.
"""
from collections.abc import Callable
from functools import lru_cache, wraps
import hashlib
import logging
import time
from typing import Any, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

# Caché en memoria para datos de uso frecuente
_memory_cache: dict[str, Any] = {}
_cache_expiry: dict[str, float] = {}


def get_cache_key(
    prefix: str,
    *args: Any,  # noqa: ANN401 - Necesario para una clave de caché genérica
    **kwargs: Any,  # noqa: ANN401 - Necesario para una clave de caché genérica
) -> str:
    """Genera una clave de caché única basada en los argumentos."""
    # Convertir argumentos a string y crear un hash seguro
    args_str = str(args) + str(sorted(kwargs.items()))
    hash_obj = hashlib.sha256(args_str.encode())
    return f"{prefix}:{hash_obj.hexdigest()}"


def cache_set(key: str, value: T, expire_seconds: int = 3600) -> None:
    """Almacena un valor en la caché en memoria."""
    _memory_cache[key] = value
    _cache_expiry[key] = time.time() + expire_seconds
    logger.debug(
        "Valor almacenado en caché con clave: %s, expira en %ss",
        key,
        expire_seconds,
    )


def cache_get(key: str) -> tuple[bool, T | None]:
    """Recupera un valor de la caché en memoria."""
    if key in _memory_cache:
        if time.time() > _cache_expiry.get(key, 0):
            logger.debug("Caché expirada para clave: %s", key)
            cache_delete(key)
            return False, None

        logger.debug("Valor recuperado de caché con clave: %s", key)
        return True, _memory_cache[key]

    return False, None


def cache_delete(key: str) -> None:
    """Elimina un valor de la caché en memoria."""
    _memory_cache.pop(key, None)
    _cache_expiry.pop(key, None)
    logger.debug("Valor eliminado de caché con clave: %s", key)


def cache_clear_all() -> None:
    """Limpia toda la caché en memoria."""
    _memory_cache.clear()
    _cache_expiry.clear()
    logger.debug("Caché en memoria limpiada completamente")


def cache_clear_by_prefix(prefix: str) -> None:
    """Limpia todas las entradas de caché que comienzan con un prefijo."""
    keys_to_delete = [k for k in _memory_cache if k.startswith(prefix)]
    for key in keys_to_delete:
        cache_delete(key)

    logger.debug(
        "Caché limpiada para prefijo: %s, %s entradas eliminadas",
        prefix,
        len(keys_to_delete),
    )


def invalidate_flow_cache(plubot_id: int) -> None:
    """Invalida la caché relacionada con un flujo específico."""
    cache_clear_by_prefix(f"flow:{plubot_id}")
    logger.info("Caché de flujo invalidada para plubot: %s", plubot_id)


def invalidate_plubot_cache(plubot_id: int) -> None:
    """Invalida toda la caché relacionada con un plubot específico."""
    cache_clear_by_prefix(f"plubot:{plubot_id}")
    invalidate_flow_cache(plubot_id)
    logger.info("Caché de plubot invalidada para plubot: %s", plubot_id)


def cached(
    prefix: str, expire_seconds: int = 3600
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorador para cachear el resultado de una función.

    Example:
        @cached("plubot", 1800)
        def get_plubot_data(plubot_id):
            # Operación costosa
            return data
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            cache_key = get_cache_key(prefix, *args, **kwargs)

            found, value = cache_get(cache_key)
            if found:
                return value  # type: ignore[return-value]

            result = func(*args, **kwargs)
            cache_set(cache_key, result, expire_seconds)
            return result

        return wrapper

    return decorator


# Caché optimizada para consultas frecuentes con LRU
@lru_cache(maxsize=100)
def get_flow_structure(plubot_id: int) -> dict[str, str]:
    """Obtiene la estructura de un flujo con caché LRU.

    Esta función debe ser llamada desde otra función que maneje la invalidación
    de caché cuando sea necesario.
    """
    # Esta función normalmente consultaría la base de datos
    # pero aquí solo devuelve un placeholder
    logger.info(
        "Caché LRU: Obteniendo estructura de flujo para plubot %s", plubot_id
    )
    return {"placeholder": "Esta función debe ser implementada con la lógica real"}


def clear_lru_caches() -> None:
    """Limpia todas las cachés LRU."""
    get_flow_structure.cache_clear()
    logger.info("Cachés LRU limpiadas")
