"""
API para la gestión de flujos de Plubots.
Este módulo proporciona endpoints optimizados para manejar flujos
con actualizaciones incrementales, caché y transacciones atómicas.
"""
from flask import Blueprint, request, jsonify, current_app as app # app es necesario para la caché
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.orm import joinedload
import logging
import json
import time
import uuid
import traceback

from config.settings import get_session
from models.plubot import Plubot
from models.flow import Flow
from models.flow_edge import FlowEdge
from utils.diff_utils import compute_flow_diff, apply_flow_diff
from utils.id_utils import generate_frontend_id, get_backend_id, create_id_mapping
from utils.transaction_utils import atomic_transaction, transactional, with_retry, backup_before_operation
from services.cache_service import cached, invalidate_flow_cache, cache_get, cache_set, get_cache_key

flow_bp = Blueprint('flow', __name__)
logger = logging.getLogger(__name__)

# Helper para validación JSON
def is_json_serializable(data):
    if data is None: # None es JSON null, que es válido
        return True
    try:
        json.dumps(data)
        return True
    except (TypeError, OverflowError) as e:
        logger.warning(f"Data is not JSON serializable: {e}. Data: {str(data)[:200]}") # Loguea el error y parte del dato
        return False

# Modelo para respaldo de flujos
class FlowBackup:
    def __init__(self, plubot_id, data, version=1):
        self.plubot_id = plubot_id
        self.data = data
        self.version = version
        self.id = str(uuid.uuid4())
        self.timestamp = time.time()

# Almacén temporal de respaldos (en producción usaríamos la base de datos)
_flow_backups = {}

def create_flow_backup(session, plubot_id):
    """Crea una copia de seguridad del flujo actual"""
    # Obtener flujos y aristas
    flows = session.query(Flow).filter_by(chatbot_id=plubot_id, is_deleted=False).all()
    edges = session.query(FlowEdge).filter_by(chatbot_id=plubot_id, is_deleted=False).all()
    
    # Convertir a formato serializable
    flow_data = {
        'nodes': [
            {
                'id': flow.frontend_id or str(flow.id),
                'type': flow.node_type,
                'position': {'x': flow.position_x or 0, 'y': flow.position_y or 0},
                'data': {
                    'label': flow.user_message,
                    'message': flow.bot_response
                },
                'metadata': flow.node_metadata
            } for flow in flows
        ],
        'edges': [
            {
                'id': edge.frontend_id or str(edge.id),
                'source': next((f.frontend_id for f in flows if f.id == edge.source_flow_id), str(edge.source_flow_id)),
                'target': next((f.frontend_id for f in flows if f.id == edge.target_flow_id), str(edge.target_flow_id)),
                'sourceHandle': edge.source_handle,
                'targetHandle': edge.target_handle,
                'type': edge.edge_type,
                'label': edge.label,
                'style': edge.style,
                'metadata': edge.edge_metadata
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

@flow_bp.route('/<int:plubot_id>', methods=['GET'])
@jwt_required()
def get_flow(plubot_id):
    """
    Obtiene el flujo completo de un plubot.
    
    GET /api/flow/{plubot_id}
    """
    user_id = get_jwt_identity()

    # Usar el sistema de caché de services.cache_service
    # La clave debe ser compatible con invalidate_flow_cache que usa cache_clear_by_prefix(f"flow:{plubot_id}")
    # get_cache_key(prefix, *args) genera 'prefix:hash_of_args'
    cache_key = get_cache_key(f"flow:{plubot_id}", "full_details")
    
    try:
        found, cached_flow = cache_get(cache_key)
        if found:
            logger.info(f"[GET /api/flow/{plubot_id}] Cache hit for key {cache_key}. Returning cached data from _memory_cache.")
            return jsonify(status="success", data=cached_flow, message="Flujo recuperado desde cache exitosamente"), 200
        logger.info(f"[GET /api/flow/{plubot_id}] Cache miss for key {cache_key} in _memory_cache.")
    except Exception as e:
        logger.error(f"[GET /api/flow/{plubot_id}] Error accessing _memory_cache for GET: {e}")

    try:
        with get_session() as session:
            # Verificar que el plubot existe y pertenece al usuario
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                return jsonify({"status": "error", "message": "Plubot no encontrado o no tienes permisos"}), 404
            
            # Consulta optimizada con carga anticipada (eager loading)
            flows = session.query(Flow).filter_by(
                chatbot_id=plubot_id,
                is_deleted=False
            ).options(
                joinedload(Flow.outgoing_edges),
                joinedload(Flow.incoming_edges)
            ).all()
            logger.info(f"[GET /api/flow/{plubot_id}] DB query for flows (nodes) returned: {len(flows)} items.")
            
            # Convertir flujos a formato esperado por el frontend
            nodes = []
            for flow in flows:
                node = {
                    'id': flow.frontend_id or str(flow.id),
                    'type': flow.node_type or 'message',
                    'position': {'x': flow.position_x or 0, 'y': flow.position_y or 0},
                    'data': flow.node_metadata.copy() if flow.node_metadata else {
                        'label': flow.user_message, # Fallback si node_metadata es None
                        'message': flow.bot_response # Fallback si node_metadata es None
                    }
                }
                # node_metadata ya está incorporado en node['data'], por lo que la asignación a node['metadata'] se elimina.
                
                nodes.append(node)
            
            # Obtener aristas
            edges = session.query(FlowEdge).filter_by(
                chatbot_id=plubot_id,
                is_deleted=False
            ).all()
            logger.info(f"[GET /api/flow/{plubot_id}] DB query for edges returned: {len(edges)} items.")
            
            # Convertir aristas a formato esperado por el frontend
            formatted_edges = []
            for edge in edges:
                try:
                    # Buscar los nodos correspondientes
                    source_node = next((n for n in flows if n.id == edge.source_flow_id), None)
                    target_node = next((n for n in flows if n.id == edge.target_flow_id), None)

                    if not source_node or not target_node:
                        logger.warning(f"[GET /api/flow/{plubot_id}] Omitiendo arista {edge.id} debido a que falta el nodo fuente/destino. Source ID: {edge.source_flow_id} (encontrado: {source_node is not None}), Target ID: {edge.target_flow_id} (encontrado: {target_node is not None})")
                        continue
                    
                    formatted_edge = {
                        'id': str(edge.id), # Asegurar ID es string
                        'source': source_node.frontend_id or str(source_node.id),
                        'target': target_node.frontend_id or str(target_node.id),
                        'sourceHandle': edge.source_handle,
                        'targetHandle': edge.target_handle,
                        'type': edge.edge_type or 'default', # Proporcionar un valor predeterminado
                        'animated': edge.animated if edge.animated is not None else True, # Proporcionar un valor predeterminado
                        'label': edge.label or '', # Proporcionar un valor predeterminado
                    }
                    # Añadir estilo si existe
                    if edge.style:
                        formatted_edge['style'] = edge.style
                    
                    # Añadir metadatos si existen
                    if edge.edge_metadata:
                        formatted_edge['metadata'] = edge.edge_metadata
                    
                    formatted_edges.append(formatted_edge)
                except Exception as e:
                    logger.error(f"[GET /api/flow/{plubot_id}] Error al formatear arista {edge.id} (Source: {edge.source_flow_id}, Target: {edge.target_flow_id}): {e}. Traceback: {traceback.format_exc()}")
                    continue
            
            # Datos completos para el frontend
            flow_data = {
                'nodes': nodes,
                'edges': formatted_edges,
                'name': plubot.name, # Asegurar que el nombre del Plubot se incluya
            }
            
            try:
                cache_set(cache_key, flow_data, expire_seconds=3600) # Cache por 1 hora en _memory_cache
                logger.info(f"[GET /api/flow/{plubot_id}] Data set in _memory_cache for key {cache_key}.")
            except Exception as e:
                logger.error(f"[GET /api/flow/{plubot_id}] Error setting _memory_cache: {e}")
            
            if flow_data.get('nodes'):
                sample_nodes_log = []
                # Loguear hasta 2 nodos de decisión o los primeros 3 nodos si no hay de decisión
                decision_nodes_logged = 0
                general_nodes_logged = 0
                for i, node_item in enumerate(flow_data['nodes']):
                    is_decision_node = node_item.get('type') == 'decision'
                    log_this_node = False

                    if is_decision_node and decision_nodes_logged < 2:
                        log_this_node = True
                        decision_nodes_logged += 1
                    elif not is_decision_node and general_nodes_logged < 3 and decision_nodes_logged == 0: # Si aún no logueamos de decisión, logueamos generales
                        log_this_node = True
                        general_nodes_logged += 1
                    elif general_nodes_logged + decision_nodes_logged < 3: # Asegurar al menos algunos logs si no se cumplen los otros
                        log_this_node = True
                        general_nodes_logged +=1 # Contamos como general para el límite total
                        
                    if log_this_node:
                        node_data_keys = list(node_item.get('data', {}).keys()) if node_item.get('data') else 'No data field'
                        sample_nodes_log.append(f"Node {i} (ID: {node_item.get('id')}, Type: {node_item.get('type')}): Data keys: {node_data_keys}")
                        if is_decision_node:
                             sample_nodes_log.append(f"  DecisionNode Data: { {k: v for k, v in node_item.get('data', {}).items() if k in ['label', 'question']} }") # Mostrar label y question

                    if decision_nodes_logged >= 2 and general_nodes_logged >=1: # Limite para no loguear demasiado
                        if len(flow_data['nodes']) > 3:
                           sample_nodes_log.append(f"... y {len(flow_data['nodes']) - len(sample_nodes_log)} más nodos.")
                        break
                logger.info(f"[GET /api/flow/{plubot_id}] Sample nodes being returned: {sample_nodes_log}")
            logger.info(f"[GET /api/flow/{plubot_id}] Returning full flow_data summary: nodes_count={len(flow_data['nodes']) if flow_data.get('nodes') else 0}, edges_count={len(flow_data['edges']) if flow_data.get('edges') else 0}, name='{flow_data.get('name')}'")
            return jsonify({"status": "success", "data": flow_data}), 200
    except Exception as e:
        # Capturar el traceback completo
        tb_str = traceback.format_exc()
        
        # Preparar el mensaje de error base
        log_message = f"Error en get_flow para plubot_id {plubot_id}. Excepción: {str(e)}\nTraceback:\n{tb_str}"
        
        # Intentar obtener una representación de flow_data para el log
        if 'flow_data' in locals():
            try:
                # Intentar serializar con json.dumps para ver si da el mismo error o más info
                # default=str para manejar tipos comunes no serializables como datetime
                problematic_data_log = json.dumps(flow_data, indent=2, default=str)
                log_message += f"\n\nIntento de volcado de flow_data (puede estar incompleto o ser la causa del error):\n{problematic_data_log}"
            except Exception as dump_error:
                # Si json.dumps también falla, registrar ese error y un repr de flow_data
                log_message += f"\n\njson.dumps también falló al intentar volcar flow_data: {str(dump_error)}"
                log_message += f"\nRepresentación de flow_data (repr):\n{repr(flow_data)}"
        else:
            log_message += "\n\nflow_data no estaba definido en el momento de la excepción."
            
        logger.error(log_message)
        
        # Devolver un mensaje de error genérico al cliente
        return jsonify({"status": "error", "message": "Error interno del servidor al obtener los datos del flujo."}), 500


@flow_bp.route('/<int:plubot_id>', methods=['PATCH'])
@jwt_required()
def patch_flow(plubot_id):
    """
    Actualiza el flujo de un plubot utilizando el método PATCH.
    Espera un payload JSON con 'nodes', 'edges', y opcionalmente 'name'.
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    logger.info(f"[PATCH /api/flow/{plubot_id}] Received raw data: {data}")

    if not data:
        return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

    flow_nodes = data.get("nodes")
    logger.info(f"[PATCH /api/flow/{plubot_id}] Extracted: nodes_count={len(flow_nodes) if flow_nodes is not None else 'None'}, edges_count={len(data.get('edges')) if data.get('edges') is not None else 'None'}, name='{data.get('name')}'")
    flow_edges = data.get("edges")
    flow_name = data.get("name")  # El nombre es opcional para la actualización

    # Los nodos y aristas son fundamentales para la actualización del flujo
    if flow_nodes is None or not isinstance(flow_nodes, list) \
            or flow_edges is None or not isinstance(flow_edges, list):
        return jsonify({"status": "error", "message": "Payload must contain 'nodes' and 'edges' as lists."}), 400

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
                return jsonify({"status": "error", "message": "Plubot no encontrado o no tienes permisos"}), 404

            # Usar transacción atómica para la operación de actualización completa
            with atomic_transaction(session, f"Error al actualizar flujo (PATCH) para plubot {plubot_id}"):
                # Crear una copia de seguridad antes de la operación principal
                create_flow_backup(session, plubot_id)
                
                # Llamar a la lógica existente para actualizar el flujo
                update_full_flow(session, plubot_id, flow_data_for_update)
            
            # Invalidar la caché después de una actualización exitosa
            invalidate_flow_cache(plubot_id)
            
            logger.info(f"Flujo actualizado correctamente para plubot {plubot_id} por usuario {user_id}")
            return jsonify({"status": "success", "message": "Flujo actualizado correctamente"}), 200
            
    except ValueError as ve:
        # Errores de validación específicos (ej. datos no serializables JSON desde update_full_flow)
        logger.error(f"Error de validación al actualizar flujo (PATCH) para plubot {plubot_id}: {ve}")
        return jsonify({"status": "error", "message": str(ve)}), 400
    except Exception as e:
        # Capturar el traceback completo para errores inesperados
        tb_str = traceback.format_exc()
        logger.error(f"Error en patch_flow para plubot {plubot_id}: {e}\nTraceback:\n{tb_str}")
        return jsonify({"status": "error", "message": "Error interno del servidor al actualizar el flujo."}), 500


@transactional("Error al actualizar flujo completo")
def update_full_flow(session, plubot_id, data):
    logger.info(f"[update_full_flow - plubot_id={plubot_id}] Starting update. Received: nodes_count={len(data.get('nodes', []))}, edges_count={len(data.get('edges', []))}, name='{data.get('name')}'")
    """
    Actualiza el flujo completo de un plubot.
    Esta función es para compatibilidad con clientes antiguos.
    """
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])
    name = data.get('name')
    
    # Actualizar nombre del plubot si se proporciona
    if name:
        plubot = session.query(Plubot).filter_by(id=plubot_id).first()
        if plubot:
            plubot.name = name
    
    # Marcar todos los nodos y aristas como eliminados (soft delete)
    session.query(Flow).filter_by(chatbot_id=plubot_id).update({"is_deleted": True})
    session.query(FlowEdge).filter_by(chatbot_id=plubot_id).update({"is_deleted": True})
    logger.info(f"[update_full_flow - plubot_id={plubot_id}] Marked existing nodes and edges as deleted.")
    
    # Crear mapa para almacenar la relación entre IDs del frontend y backend
    node_id_map = {}
    
    # Guardar nuevos flujos
    for node_idx, node in enumerate(nodes):
        logger.debug(f"[update_full_flow - plubot_id={plubot_id}] Processing node {node_idx + 1}/{len(nodes)}: ID={node.get('id')}")
        node_id = node.get('id')
        node_type = node.get('type', 'message')
        position = node.get('position', {})
        data = node.get('data', {})
        
        # Log data being saved for decision nodes
        if node.get('type') == 'decision':
            logger.info(f"[update_full_flow - plubot_id={plubot_id}] Saving DecisionNode ID {node.get('id')} with data: {node.get('data', {})}")
        
        # Verificar si ya existe un nodo con este frontend_id
        existing_node = session.query(Flow).filter_by(
            chatbot_id=plubot_id,
            frontend_id=node_id
        ).first()
        
        if existing_node:
            # Actualizar nodo existente
            existing_node.user_message = data.get('label', '')
            existing_node.bot_response = data.get('message', '')
            existing_node.position_x = position.get('x', 0)
            existing_node.position_y = position.get('y', 0)
            existing_node.node_type = node_type
            existing_node.intent = node_type
            existing_node.is_deleted = False
            
            # Usar node.get('data') como base para node_metadata
            node_metadata = data.copy()  # 'data' es node.get('data', {}) de la línea 363

            # Añadir width, height, y style si están disponibles en el nodo principal
            if node.get('width') is not None:
                node_metadata['width'] = node.get('width')
            if node.get('height') is not None:
                node_metadata['height'] = node.get('height')
            
            node_style_from_node = node.get('style', {})
            if node_style_from_node: # Asegurar que el estilo no esté vacío antes de añadirlo
                node_metadata['style'] = node_style_from_node

            if not is_json_serializable(node_metadata):
                raise ValueError(f"Node metadata for node ID {node_id} is not JSON serializable.")
            existing_node.node_metadata = node_metadata
            
            # La asignación a existing_node.style se elimina ya que style ahora es parte de node_metadata
            
            node_id_map[node_id] = existing_node.id
        else:
            # Crear nuevo nodo
            node_metadata_new = data.copy() # 'data' es node.get('data', {}) de la línea 363
            node_metadata_new['width'] = node.get('width')
            node_metadata_new['height'] = node.get('height')
            node_metadata_new['style'] = node.get('style', {})

            if not is_json_serializable(node_metadata_new):
                raise ValueError(f"Combined node_metadata for new node ID {node_id} (including width, height, style) is not JSON serializable.")

            new_node = Flow(
                chatbot_id=plubot_id,
                frontend_id=node_id or generate_frontend_id('node'),
                user_message=data.get('label', ''),
                bot_response=data.get('message', ''),
                position=0,  # Legacy
                intent=node_type,
                node_type=node_type,
                position_x=position.get('x', 0),
                position_y=position.get('y', 0),
                node_metadata=node_metadata_new
            )
            
            session.add(new_node)
            session.flush()  # Para obtener el ID generado
            
            node_id_map[node_id] = new_node.id
    
    # Guardar nuevas aristas
    for edge_idx, edge in enumerate(edges):
        logger.debug(f"[update_full_flow - plubot_id={plubot_id}] Processing edge {edge_idx + 1}/{len(edges)}: ID={edge.get('id')}")
        source_id = edge.get('source')
        target_id = edge.get('target')
        
        # Verificar que los nodos existen
        if source_id not in node_id_map or target_id not in node_id_map:
            logger.warning(f"Arista con nodos inválidos: {source_id} -> {target_id}")
            continue
        
        # Verificar si ya existe una arista con este frontend_id
        existing_edge = None
        if edge.get('id'):
            existing_edge = session.query(FlowEdge).filter_by(
                chatbot_id=plubot_id,
                frontend_id=edge.get('id')
            ).first()
        
        if existing_edge:
            # Actualizar arista existente
            existing_edge.source_flow_id = node_id_map[source_id]
            existing_edge.target_flow_id = node_id_map[target_id]
            existing_edge.source_handle = edge.get('sourceHandle')
            existing_edge.target_handle = edge.get('targetHandle')
            existing_edge.edge_type = edge.get('type', 'default')
            existing_edge.label = edge.get('label', '')
            
            edge_style_existing = edge.get('style', {})
            if not is_json_serializable(edge_style_existing):
                raise ValueError(f"Edge style for existing edge ID {edge.get('id')} is not JSON serializable.")
            existing_edge.style = edge_style_existing
            
            edge_metadata_existing = edge.get('metadata', {})
            if not is_json_serializable(edge_metadata_existing):
                raise ValueError(f"Edge metadata for existing edge ID {edge.get('id')} is not JSON serializable.")
            existing_edge.edge_metadata = edge_metadata_existing
            existing_edge.is_deleted = False
        else:
            # Crear nueva arista
            edge_style_new = edge.get('style', {})
            if not is_json_serializable(edge_style_new):
                raise ValueError(f"Edge style for new edge ID {edge.get('id')} is not JSON serializable.")
            
            edge_metadata_new = edge.get('metadata', {})
            if not is_json_serializable(edge_metadata_new):
                raise ValueError(f"Edge metadata for new edge ID {edge.get('id')} is not JSON serializable.")

            new_edge = FlowEdge(
                chatbot_id=plubot_id,
                frontend_id=edge.get('id') or generate_frontend_id('edge'),
                source_flow_id=node_id_map[source_id],
                target_flow_id=node_id_map[target_id],
                source_handle=edge.get('sourceHandle'),
                target_handle=edge.get('targetHandle'),
                edge_type=edge.get('type', 'default'),
                label=edge.get('label', ''),
                style=edge_style_new,
                edge_metadata=edge_metadata_new
            )
            
            session.add(new_edge)
    
    logger.info(f"[update_full_flow - plubot_id={plubot_id}] Update process completed. Node ID map created with {len(node_id_map)} entries. Processed {len(nodes)} nodes and {len(edges)} edges.")
    return True

@flow_bp.route('/<int:plubot_id>/backup', methods=['GET'])
@jwt_required()
def list_backups(plubot_id):
    """
    Lista las copias de seguridad disponibles para un plubot.
    
    GET /api/flow/{plubot_id}/backup
    """
    user_id = get_jwt_identity()
    
    try:
        with get_session() as session:
            # Verificar que el plubot existe y pertenece al usuario
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                return jsonify({"status": "error", "message": "Plubot no encontrado o no tienes permisos"}), 404
            
            # Obtener backups
            backups = [
                {
                    'id': b.id,
                    'version': b.version,
                    'timestamp': b.timestamp
                }
                for b in _flow_backups.values()
                if b.plubot_id == plubot_id
            ]
            
            # Ordenar por versión descendente
            backups.sort(key=lambda b: b['version'], reverse=True)
            
            return jsonify({"status": "success", "backups": backups}), 200
    except Exception as e:
        logger.error(f"Error al listar backups para plubot {plubot_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@flow_bp.route('/<int:plubot_id>/backup/<backup_id>', methods=['POST'])
@jwt_required()
@transactional("Error al restaurar backup")
def restore_backup(plubot_id, backup_id):
    """
    Restaura una copia de seguridad para un plubot.
    
    POST /api/flow/{plubot_id}/backup/{backup_id}
    """
    user_id = get_jwt_identity()
    
    try:
        # Verificar que el backup existe
        if backup_id not in _flow_backups:
            return jsonify({"status": "error", "message": "Backup no encontrado"}), 404
        
        backup = _flow_backups[backup_id]
        if backup.plubot_id != plubot_id:
            return jsonify({"status": "error", "message": "El backup no pertenece a este plubot"}), 403
        
        with get_session() as session:
            # Verificar que el plubot existe y pertenece al usuario
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                return jsonify({"status": "error", "message": "Plubot no encontrado o no tienes permisos"}), 404
            
            with atomic_transaction(session, f"Error al restaurar backup {backup_id} para plubot {plubot_id}"):
                # Marcar todos los nodos y aristas como eliminados (soft delete)
                session.query(Flow).filter_by(chatbot_id=plubot_id).update({"is_deleted": True})
                session.query(FlowEdge).filter_by(chatbot_id=plubot_id).update({"is_deleted": True})
                
                # Restaurar desde backup
                update_full_flow(session, plubot_id, backup.data)
            
            # Invalidar caché
            invalidate_flow_cache(plubot_id)
            
            return jsonify({"status": "success", "message": "Backup restaurado correctamente"}), 200
    except Exception as e:
        logger.error(f"Error al restaurar backup {backup_id} para plubot {plubot_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
