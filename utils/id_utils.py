"""Utilidades para la generación y manejo de IDs persistentes.

Este módulo proporciona funciones para generar IDs únicos y
mantener la persistencia entre frontend y backend.
"""
import logging
import re
from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from models.flow import Flow
from models.flow_edge import FlowEdge

logger = logging.getLogger(__name__)


def generate_uuid() -> str:
    """Genera un UUID único para usar como identificador.

    Returns:
        str: UUID en formato string.
    """
    return str(uuid.uuid4())


def generate_frontend_id(prefix: str = "node") -> str:
    """Genera un ID para el frontend con un prefijo específico.

    Args:
        prefix: Prefijo para el ID ('node', 'edge', etc.).

    Returns:
        str: ID en formato '{prefix}-{uuid}'.
    """
    return f"{prefix}-{generate_uuid()}"


def extract_id_from_frontend_id(frontend_id: str) -> tuple[str | None, str | None]:
    """Extrae el prefijo y el UUID de un ID del frontend.

    Args:
        frontend_id: ID del frontend en formato '{prefix}-{uuid}'.

    Returns:
        tuple[str | None, str | None]: (prefijo, uuid) o (None, None) si no es válido.
    """
    if not frontend_id:
        return None, None

    match = re.match(r"^([a-zA-Z]+)-([a-zA-Z0-9-]+)$", frontend_id)
    if match:
        return match.group(1), match.group(2)

    return None, None


def is_valid_frontend_id(frontend_id: str) -> bool:
    """Verifica si un ID del frontend tiene un formato válido.

    Args:
        frontend_id: ID del frontend a verificar.

    Returns:
        bool: True si el ID es válido, False en caso contrario.
    """
    prefix, uuid_part = extract_id_from_frontend_id(frontend_id)
    return prefix is not None and uuid_part is not None


def create_id_mapping(session: "Session", plubot_id: int) -> dict[str, int]:
    """Crea un mapeo de IDs del frontend a IDs del backend para un plubot específico.

    Args:
        session: Sesión de SQLAlchemy.
        plubot_id: ID del plubot.

    Returns:
        dict[str, int]: Diccionario con mapeo {frontend_id: backend_id}.
    """
    mapping = {}

    # Mapear nodos
    nodes = (
        session.query(Flow)
        .filter_by(chatbot_id=plubot_id, is_deleted=False)
        .all()
    )

    for node in nodes:
        if node.frontend_id:
            mapping[node.frontend_id] = node.id

    # Mapear aristas
    edges = (
        session.query(FlowEdge)
        .filter_by(chatbot_id=plubot_id, is_deleted=False)
        .all()
    )

    for edge in edges:
        if edge.frontend_id:
            mapping[edge.frontend_id] = edge.id

    return mapping


def get_backend_id(session: "Session", plubot_id: int, frontend_id: str) -> int | None:
    """Obtiene el ID del backend correspondiente a un ID del frontend.

    Args:
        session: Sesión de SQLAlchemy.
        plubot_id: ID del plubot.
        frontend_id: ID del frontend.

    Returns:
        int | None: ID del backend o None si no se encontró.
    """
    # Determinar si es un nodo o una arista
    prefix, _ = extract_id_from_frontend_id(frontend_id)

    if prefix == "node":
        node = (
            session.query(Flow)
            .filter_by(
                chatbot_id=plubot_id, frontend_id=frontend_id, is_deleted=False
            )
            .first()
        )
        return node.id if node else None

    if prefix == "edge":
        edge = (
            session.query(FlowEdge)
            .filter_by(
                chatbot_id=plubot_id, frontend_id=frontend_id, is_deleted=False
            )
            .first()
        )
        return edge.id if edge else None

    return None
