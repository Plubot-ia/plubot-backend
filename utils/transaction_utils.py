"""Utilidades para manejar transacciones atómicas en la base de datos.

Este módulo proporciona decoradores y funciones para garantizar
la consistencia de los datos en operaciones complejas.
"""
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
import functools
import logging
from typing import ParamSpec, TypeVar

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ERROR_SESSION_NOT_FOUND = (
    "No se encontró una sesión de SQLAlchemy en los argumentos de la función."
)
ERROR_SESSION_OR_ID_NOT_FOUND = (
    "No se encontró una sesión o plubot_id en los argumentos."
)


P = ParamSpec("P")
R = TypeVar("R")


@contextmanager
def atomic_transaction(
    session: Session, error_message: str = "Error en transacción"
) -> AbstractContextManager[Session]:
    """Contexto para ejecutar operaciones dentro de una transacción atómica.

    Si ocurre un error, se hace rollback de todos los cambios.

    Args:
        session (Session): Sesión de SQLAlchemy.
        error_message (str): Mensaje de error personalizado.

    Yields:
        Session: La misma sesión para usar dentro del contexto.

    Example:
        with atomic_transaction(session) as tx_session:
            # Operaciones con tx_session
            # Si ocurre una excepción, se hace rollback automáticamente
    """
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("%s", error_message)
        raise


def transactional(
    error_message: str = "Error en transacción",
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorador para ejecutar una función dentro de una transacción atómica.

    Busca automáticamente el argumento 'session' en la función decorada
    y gestiona el commit/rollback.

    Args:
        error_message (str): Mensaje de error personalizado.

    Returns:
        Callable: Decorador para la función.

    Raises:
        TypeError: Si no se encuentra un argumento de sesión de SQLAlchemy.

    Example:
        @transactional("Error al guardar el flujo")
        def save_flow(session, plubot_id, data):
            # Operaciones con la base de datos
            # Si ocurre una excepción, se hace rollback automáticamente
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            session: Session | None = None
            # Buscar la sesión en los argumentos posicionales
            for arg in args:
                if isinstance(arg, Session):
                    session = arg
                    break

            # Si no se encuentra, buscar en los argumentos de palabra clave
            if session is None:
                session = kwargs.get("session")

            if not isinstance(session, Session):
                raise TypeError(ERROR_SESSION_NOT_FOUND)

            # Ejecutar la función original dentro del contexto de la transacción
            with atomic_transaction(session, error_message):
                return func(*args, **kwargs)

        return wrapper

    return decorator

def with_retry(
    max_attempts: int = 3,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    error_message: str = "Error con reintento",
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorador para reintentar una función en caso de error.

    Args:
        max_attempts (int): Número máximo de intentos.
        retry_on (tuple): Excepciones que activarán un reintento.
        error_message (str): Mensaje de error personalizado.

    Returns:
        Callable: Decorador para la función.

    Example:
        @with_retry(max_attempts=3, retry_on=(SQLAlchemyError,))
        def operation_with_retry(session, data):
            # Operación que podría fallar
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exception = e
                    logger.warning(
                        "%s (intento %d/%d): %s",
                        error_message,
                        attempt + 1,
                        max_attempts,
                        e,
                    )

                    if attempt == max_attempts - 1:
                        break

            logger.error(
                "%s (todos los intentos fallaron): %s", error_message, last_exception
            )
            if last_exception is not None:
                raise last_exception
            # Fallback in case loop doesn't run
            message = f"{error_message} falló inesperadamente."
            raise RuntimeError(message)

        return wrapper

    return decorator


def backup_before_operation(
    backup_func: Callable[[Session, int], int]
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorador para crear una copia de seguridad antes de ejecutar una operación.

    Args:
        backup_func (Callable): Función que realiza la copia de seguridad.
                               Debe aceptar `session` y `plubot_id` y devolver `backup_id`.

    Returns:
        Callable: Decorador para la función.

    Example:
        def create_flow_backup(session, plubot_id):
            # Crear copia de seguridad
            return backup_id

        @backup_before_operation(create_flow_backup)
        def update_flow(session, plubot_id, data):
            # Actualizar flujo
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            session: Session | None = None
            plubot_id: int | None = None

            # Buscar la sesión y el plubot_id en los argumentos
            for arg in args:
                if isinstance(arg, Session):
                    session = arg
                # Asumimos que el primer entero es el plubot_id
                elif isinstance(arg, int) and plubot_id is None:
                    plubot_id = arg

            if session is None:
                session = kwargs.get("session")

            if plubot_id is None:
                plubot_id = kwargs.get("plubot_id")

            if not isinstance(session, Session) or not isinstance(plubot_id, int):
                raise TypeError(ERROR_SESSION_OR_ID_NOT_FOUND)

            # Crear copia de seguridad
            backup_id = backup_func(session, plubot_id)
            logger.info(
                "Copia de seguridad creada con ID %d para plubot %d",
                backup_id,
                plubot_id,
            )

            # Ejecutar la función original
            return func(*args, **kwargs)

        return wrapper

    return decorator
