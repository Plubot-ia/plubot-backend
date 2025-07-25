"""API para la gestión de flujos de Plubots.

Este módulo proporciona endpoints optimizados para manejar flujos
con actualizaciones incrementales, caché y transacciones atómicas.
"""
import json
import logging
import time
from typing import Any
import uuid

from flask import Blueprint, Response, jsonify, request  # app es necesario para la caché
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.orm import Session, joinedload

from config.settings import get_session
from models.flow import Flow
from models.flow_edge import FlowEdge
from models.plubot import Plubot
from services.cache_service import cache_get, cache_set, get_cache_key, invalidate_flow_cache
from utils.transaction_utils import atomic_transaction, transactional

flow_bp = Blueprint("flow", __name__)
logger = logging.getLogger(__name__)

# Helper para validación JSON
def is_json_serializable(obj: Any) -> bool:  # noqa: ANN401
    if obj is None:  # None es JSON null, que es válido
        return True
    try:
        json.dumps(obj)
    except (TypeError, OverflowError) as e:
        logger.warning(
            "Data is not JSON serializable: %s. Data: %s", e, str(obj)[:200]
        )  # Loguea el error y parte del dato
        return False
    else:
        return True

# Modelo para respaldo de flujos
class FlowBackup:
    def __init__(self, plubot_id: int, data: dict[str, Any], version: int = 1):
        self.plubot_id = plubot_id
        self.data = data
        self.version = version
        self.id = str(uuid.uuid4())
        self.timestamp = time.time()

# Almacén temporal de respaldos (en producción usaríamos la base de datos)
_flow_backups = {}

def create_flow_backup(session: Session, plubot_id: int, version: int | None = None) -> str:
    """Crea una copia de seguridad del flujo actual."""
    # Obtener flujos y aristas
    flows = session.query(Flow).filter_by(chatbot_id=plubot_id, is_deleted=False).all()
    edges = session.query(FlowEdge).filter_by(chatbot_id=plubot_id, is_deleted=False).all()

    # Convertir a formato serializable
    flow_data = {
        "nodes": [
            {
                "id": flow.frontend_id or str(flow.id),
                "type": flow.node_type,
                "position": {"x": flow.position_x or 0, "y": flow.position_y or 0},
                "data": {
                    "label": flow.user_message,
                    "message": flow.bot_response
                },
                "metadata": flow.node_metadata
            } for flow in flows
        ],
        "edges": [
            {
                "id": edge.frontend_id or str(edge.id),
                "source": next(
                    (f.frontend_id for f in flows if f.id == edge.source_flow_id),
                    str(edge.source_flow_id),
                ),
                "target": next(
                    (f.frontend_id for f in flows if f.id == edge.target_flow_id),
                    str(edge.target_flow_id),
                ),
                "sourceHandle": edge.source_handle,
                "targetHandle": edge.target_handle,
                "type": edge.edge_type,
                "label": edge.label,
                "style": edge.style,
                "metadata": edge.edge_metadata
            } for edge in edges
        ]
    }

    # Determinar la versión
    versions = [b.version for b in _flow_backups.values() if b.plubot_id == plubot_id]
    version = max(versions) + 1 if versions else 1

    # Crear backup
    backup = FlowBackup(plubot_id, flow_data, version)
    _flow_backups[backup.id] = backup

    # Limitar a 10 versiones por plubot
    plubot_backups = [b for b in _flow_backups.values() if b.plubot_id == plubot_id]
    if len(plubot_backups) > 10:
        oldest = min(plubot_backups, key=lambda b: b.timestamp)
        if oldest.id in _flow_backups:
            del _flow_backups[oldest.id]

    return backup.id

@flow_bp.route("/<int:plubot_id>", methods=["GET"])
@jwt_required()
def get_flow(plubot_id: int) -> Response:
    """Obtiene el flujo completo de un plubot.

    GET /api/flow/{plubot_id}
    """
    user_id = get_jwt_identity()

    cache_key = get_cache_key(f"flow:{plubot_id}", "full_details")

    try:
        found, cached_flow = cache_get(cache_key)
        if found:
            logger.info("Cache hit for key %s. Returning cached data.", cache_key)
            return (
                jsonify(
                    status="success",
                    data=cached_flow,
                    message="Flujo recuperado desde cache exitosamente",
                ),
                200,
            )
        logger.info("Cache miss for key %s.", cache_key)
    except Exception:
        logger.exception("Error accessing cache for GET flow for plubot %s", plubot_id)

    try:
        with get_session() as session:
            plubot = (
                session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            )
            if not plubot:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Plubot no encontrado o no tienes permisos",
                        }
                    ),
                    404,
                )

            flows = (
                session.query(Flow)
                .filter_by(chatbot_id=plubot_id, is_deleted=False)
                .options(
                    joinedload(Flow.outgoing_edges), joinedload(Flow.incoming_edges)
                )
                .all()
            )
            logger.info("DB query for flows returned %d items.", len(flows))

            nodes = []
            for flow in flows:
                node = {
                    "id": flow.frontend_id or str(flow.id),
                    "type": flow.node_type or "message",
                    "position": {"x": flow.position_x or 0, "y": flow.position_y or 0},
                    "data": (
                        flow.node_metadata.copy()
                        if flow.node_metadata
                        else {"label": flow.user_message, "message": flow.bot_response}
                    ),
                }
                nodes.append(node)

            edges = (
                session.query(FlowEdge)
                .filter_by(chatbot_id=plubot_id, is_deleted=False)
                .all()
            )
            logger.info("DB query for edges returned %d items.", len(edges))

            formatted_edges = []
            for edge in edges:
                try:
                    source_node = next(
                        (n for n in flows if n.id == edge.source_flow_id), None
                    )
                    target_node = next(
                        (n for n in flows if n.id == edge.target_flow_id), None
                    )

                    if not source_node or not target_node:
                        logger.warning(
                            "Omitiendo arista %s por nodo fuente/destino faltante. "
                            "SourceID: %s, TargetID: %s",
                            edge.id,
                            edge.source_flow_id,
                            edge.target_flow_id,
                        )
                        continue

                    formatted_edge = {
                        "id": str(edge.id),
                        "source": source_node.frontend_id or str(source_node.id),
                        "target": target_node.frontend_id or str(target_node.id),
                        "sourceHandle": edge.source_handle,
                        "targetHandle": edge.target_handle,
                        "type": edge.edge_type or "default",
                        "animated": edge.animated is not None and edge.animated,
                        "label": edge.label or "",
                    }
                    if edge.style:
                        formatted_edge["style"] = edge.style
                    if edge.edge_metadata:
                        formatted_edge["metadata"] = edge.edge_metadata

                    formatted_edges.append(formatted_edge)
                except Exception:
                    logger.exception("Error al formatear arista %s", edge.id)

            response_data = {
                "nodes": nodes,
                "edges": formatted_edges,
                "name": plubot.name,
            }

            try:
                cache_set(cache_key, response_data, expire_seconds=300)
                logger.info(
                    "Flow data for plubot %s stored in cache with key %s",
                    plubot_id,
                    cache_key,
                )
            except Exception:
                logger.exception(
                    "Error storing flow data in cache for plubot %s", plubot_id
                )

            return (
                jsonify(
                    status="success",
                    data=response_data,
                    message="Flujo recuperado desde DB exitosamente",
                ),
                200,
            )
    except Exception:
        logger.exception("Error al obtener flujo para plubot %s", plubot_id)
        return (
            jsonify(
                {"status": "error", "message": "Error interno al obtener el flujo"}
            ),
            500,
        )


@flow_bp.route("/<int:plubot_id>", methods=["PATCH"])
@jwt_required()
def patch_flow(plubot_id: int) -> Response:
    """Actualiza el flujo de un plubot utilizando el método PATCH.

    Espera un payload JSON con 'nodes', 'edges', y opcionalmente 'name'.
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    logger.info("[PATCH /api/flow/%s] Received raw data: %s", plubot_id, data)

    if not data or not isinstance(data, dict):
        return jsonify({"status": "error", "message": "Payload inválido"}), 400

    flow_nodes = data.get("nodes")
    nodes_count = len(flow_nodes) if flow_nodes is not None else "None"
    edges_count = len(data.get("edges", []))
    name = data.get("name", "N/A")
    logger.info(
        "[PATCH /api/flow/%s] Extracted: nodes_count=%s, edges_count=%s, name='%s'",
        plubot_id, nodes_count, edges_count, name
    )
    flow_edges = data.get("edges")
    flow_name = data.get("name")  # El nombre es opcional para la actualización

    # Los nodos y aristas son fundamentales para la actualización del flujo
    if flow_nodes is None or not isinstance(flow_nodes, list) \
            or flow_edges is None or not isinstance(flow_edges, list):
        msg = "Payload must contain 'nodes' and 'edges' as lists."
        return jsonify({"status": "error", "message": msg}), 400

    flow_data_for_update = {
        "nodes": flow_nodes,
        "edges": flow_edges,
        "name": flow_name
    }

    try:
        with get_session() as session:
            # Verificar que el plubot existe y pertenece al usuario
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                msg = "Plubot no encontrado o no tienes permisos"
                return jsonify({"status": "error", "message": msg}), 404

            # Usar transacción atómica para la operación de actualización completa
            log_msg = f"Error al actualizar flujo (PATCH) para plubot {plubot_id}"
            with atomic_transaction(session, log_msg):
                # Crear una copia de seguridad antes de la operación principal
                create_flow_backup(session, plubot_id)

                # Llamar a la lógica existente para actualizar el flujo
                update_full_flow(session, plubot_id, flow_data_for_update)

            # Invalidar la caché después de una actualización exitosa
            invalidate_flow_cache(plubot_id)

            logger.info(
                "Flujo actualizado para plubot %s por usuario %s",
                plubot_id,
                user_id,
            )
            return jsonify({"status": "success", "message": "Flujo actualizado correctamente"}), 200

    except ValueError:
        # Errores de validación específicos
        logger.exception("Error de validación en PATCH para plubot %s", plubot_id)
        return jsonify({"status": "error", "message": "Error de validación de datos"}), 400
    except Exception:
        # Capturar el traceback completo para errores inesperados
        logger.exception("Error inesperado en PATCH para plubot %s", plubot_id)
        return jsonify({"status": "error", "message": "Error interno del servidor"}), 500


def _update_plubot_name_if_provided(session: Session, plubot_id: int, name: str | None) -> None:
    """Actualiza el nombre del plubot si se proporciona."""
    if not name:
        return
    plubot = session.query(Plubot).filter_by(id=plubot_id).first()
    if plubot:
        plubot.name = name
        session.add(plubot)

def _sync_nodes(
    session: Session, plubot_id: int, nodes_data: list, node_map: dict
) -> None:
    """Sincroniza los nodos del flujo y actualiza el node_map con los nuevos nodos."""
    frontend_ids_in_payload = {n.get("id") for n in nodes_data}

    for node_data in nodes_data:
        frontend_id = node_data.get("id")
        if not frontend_id:
            continue

        node_type = node_data.get("type")
        position = node_data.get("position", {})
        node_data_field = node_data.get("data", {})
        existing_node = node_map.get(frontend_id)

        if existing_node:
            existing_node.node_type = node_type
            existing_node.position_x = position.get("x")
            existing_node.position_y = position.get("y")
            existing_node.node_metadata = node_data_field
            existing_node.user_message = node_data_field.get(
                "label", existing_node.user_message
            )
            existing_node.bot_response = node_data_field.get(
                "message", existing_node.bot_response
            )
            existing_node.position = node_data_field.get(
                "position", existing_node.position
            )
            session.add(existing_node)
        else:
            new_node = Flow(
                chatbot_id=plubot_id,
                frontend_id=frontend_id,
                node_type=node_type,
                position_x=position.get("x"),
                position_y=position.get("y"),
                node_metadata=node_data_field,
                user_message=node_data_field.get("label", "Sin título"),
                bot_response=node_data_field.get("message", ""),
                position=node_data_field.get("position", 0),
            )
            session.add(new_node)
            session.flush()
            node_map[frontend_id] = new_node

    nodes_to_delete = [
        node for f_id, node in node_map.items() if f_id not in frontend_ids_in_payload
    ]
    for node in nodes_to_delete:
        session.delete(node)

def _sync_edges(
    session: Session, plubot_id: int, edges_data: list, node_map: dict
) -> None:
    """Sincroniza las aristas usando un node_map (frontend_id -> nodo) actualizado."""
    existing_edges = session.query(FlowEdge).filter_by(chatbot_id=plubot_id).all()
    edge_map = {edge.frontend_id: edge for edge in existing_edges if edge.frontend_id}
    frontend_ids_in_payload = {e.get("id") for e in edges_data}

    for edge_data in edges_data:
        frontend_id = edge_data.get("id")
        if not frontend_id:
            continue

        source_id = edge_data.get("source")
        target_id = edge_data.get("target")

        if source_id not in node_map or target_id not in node_map:
            logger.warning(
                "Skipping edge with invalid source/target frontend_ids: %s -> %s",
                source_id,
                target_id,
            )
            continue

        source_db_id = node_map[source_id].id
        target_db_id = node_map[target_id].id

        existing_edge = edge_map.get(frontend_id)
        if existing_edge:
            existing_edge.source_flow_id = source_db_id
            existing_edge.target_flow_id = target_db_id
            existing_edge.source_handle = edge_data.get("sourceHandle")
            existing_edge.target_handle = edge_data.get("targetHandle")
            existing_edge.edge_type = edge_data.get("type")
            existing_edge.label = edge_data.get("label")
            existing_edge.edge_metadata = edge_data.get("metadata")
            session.add(existing_edge)
        else:
            new_edge = FlowEdge(
                chatbot_id=plubot_id,
                frontend_id=frontend_id,
                source_flow_id=source_db_id,
                target_flow_id=target_db_id,
                source_handle=edge_data.get("sourceHandle", ""),
                target_handle=edge_data.get("targetHandle", ""),
                edge_type=edge_data.get("type"),
                label=edge_data.get("label"),
                edge_metadata=edge_data.get("metadata"),
            )
            session.add(new_edge)

    edges_to_delete = [
        edge for f_id, edge in edge_map.items() if f_id not in frontend_ids_in_payload
    ]
    for edge in edges_to_delete:
        session.delete(edge)

@transactional("Error al actualizar flujo completo")
def update_full_flow(
    session: Session,
    plubot_id: int,
    data: dict[str, Any],
) -> bool:
    """Actualiza el flujo completo de un plubot orquestando las sub-funciones."""
    nodes_data = data.get("nodes", [])
    edges_data = data.get("edges", [])
    name = data.get("name")

    logger.info(
        "[update_full_flow - plubot_id=%s] Starting update. "
        "Received: nodes_count=%s, edges_count=%s, name='%s'",
        plubot_id, len(nodes_data), len(edges_data), name
    )

    _update_plubot_name_if_provided(session, plubot_id, name)

    # El `node_map` (frontend_id -> nodo) es la única fuente de verdad.
    # Se pasa y se actualiza en `_sync_nodes`, y luego se usa en `_sync_edges`.
    existing_nodes = session.query(Flow).filter_by(chatbot_id=plubot_id).all()
    node_map = {node.frontend_id: node for node in existing_nodes if node.frontend_id}

    _sync_nodes(session, plubot_id, nodes_data, node_map)
    _sync_edges(session, plubot_id, edges_data, node_map)

    return True



@jwt_required()
def list_backups(plubot_id: int) -> Response:
    """Lista todas las copias de seguridad para un plubot.

    GET /api/flow/{plubot_id}/backup
    """
    user_id = get_jwt_identity()

    try:
        with get_session() as session:
            # Verificar que el plubot existe y pertenece al usuario
            plubot = (
                session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            )
            if not plubot:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Plubot no encontrado o no tienes permisos",
                        },
                    ),
                    404,
                )

            # Obtener backups
            backups = [
                {
                    "id": b.id,
                    "version": b.version,
                    "timestamp": b.timestamp,
                }
                for b in _flow_backups.values()
                if b.plubot_id == plubot_id
            ]

            # Ordenar por versión descendente
            backups.sort(key=lambda b: b["version"], reverse=True)

            return jsonify({"status": "success", "backups": backups}), 200
    except Exception:
        logger.exception("Error al listar backups para plubot %s", plubot_id)
        return (
            jsonify({"status": "error", "message": "Error al listar backups"}),
            500,
        )


@flow_bp.route("/<int:plubot_id>/backup/<backup_id>", methods=["POST"])
@jwt_required()
@transactional("Error al restaurar backup")
def restore_backup(plubot_id: int, backup_id: str) -> Response:
    """Restaura una copia de seguridad para un plubot.

    POST /api/flow/{plubot_id}/backup/{backup_id}
    """
    user_id = get_jwt_identity()

    try:
        # Verificar que el backup existe
        if backup_id not in _flow_backups:
            return jsonify({"status": "error", "message": "Backup no encontrado"}), 404

        backup = _flow_backups[backup_id]
        if backup.plubot_id != plubot_id:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "El backup no pertenece a este plubot",
                    }
                ),
                403,
            )

        with get_session() as session:
            # Verificar que el plubot existe y pertenece al usuario
            plubot = (
                session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            )
            if not plubot:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Plubot no encontrado o no tienes permisos",
                        }
                    ),
                    404,
                )

            # Restaurar desde backup
            update_full_flow(session, plubot_id, backup.data)

            # Invalidar caché
            invalidate_flow_cache(plubot_id)

            return jsonify({"status": "success", "message": "Backup restaurado correctamente"}), 200
    except Exception:
        logger.exception(
            "Error al restaurar backup %s para plubot %s", backup_id, plubot_id,
        )
        return (
            jsonify({"status": "error", "message": "Error al restaurar el backup"}),
            500,
        )
