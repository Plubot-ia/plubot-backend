"""
Utilidades para manejar transacciones atómicas en la base de datos.
Este módulo proporciona decoradores y funciones para garantizar
la consistencia de los datos en operaciones complejas.
"""
import logging
import functools
import traceback
from contextlib import contextmanager
from sqlalchemy.orm import Session
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

@contextmanager
def atomic_transaction(session: Session, error_message: str = "Error en transacción"):
    """
    Contexto para ejecutar operaciones dentro de una transacción atómica.
    Si ocurre un error, se hace rollback de todos los cambios.
    
    Args:
        session (Session): Sesión de SQLAlchemy
        error_message (str): Mensaje de error personalizado
    
    Yields:
        Session: La misma sesión para usar dentro del contexto
    
    Example:
        with atomic_transaction(session) as tx_session:
            # Operaciones con tx_session
            # Si ocurre una excepción, se hace rollback automáticamente
    """
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"{error_message}: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def transactional(error_message: str = "Error en transacción") -> Callable:
    """
    Decorador para ejecutar una función dentro de una transacción atómica.
    
    Args:
        error_message (str): Mensaje de error personalizado
    
    Returns:
        Callable: Decorador para la función
    
    Example:
        @transactional("Error al guardar el flujo")
        def save_flow(session, plubot_id, data):
            # Operaciones con la base de datos
            # Si ocurre una excepción, se hace rollback automáticamente
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Buscar la sesión en los argumentos
            session = None
            for arg in args:
                if isinstance(arg, Session):
                    session = arg
                    break
            
            if session is None:
                session = kwargs.get('session')
            
            if session is None:
                raise ValueError("No se encontró una sesión de SQLAlchemy en los argumentos")
            
            with atomic_transaction(session, error_message):
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator

def with_retry(max_attempts: int = 3, retry_on: tuple = (Exception,), 
               error_message: str = "Error con reintento") -> Callable:
    """
    Decorador para reintentar una función en caso de error.
    
    Args:
        max_attempts (int): Número máximo de intentos
        retry_on (tuple): Excepciones que activarán un reintento
        error_message (str): Mensaje de error personalizado
    
    Returns:
        Callable: Decorador para la función
    
    Example:
        @with_retry(max_attempts=3, retry_on=(SQLAlchemyError,))
        def operation_with_retry(session, data):
            # Operación que podría fallar
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exception = e
                    logger.warning(f"{error_message} (intento {attempt+1}/{max_attempts}): {str(e)}")
                    
                    # Si es el último intento, no continuamos
                    if attempt == max_attempts - 1:
                        break
            
            # Si llegamos aquí, todos los intentos fallaron
            logger.error(f"{error_message} (todos los intentos fallaron): {str(last_exception)}")
            raise last_exception
        
        return wrapper
    
    return decorator

def backup_before_operation(backup_func: Callable) -> Callable:
    """
    Decorador para crear una copia de seguridad antes de ejecutar una operación.
    
    Args:
        backup_func (Callable): Función que realiza la copia de seguridad
    
    Returns:
        Callable: Decorador para la función
    
    Example:
        def create_flow_backup(session, plubot_id):
            # Crear copia de seguridad
            return backup_id
        
        @backup_before_operation(create_flow_backup)
        def update_flow(session, plubot_id, data):
            # Actualizar flujo
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Buscar la sesión y el plubot_id en los argumentos
            session = None
            plubot_id = None
            
            for arg in args:
                if isinstance(arg, Session):
                    session = arg
                elif isinstance(arg, int) and plubot_id is None:
                    plubot_id = arg
            
            if session is None:
                session = kwargs.get('session')
            
            if plubot_id is None:
                plubot_id = kwargs.get('plubot_id')
            
            if session is None or plubot_id is None:
                raise ValueError("No se encontró una sesión o plubot_id en los argumentos")
            
            # Crear copia de seguridad
            backup_id = backup_func(session, plubot_id)
            logger.info(f"Copia de seguridad creada con ID {backup_id} para plubot {plubot_id}")
            
            # Ejecutar la función original
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator
