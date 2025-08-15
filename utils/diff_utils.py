"""Utilidades para manejar actualizaciones incrementales de flujos y aristas.

Este módulo proporciona funciones para calcular diferencias entre estados
y aplicar cambios incrementales a la base de datos.
"""
import logging
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from models.flow import Flow
from models.flow_edge import FlowEdge

logger = logging.getLogger(__name__)


# --- Tipos de Datos Estructurados ---
class PositionDict(TypedDict):
    x: float
    y: float


class NodeDataDict(TypedDict):
    label: str
    message: str


class NodeDict(TypedDict):
    id: str
    position: PositionDict
    data: NodeDataDict
    type: str
    metadata: dict[str, Any]


class EdgeStyleDict(TypedDict):
    stroke: str
    strokeWidth: float


class EdgeDict(TypedDict):
    id: str
    source: str
    target: str
    sourceHandle: str | None
    targetHandle: str | None
    label: str
    type: str
    style: EdgeStyleDict
    condition: str
    metadata: dict[str, Any]


class FlowStateDict(TypedDict):
    nodes: list[NodeDict]
    edges: list[EdgeDict]


class FlowDiff(TypedDict):
    nodes_to_create: list[NodeDict]
    nodes_to_update: list[NodeDict]
    nodes_to_delete: list[str]
    edges_to_create: list[EdgeDict]
    edges_to_update: list[EdgeDict]
    edges_to_delete: list[str]


# --- Funciones de Comparación de Flujos ---
def compute_flow_diff(old_state: FlowStateDict, new_state: FlowStateDict) -> FlowDiff:
    """Calcula las diferencias entre dos estados de flujo.

    Args:
        old_state: Estado anterior del flujo.
        new_state: Nuevo estado del flujo.

    Returns:
        Un diccionario con las diferencias calculadas.
    """
    old_nodes = old_state.get("nodes", [])
    new_nodes = new_state.get("nodes", [])
    old_edges = old_state.get("edges", [])
    new_edges = new_state.get("edges", [])

    old_nodes_map = {node["id"]: node for node in old_nodes}
    new_nodes_map = {node["id"]: node for node in new_nodes}
    old_edges_map = {edge["id"]: edge for edge in old_edges}
    new_edges_map = {edge["id"]: edge for edge in new_edges}

    nodes_to_create = [n for n in new_nodes if n["id"] not in old_nodes_map]
    nodes_to_update = [
        n
        for n in new_nodes
        if n["id"] in old_nodes_map and has_node_changed(old_nodes_map[n["id"]], n)
    ]
    nodes_to_delete = [n["id"] for n in old_nodes if n["id"] not in new_nodes_map]

    edges_to_create = [e for e in new_edges if e["id"] not in old_edges_map]
    edges_to_update = [
        e
        for e in new_edges
        if e["id"] in old_edges_map and has_edge_changed(old_edges_map[e["id"]], e)
    ]
    edges_to_delete = [e["id"] for e in old_edges if e["id"] not in new_edges_map]

    return {
        "nodes_to_create": nodes_to_create,
        "nodes_to_update": nodes_to_update,
        "nodes_to_delete": nodes_to_delete,
        "edges_to_create": edges_to_create,
        "edges_to_update": edges_to_update,
        "edges_to_delete": edges_to_delete,
    }


def has_node_changed(old_node: NodeDict, new_node: NodeDict) -> bool:
    """Determina si un nodo ha cambiado comparando sus propiedades relevantes."""
    return (
        old_node["position"] != new_node["position"]
        or old_node["data"] != new_node["data"]
        or old_node["type"] != new_node["type"]
    )


def has_edge_changed(old_edge: EdgeDict, new_edge: EdgeDict) -> bool:
    """Determina si una arista ha cambiado comparando sus propiedades relevantes."""
    return (
        old_edge["source"] != new_edge["source"]
        or old_edge["target"] != new_edge["target"]
        or old_edge["sourceHandle"] != new_edge["sourceHandle"]
        or old_edge["targetHandle"] != new_edge["targetHandle"]
        or old_edge.get("label") != new_edge.get("label")
        or old_edge.get("type") != new_edge.get("type")
        or old_edge.get("style") != new_edge.get("style")
    )


# --- Funciones de Aplicación de Cambios ---
def apply_flow_diff(session: Session, plubot_id: int, diff: FlowDiff) -> bool:
    """Aplica cambios incrementales al flujo en la base de datos.

    Args:
        session: Sesión de SQLAlchemy.
        plubot_id: ID del plubot.
        diff: Diferencias a aplicar.

    Returns:
        True si se aplicaron los cambios correctamente.
    """
    try:
        for node_data in diff["nodes_to_create"]:
            create_node(session, plubot_id, node_data)
        for node_data in diff["nodes_to_update"]:
            update_node(session, plubot_id, node_data)
        for node_id in diff["nodes_to_delete"]:
            soft_delete_node(session, plubot_id, node_id)

        for edge_data in diff["edges_to_create"]:
            create_edge(session, plubot_id, edge_data)
        for edge_data in diff["edges_to_update"]:
            update_edge(session, plubot_id, edge_data)
        for edge_id in diff["edges_to_delete"]:
            soft_delete_edge(session, plubot_id, edge_id)

    except Exception:
        logger.exception("Error al aplicar diferencias de flujo para plubot_id: %d", plubot_id)
        raise
    else:
        return True


def create_node(session: Session, plubot_id: int, node_data: NodeDict) -> Flow:
    """Crea un nuevo nodo en la base de datos."""
    position = node_data.get("position", {"x": 0, "y": 0})
    data = node_data.get("data", {"label": "", "message": ""})

    node = Flow(
        chatbot_id=plubot_id,
        frontend_id=node_data["id"],
        user_message=data.get("label", ""),
        bot_response=data.get("message", ""),
        position=0,  # Legacy
        intent=node_data.get("type", "message"),
        position_x=position.get("x", 0),
        position_y=position.get("y", 0),
        node_type=node_data.get("type", "message"),
        metadata=node_data.get("metadata", {}),
    )

    session.add(node)
    session.flush()

    logger.info(
        "Nodo creado: %s (frontend_id: %s)", node.id, node.frontend_id
    )
    return node


def update_node(session: Session, plubot_id: int, node_data: NodeDict) -> Flow | None:
    """Actualiza un nodo existente en la base de datos."""
    node_id = node_data["id"]
    node = (
        session.query(Flow)
        .filter_by(chatbot_id=plubot_id, frontend_id=node_id, is_deleted=False)
        .first()
    )

    if not node:
        logger.warning(
            "No se encontró el nodo con frontend_id %s para actualizar", node_id
        )
        return None

    position = node_data.get("position", {})
    data = node_data.get("data", {})

    node.user_message = data.get("label", node.user_message)
    node.bot_response = data.get("message", node.bot_response)
    node.position_x = position.get("x", node.position_x)
    node.position_y = position.get("y", node.position_y)
    node.node_type = node_data.get("type", node.node_type)
    node.intent = node_data.get("type", node.intent)

    if node.metadata and isinstance(node.metadata, dict):
        node.metadata.update(node_data.get("metadata", {}))
    else:
        node.metadata = node_data.get("metadata", {})

    node.updated_at = None  # Trigger onupdate

    logger.info(
        "Nodo actualizado: %s (frontend_id: %s)", node.id, node.frontend_id
    )
    return node


def soft_delete_node(session: Session, plubot_id: int, node_id: str) -> bool:
    """Marca un nodo como eliminado (soft delete)."""
    node = (
        session.query(Flow)
        .filter_by(chatbot_id=plubot_id, frontend_id=node_id, is_deleted=False)
        .first()
    )

    if not node:
        logger.warning(
            "No se encontró el nodo con frontend_id %s para eliminar", node_id
        )
        return False

    node.is_deleted = True
    node.updated_at = None  # Trigger onupdate

    logger.info(
        "Nodo marcado como eliminado: %s (frontend_id: %s)",
        node.id,
        node.frontend_id,
    )
    return True


def create_edge(
    session: Session, plubot_id: int, edge_data: EdgeDict
) -> FlowEdge | None:
    """Crea una nueva arista en la base de datos."""
    source_node = (
        session.query(Flow)
        .filter_by(
            chatbot_id=plubot_id, frontend_id=edge_data["source"], is_deleted=False
        )
        .first()
    )
    target_node = (
        session.query(Flow)
        .filter_by(
            chatbot_id=plubot_id, frontend_id=edge_data["target"], is_deleted=False
        )
        .first()
    )

    if not source_node or not target_node:
        logger.warning(
            "No se encontraron nodos para la arista: %s -> %s",
            edge_data["source"],
            edge_data["target"],
        )
        return None

    edge = FlowEdge(
        chatbot_id=plubot_id,
        source_flow_id=source_node.id,
        target_flow_id=target_node.id,
        frontend_id=edge_data["id"],
        condition=edge_data.get("condition", ""),
        label=edge_data.get("label", ""),
        edge_type=edge_data.get("type", "default"),
        source_handle=edge_data.get("sourceHandle"),
        target_handle=edge_data.get("targetHandle"),
        style=edge_data.get("style", {}),
        metadata=edge_data.get("metadata", {}),
    )

    session.add(edge)
    session.flush()

    logger.info(
        "Arista creada: %s (frontend_id: %s)", edge.id, edge.frontend_id
    )
    return edge


def update_edge(
    session: Session, plubot_id: int, edge_data: EdgeDict
) -> FlowEdge | None:
    """Actualiza una arista existente en la base de datos."""
    edge_id = edge_data["id"]
    edge = (
        session.query(FlowEdge)
        .filter_by(chatbot_id=plubot_id, frontend_id=edge_id, is_deleted=False)
        .first()
    )

    if not edge:
        logger.warning(
            "No se encontró la arista con frontend_id %s para actualizar", edge_id
        )
        return None

    edge.condition = edge_data.get("condition", edge.condition)
    edge.label = edge_data.get("label", edge.label)
    edge.edge_type = edge_data.get("type", edge.edge_type)
    edge.source_handle = edge_data.get("sourceHandle", edge.source_handle)
    edge.target_handle = edge_data.get("targetHandle", edge.target_handle)
    edge.style = edge_data.get("style", edge.style)

    if edge.metadata and isinstance(edge.metadata, dict):
        edge.metadata.update(edge_data.get("metadata", {}))
    else:
        edge.metadata = edge_data.get("metadata", {})

    edge.updated_at = None  # Trigger onupdate

    logger.info(
        "Arista actualizada: %s (frontend_id: %s)", edge.id, edge.frontend_id
    )
    return edge


def soft_delete_edge(session: Session, plubot_id: int, edge_id: str) -> bool:
    """Marca una arista como eliminada (soft delete)."""
    edge = (
        session.query(FlowEdge)
        .filter_by(chatbot_id=plubot_id, frontend_id=edge_id, is_deleted=False)
        .first()
    )

    if not edge:
        logger.warning(
            "No se encontró la arista con frontend_id %s para eliminar", edge_id
        )
        return False

    edge.is_deleted = True
    edge.updated_at = None  # Trigger onupdate

    logger.info(
        "Arista marcada como eliminada: %s (frontend_id: %s)",
        edge.id,
        edge.frontend_id,
    )
    return True
