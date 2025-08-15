#!/usr/bin/env python3
"""Script para forzar la recarga de los modelos SQLAlchemy y limpiar la caché.

Esto ayudará a resolver el problema con el atributo edge_type en el modelo FlowEdge.
"""

import importlib
import logging
from pathlib import Path
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# --- Constantes de Error ---
_RUFF_NOT_FOUND_ERROR = "El comando 'ruff' no fue encontrado."
_ATTRIBUTE_NOT_IN_MODEL_ERROR = "El atributo edge_type NO existe en el modelo FlowEdge."
_COLUMN_NOT_IN_MODEL_ERROR = "edge_type NO está en las columnas del modelo."
_COLUMN_NOT_IN_DB_ERROR = "edge_type NO existe en la tabla 'flow_edges' en la BD."


# Configurar logging
logger = logging.getLogger(__name__)

# Añadir el directorio del proyecto al sys.path para importaciones locales
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Importar los módulos necesarios después de ajustar el path
from models import get_engine, get_session  # noqa: E402
from models.flow_edge import FlowEdge  # noqa: E402


def _run_ruff_lint() -> None:
    """Ejecuta ruff para verificar el linting del código."""
    logger.info("Ejecutando ruff para verificar el código...")
    try:
        result = subprocess.run(
            ["ruff", "check", "."],
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode != 0:
            logger.error("❌ Ruff encontró errores de linting.")
            logger.error("Salida de ruff:\n%s", result.stdout)
            logger.error("Errores de ruff:\n%s", result.stderr)
        else:
            logger.info("✅ Ruff no encontró errores.")
    except FileNotFoundError:
        logger.exception(_RUFF_NOT_FOUND_ERROR)


def refresh_models() -> None:
    """Refresca los modelos de la base de datos y verifica que edge_type existe."""
    logger.info("Verificando modelo FlowEdge...")

    # Recargar el módulo para asegurar que se usa la última definición
    importlib.reload(sys.modules["models.flow_edge"])

    # Usar validaciones explícitas en lugar de asserts
    if not hasattr(FlowEdge, "edge_type"):
        raise ValueError(_ATTRIBUTE_NOT_IN_MODEL_ERROR)
    logger.info("✅ El atributo edge_type existe en el modelo FlowEdge.")

    columns = [column.name for column in FlowEdge.__table__.columns]
    logger.info("Columnas del modelo FlowEdge: %s", columns)

    if "edge_type" not in columns:
        raise ValueError(_COLUMN_NOT_IN_MODEL_ERROR)
    logger.info("✅ edge_type está en las columnas del modelo.")

    engine = get_engine()
    try:
        with engine.connect() as conn:
            query = text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'flow_edges'"
            )
            result = conn.execute(query)
            db_columns = [row[0] for row in result]
            logger.info("Columnas de 'flow_edges' en BD: %s", db_columns)

            if "edge_type" not in db_columns:
                raise ValueError(_COLUMN_NOT_IN_DB_ERROR)
            logger.info("✅ edge_type existe en la tabla 'flow_edges' de la BD.")
    except SQLAlchemyError:
        # Usar logging.exception para capturar el traceback
        logger.exception("Error al verificar la estructura de la tabla en la BD.")
        return

    session = get_session()
    try:
        first_edge = session.query(FlowEdge).first()
        if first_edge:
            logger.info("Primera arista encontrada: %s", first_edge.id)
            if hasattr(first_edge, "edge_type"):
                logger.info("  edge_type: %s", first_edge.edge_type)
            else:
                logger.warning("  El objeto no tiene el atributo edge_type")
        else:
            logger.info("No se encontraron aristas en la tabla.")
    except SQLAlchemyError:
        # Usar logging.exception aquí también
        logger.exception("Error al consultar la base de datos.")
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    _run_ruff_lint()
    refresh_models()

