"""
Servicio de caché para mejorar el rendimiento del sistema.
Este módulo proporciona funciones para almacenar y recuperar
datos en caché, reduciendo la carga en la base de datos.
"""
import json
import logging
import hashlib
import time
from functools import lru_cache, wraps
from typing import Any, Dict, Optional, Callable, Tuple

logger = logging.getLogger(__name__)

# Caché en memoria para datos de uso frecuente
_memory_cache = {}
_cache_expiry = {}

def get_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Genera una clave de caché única basada en los argumentos.
    
    Args:
        prefix (str): Prefijo para la clave
        *args: Argumentos posicionales
        **kwargs: Argumentos con nombre
    
    Returns:
        str: Clave de caché única
    """
    # Convertir argumentos a string y crear un hash
    args_str = str(args) + str(sorted(kwargs.items()))
    hash_obj = hashlib.md5(args_str.encode())
    return f"{prefix}:{hash_obj.hexdigest()}"

def cache_set(key: str, value: Any, expire_seconds: int = 3600) -> None:
    """
    Almacena un valor en la caché en memoria.
    
    Args:
        key (str): Clave de caché
        value (Any): Valor a almacenar
        expire_seconds (int): Tiempo de expiración en segundos
    """
    _memory_cache[key] = value
    _cache_expiry[key] = time.time() + expire_seconds
    logger.debug(f"Valor almacenado en caché con clave: {key}, expira en {expire_seconds}s")

def cache_get(key: str) -> Tuple[bool, Any]:
    """
    Recupera un valor de la caché en memoria.
    
    Args:
        key (str): Clave de caché
    
    Returns:
        Tuple[bool, Any]: (encontrado, valor)
    """
    if key in _memory_cache:
        # Verificar si ha expirado
        if time.time() > _cache_expiry.get(key, 0):
            logger.debug(f"Caché expirada para clave: {key}")
            cache_delete(key)
            return False, None
        
        logger.debug(f"Valor recuperado de caché con clave: {key}")
        return True, _memory_cache[key]
    
    return False, None

def cache_delete(key: str) -> None:
    """
    Elimina un valor de la caché en memoria.
    
    Args:
        key (str): Clave de caché
    """
    if key in _memory_cache:
        del _memory_cache[key]
    
    if key in _cache_expiry:
        del _cache_expiry[key]
    
    logger.debug(f"Valor eliminado de caché con clave: {key}")

def cache_clear_all() -> None:
    """
    Limpia toda la caché en memoria.
    """
    _memory_cache.clear()
    _cache_expiry.clear()
    logger.debug("Caché en memoria limpiada completamente")

def cache_clear_by_prefix(prefix: str) -> None:
    """
    Limpia todas las entradas de caché que comienzan con un prefijo.
    
    Args:
        prefix (str): Prefijo para filtrar las claves
    """
    keys_to_delete = [k for k in _memory_cache.keys() if k.startswith(prefix)]
    for key in keys_to_delete:
        cache_delete(key)
    
    logger.debug(f"Caché limpiada para prefijo: {prefix}, {len(keys_to_delete)} entradas eliminadas")

def invalidate_flow_cache(plubot_id: int) -> None:
    """
    Invalida la caché relacionada con un flujo específico.
    
    Args:
        plubot_id (int): ID del plubot
    """
    cache_clear_by_prefix(f"flow:{plubot_id}")
    logger.info(f"Caché de flujo invalidada para plubot: {plubot_id}")

def invalidate_plubot_cache(plubot_id: int) -> None:
    """
    Invalida toda la caché relacionada con un plubot específico.
    
    Args:
        plubot_id (int): ID del plubot
    """
    cache_clear_by_prefix(f"plubot:{plubot_id}")
    invalidate_flow_cache(plubot_id)
    logger.info(f"Caché de plubot invalidada para plubot: {plubot_id}")

def cached(prefix: str, expire_seconds: int = 3600) -> Callable:
    """
    Decorador para cachear el resultado de una función.
    
    Args:
        prefix (str): Prefijo para la clave de caché
        expire_seconds (int): Tiempo de expiración en segundos
    
    Returns:
        Callable: Decorador para la función
    
    Example:
        @cached("plubot", 1800)
        def get_plubot_data(plubot_id):
            # Operación costosa
            return data
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generar clave de caché
            cache_key = get_cache_key(prefix, *args, **kwargs)
            
            # Intentar recuperar de caché
            found, value = cache_get(cache_key)
            if found:
                return value
            
            # Ejecutar función original
            result = func(*args, **kwargs)
            
            # Almacenar en caché
            cache_set(cache_key, result, expire_seconds)
            
            return result
        
        return wrapper
    
    return decorator

# Caché optimizada para consultas frecuentes con LRU
@lru_cache(maxsize=100)
def get_flow_structure(plubot_id: int) -> Dict:
    """
    Obtiene la estructura de un flujo con caché LRU.
    Esta función debe ser llamada desde otra función que maneje
    la invalidación de caché cuando sea necesario.
    
    Args:
        plubot_id (int): ID del plubot
    
    Returns:
        Dict: Estructura del flujo
    """
    # Esta función normalmente consultaría la base de datos
    # pero aquí solo devuelve un placeholder
    logger.info(f"Caché LRU: Obteniendo estructura de flujo para plubot {plubot_id}")
    return {"placeholder": "Esta función debe ser implementada con la lógica real"}

def clear_lru_caches() -> None:
    """
    Limpia todas las cachés LRU.
    """
    get_flow_structure.cache_clear()
    logger.info("Cachés LRU limpiadas")
