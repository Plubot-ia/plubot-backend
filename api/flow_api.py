"""
API para la gestión de flujos de Plubots.
Este módulo proporciona endpoints optimizados para manejar flujos
con actualizaciones incrementales, caché y transacciones atómicas.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.orm import joinedload
import logging
import json
import time
import uuid

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
@cached("flow", 300)  # Caché de 5 minutos
def get_flow(plubot_id):
    """
    Obtiene el flujo completo de un plubot.
    
    GET /api/flow/{plubot_id}
    """
    user_id = get_jwt_identity()
    
    # Verificar si está en caché
    cache_key = get_cache_key("flow", plubot_id)
    found, cached_data = cache_get(cache_key)
    if found:
        logger.info(f"Flujo recuperado de caché para plubot {plubot_id}")
        return jsonify({"status": "success", "data": cached_data, "source": "cache"}), 200
    
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
            
            # Convertir flujos a formato esperado por el frontend
            nodes = []
            for flow in flows:
                node = {
                    'id': flow.frontend_id or str(flow.id),
                    'type': flow.node_type or 'message',
                    'position': {'x': flow.position_x or 0, 'y': flow.position_y or 0},
                    'data': {
                        'label': flow.user_message,
                        'message': flow.bot_response
                    }
                }
                
                # Añadir metadatos si existen
                if flow.node_metadata:
                    node['metadata'] = flow.node_metadata
                
                nodes.append(node)
            
            # Obtener aristas
            edges = session.query(FlowEdge).filter_by(
                chatbot_id=plubot_id,
                is_deleted=False
            ).all()
            
            # Convertir aristas a formato esperado por el frontend
            formatted_edges = []
            for edge in edges:
                try:
                    # Buscar los nodos correspondientes
                    source_node = next((n for n in flows if n.id == edge.source_flow_id), None)
                    target_node = next((n for n in flows if n.id == edge.target_flow_id), None)
                    
                    if not source_node or not target_node:
                        logger.warning(f"Arista {edge.id} tiene nodos inválidos: {edge.source_flow_id} -> {edge.target_flow_id}")
                        continue
                    
                    formatted_edge = {
                        'id': edge.frontend_id or str(edge.id),
                        'source': source_node.frontend_id or str(source_node.id),
                        'target': target_node.frontend_id or str(target_node.id),
                        'type': edge.edge_type or 'default',
                        'sourceHandle': edge.source_handle,
                        'targetHandle': edge.target_handle
                    }
                    
                    # Añadir etiqueta si existe
                    if edge.label:
                        formatted_edge['label'] = edge.label
                    
                    # Añadir estilo si existe
                    if edge.style:
                        formatted_edge['style'] = edge.style
                    
                    # Añadir metadatos si existen
                    if edge.edge_metadata:
                        formatted_edge['metadata'] = edge.edge_metadata
                    
                    formatted_edges.append(formatted_edge)
                except Exception as e:
                    logger.error(f"Error al formatear arista {edge.id}: {e}")
                    continue
            
            # Datos completos para el frontend
            flow_data = {
                'nodes': nodes,
                'edges': formatted_edges,
                'name': plubot.name
            }
            
            # Guardar en caché
            cache_set(cache_key, flow_data, 300)  # 5 minutos
            
            return jsonify({"status": "success", "data": flow_data}), 200
    except Exception as e:
        logger.error(f"Error al obtener flujo para plubot {plubot_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@flow_bp.route('/<int:plubot_id>', methods=['PATCH'])
@jwt_required()
@transactional("Error al actualizar flujo")
@backup_before_operation(create_flow_backup)
def update_flow(plubot_id):
    """
    Actualiza el flujo de un plubot de forma incremental.
    
    PATCH /api/flow/{plubot_id}
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    try:
        with get_session() as session:
            # Verificar que el plubot existe y pertenece al usuario
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                return jsonify({"status": "error", "message": "Plubot no encontrado o no tienes permisos"}), 404
            
            # Verificar si se proporcionó un diff o datos completos
            diff = data.get('diff')
            
            with atomic_transaction(session, f"Error al actualizar flujo para plubot {plubot_id}"):
                if diff:
                    # Aplicar cambios incrementales
                    logger.info(f"Aplicando diff para plubot {plubot_id}: {len(diff.get('nodes_to_create', []))} nodos a crear, {len(diff.get('edges_to_create', []))} aristas a crear")
                    apply_flow_diff(session, plubot_id, diff)
                else:
                    # Compatibilidad con clientes antiguos (envío completo)
                    logger.info(f"Actualizando flujo completo para plubot {plubot_id}")
                    update_full_flow(session, plubot_id, data)
            
            # Invalidar caché
            invalidate_flow_cache(plubot_id)
            
            return jsonify({"status": "success", "message": "Flujo actualizado correctamente"}), 200
    except Exception as e:
        logger.error(f"Error al actualizar flujo para plubot {plubot_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@transactional("Error al actualizar flujo completo")
def update_full_flow(session, plubot_id, data):
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
    
    # Crear mapa para almacenar la relación entre IDs del frontend y backend
    node_id_map = {}
    
    # Guardar nuevos flujos
    for node in nodes:
        node_id = node.get('id')
        node_type = node.get('type', 'message')
        position = node.get('position', {})
        data = node.get('data', {})
        
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
            existing_node.node_metadata = node.get('metadata', {})
            
            node_id_map[node_id] = existing_node.id
        else:
            # Crear nuevo nodo
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
                node_metadata=node.get('metadata', {})
            )
            
            session.add(new_node)
            session.flush()  # Para obtener el ID generado
            
            node_id_map[node_id or new_node.frontend_id] = new_node.id
    
    # Guardar nuevas aristas
    for edge in edges:
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
            existing_edge.style = edge.get('style', {})
            existing_edge.edge_metadata = edge.get('metadata', {})
            existing_edge.is_deleted = False
        else:
            # Crear nueva arista
            new_edge = FlowEdge(
                chatbot_id=plubot_id,
                frontend_id=edge.get('id') or generate_frontend_id('edge'),
                source_flow_id=node_id_map[source_id],
                target_flow_id=node_id_map[target_id],
                source_handle=edge.get('sourceHandle'),
                target_handle=edge.get('targetHandle'),
                edge_type=edge.get('type', 'default'),
                label=edge.get('label', ''),
                style=edge.get('style', {}),
                edge_metadata=edge.get('metadata', {})
            )
            
            session.add(new_edge)
    
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
