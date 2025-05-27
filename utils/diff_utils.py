"""
Utilidades para manejar actualizaciones incrementales de flujos y aristas.
Este módulo proporciona funciones para calcular diferencias entre estados
y aplicar cambios incrementales a la base de datos.
"""
import logging
import json
from sqlalchemy.orm import Session
from models.flow import Flow
from models.flow_edge import FlowEdge

logger = logging.getLogger(__name__)

def compute_flow_diff(old_state, new_state):
    """
    Calcula las diferencias entre dos estados de flujo.
    
    Args:
        old_state (dict): Estado anterior del flujo {nodes: [], edges: []}
        new_state (dict): Nuevo estado del flujo {nodes: [], edges: []}
    
    Returns:
        dict: Diferencias entre los estados {nodes_to_create: [], nodes_to_update: [], 
              nodes_to_delete: [], edges_to_create: [], edges_to_update: [], edges_to_delete: []}
    """
    old_nodes = old_state.get('nodes', [])
    new_nodes = new_state.get('nodes', [])
    old_edges = old_state.get('edges', [])
    new_edges = new_state.get('edges', [])
    
    # Mapas para búsqueda rápida
    old_nodes_map = {node.get('id'): node for node in old_nodes}
    new_nodes_map = {node.get('id'): node for node in new_nodes}
    old_edges_map = {edge.get('id'): edge for edge in old_edges}
    new_edges_map = {edge.get('id'): edge for edge in new_edges}
    
    # Calcular diferencias en nodos
    nodes_to_create = []
    nodes_to_update = []
    nodes_to_delete = []
    
    # Nodos nuevos o actualizados
    for node in new_nodes:
        node_id = node.get('id')
        if node_id not in old_nodes_map:
            nodes_to_create.append(node)
        else:
            old_node = old_nodes_map[node_id]
            if has_node_changed(old_node, node):
                nodes_to_update.append(node)
    
    # Nodos eliminados
    for node in old_nodes:
        node_id = node.get('id')
        if node_id not in new_nodes_map:
            nodes_to_delete.append(node_id)
    
    # Calcular diferencias en aristas
    edges_to_create = []
    edges_to_update = []
    edges_to_delete = []
    
    # Aristas nuevas o actualizadas
    for edge in new_edges:
        edge_id = edge.get('id')
        if edge_id not in old_edges_map:
            edges_to_create.append(edge)
        else:
            old_edge = old_edges_map[edge_id]
            if has_edge_changed(old_edge, edge):
                edges_to_update.append(edge)
    
    # Aristas eliminadas
    for edge in old_edges:
        edge_id = edge.get('id')
        if edge_id not in new_edges_map:
            edges_to_delete.append(edge_id)
    
    return {
        'nodes_to_create': nodes_to_create,
        'nodes_to_update': nodes_to_update,
        'nodes_to_delete': nodes_to_delete,
        'edges_to_create': edges_to_create,
        'edges_to_update': edges_to_update,
        'edges_to_delete': edges_to_delete
    }

def has_node_changed(old_node, new_node):
    """
    Determina si un nodo ha cambiado comparando sus propiedades relevantes.
    
    Args:
        old_node (dict): Nodo en estado anterior
        new_node (dict): Nodo en nuevo estado
    
    Returns:
        bool: True si el nodo ha cambiado, False en caso contrario
    """
    # Comparar posición
    old_pos = old_node.get('position', {})
    new_pos = new_node.get('position', {})
    
    if old_pos.get('x') != new_pos.get('x') or old_pos.get('y') != new_pos.get('y'):
        return True
    
    # Comparar datos
    old_data = old_node.get('data', {})
    new_data = new_node.get('data', {})
    
    if old_data.get('label') != new_data.get('label') or old_data.get('message') != new_data.get('message'):
        return True
    
    # Comparar tipo
    if old_node.get('type') != new_node.get('type'):
        return True
    
    return False

def has_edge_changed(old_edge, new_edge):
    """
    Determina si una arista ha cambiado comparando sus propiedades relevantes.
    
    Args:
        old_edge (dict): Arista en estado anterior
        new_edge (dict): Arista en nuevo estado
    
    Returns:
        bool: True si la arista ha cambiado, False en caso contrario
    """
    # Comparar conexiones
    if (old_edge.get('source') != new_edge.get('source') or
        old_edge.get('target') != new_edge.get('target') or
        old_edge.get('sourceHandle') != new_edge.get('sourceHandle') or
        old_edge.get('targetHandle') != new_edge.get('targetHandle')):
        return True
    
    # Comparar etiqueta
    if old_edge.get('label') != new_edge.get('label'):
        return True
    
    # Comparar tipo
    if old_edge.get('type') != new_edge.get('type'):
        return True
    
    # Comparar estilo (simplificado)
    old_style = old_edge.get('style', {})
    new_style = new_edge.get('style', {})
    
    if old_style.get('stroke') != new_style.get('stroke') or old_style.get('strokeWidth') != new_style.get('strokeWidth'):
        return True
    
    return False

def apply_flow_diff(session: Session, plubot_id: int, diff: dict):
    """
    Aplica cambios incrementales al flujo en la base de datos.
    
    Args:
        session (Session): Sesión de SQLAlchemy
        plubot_id (int): ID del plubot
        diff (dict): Diferencias a aplicar
    
    Returns:
        bool: True si se aplicaron los cambios correctamente
    """
    try:
        # Procesar nodos a crear
        for node_data in diff.get('nodes_to_create', []):
            create_node(session, plubot_id, node_data)
        
        # Procesar nodos a actualizar
        for node_data in diff.get('nodes_to_update', []):
            update_node(session, plubot_id, node_data)
        
        # Procesar nodos a eliminar (soft delete)
        for node_id in diff.get('nodes_to_delete', []):
            soft_delete_node(session, plubot_id, node_id)
        
        # Procesar aristas a crear
        for edge_data in diff.get('edges_to_create', []):
            create_edge(session, plubot_id, edge_data)
        
        # Procesar aristas a actualizar
        for edge_data in diff.get('edges_to_update', []):
            update_edge(session, plubot_id, edge_data)
        
        # Procesar aristas a eliminar (soft delete)
        for edge_id in diff.get('edges_to_delete', []):
            soft_delete_edge(session, plubot_id, edge_id)
        
        return True
    except Exception as e:
        logger.error(f"Error al aplicar diferencias de flujo: {e}")
        raise

def create_node(session: Session, plubot_id: int, node_data: dict):
    """
    Crea un nuevo nodo en la base de datos.
    
    Args:
        session (Session): Sesión de SQLAlchemy
        plubot_id (int): ID del plubot
        node_data (dict): Datos del nodo a crear
    
    Returns:
        Flow: Objeto Flow creado
    """
    position = node_data.get('position', {})
    data = node_data.get('data', {})
    
    node = Flow(
        chatbot_id=plubot_id,
        frontend_id=node_data.get('id'),
        user_message=data.get('label', ''),
        bot_response=data.get('message', ''),
        position=0,  # Legacy
        intent=node_data.get('type', 'message'),
        position_x=position.get('x', 0),
        position_y=position.get('y', 0),
        node_type=node_data.get('type', 'message'),
        metadata=node_data.get('metadata', {})
    )
    
    session.add(node)
    session.flush()  # Para obtener el ID generado
    
    logger.info(f"Nodo creado: {node.id} (frontend_id: {node.frontend_id})")
    return node

def update_node(session: Session, plubot_id: int, node_data: dict):
    """
    Actualiza un nodo existente en la base de datos.
    
    Args:
        session (Session): Sesión de SQLAlchemy
        plubot_id (int): ID del plubot
        node_data (dict): Datos del nodo a actualizar
    
    Returns:
        Flow: Objeto Flow actualizado o None si no se encontró
    """
    node = session.query(Flow).filter_by(
        chatbot_id=plubot_id,
        frontend_id=node_data.get('id'),
        is_deleted=False
    ).first()
    
    if not node:
        logger.warning(f"No se encontró el nodo con frontend_id {node_data.get('id')} para actualizar")
        return None
    
    position = node_data.get('position', {})
    data = node_data.get('data', {})
    
    # Actualizar campos
    node.user_message = data.get('label', node.user_message)
    node.bot_response = data.get('message', node.bot_response)
    node.position_x = position.get('x', node.position_x)
    node.position_y = position.get('y', node.position_y)
    node.node_type = node_data.get('type', node.node_type)
    node.intent = node_data.get('type', node.intent)
    
    # Actualizar metadatos preservando los existentes
    if node.metadata:
        metadata = node.metadata.copy()
        metadata.update(node_data.get('metadata', {}))
        node.metadata = metadata
    else:
        node.metadata = node_data.get('metadata', {})
    
    node.updated_at = None  # Trigger onupdate
    
    logger.info(f"Nodo actualizado: {node.id} (frontend_id: {node.frontend_id})")
    return node

def soft_delete_node(session: Session, plubot_id: int, node_id: str):
    """
    Marca un nodo como eliminado (soft delete).
    
    Args:
        session (Session): Sesión de SQLAlchemy
        plubot_id (int): ID del plubot
        node_id (str): ID del frontend del nodo a eliminar
    
    Returns:
        bool: True si se eliminó correctamente
    """
    node = session.query(Flow).filter_by(
        chatbot_id=plubot_id,
        frontend_id=node_id,
        is_deleted=False
    ).first()
    
    if not node:
        logger.warning(f"No se encontró el nodo con frontend_id {node_id} para eliminar")
        return False
    
    node.is_deleted = True
    node.updated_at = None  # Trigger onupdate
    
    logger.info(f"Nodo marcado como eliminado: {node.id} (frontend_id: {node.frontend_id})")
    return True

def create_edge(session: Session, plubot_id: int, edge_data: dict):
    """
    Crea una nueva arista en la base de datos.
    
    Args:
        session (Session): Sesión de SQLAlchemy
        plubot_id (int): ID del plubot
        edge_data (dict): Datos de la arista a crear
    
    Returns:
        FlowEdge: Objeto FlowEdge creado
    """
    # Buscar nodos por frontend_id
    source_node = session.query(Flow).filter_by(
        chatbot_id=plubot_id,
        frontend_id=edge_data.get('source'),
        is_deleted=False
    ).first()
    
    target_node = session.query(Flow).filter_by(
        chatbot_id=plubot_id,
        frontend_id=edge_data.get('target'),
        is_deleted=False
    ).first()
    
    if not source_node or not target_node:
        logger.warning(f"No se encontraron los nodos para la arista: {edge_data.get('source')} -> {edge_data.get('target')}")
        return None
    
    edge = FlowEdge(
        chatbot_id=plubot_id,
        source_flow_id=source_node.id,
        target_flow_id=target_node.id,
        frontend_id=edge_data.get('id'),
        condition=edge_data.get('condition', ''),
        label=edge_data.get('label', ''),
        edge_type=edge_data.get('type', 'default'),
        source_handle=edge_data.get('sourceHandle'),
        target_handle=edge_data.get('targetHandle'),
        style=edge_data.get('style', {}),
        metadata=edge_data.get('metadata', {})
    )
    
    session.add(edge)
    session.flush()  # Para obtener el ID generado
    
    logger.info(f"Arista creada: {edge.id} (frontend_id: {edge.frontend_id})")
    return edge

def update_edge(session: Session, plubot_id: int, edge_data: dict):
    """
    Actualiza una arista existente en la base de datos.
    
    Args:
        session (Session): Sesión de SQLAlchemy
        plubot_id (int): ID del plubot
        edge_data (dict): Datos de la arista a actualizar
    
    Returns:
        FlowEdge: Objeto FlowEdge actualizado o None si no se encontró
    """
    edge = session.query(FlowEdge).filter_by(
        chatbot_id=plubot_id,
        frontend_id=edge_data.get('id'),
        is_deleted=False
    ).first()
    
    if not edge:
        logger.warning(f"No se encontró la arista con frontend_id {edge_data.get('id')} para actualizar")
        return None
    
    # Actualizar campos
    edge.condition = edge_data.get('condition', edge.condition)
    edge.label = edge_data.get('label', edge.label)
    edge.edge_type = edge_data.get('type', edge.edge_type)
    edge.source_handle = edge_data.get('sourceHandle', edge.source_handle)
    edge.target_handle = edge_data.get('targetHandle', edge.target_handle)
    edge.style = edge_data.get('style', edge.style)
    
    # Actualizar metadatos preservando los existentes
    if edge.metadata:
        metadata = edge.metadata.copy()
        metadata.update(edge_data.get('metadata', {}))
        edge.metadata = metadata
    else:
        edge.metadata = edge_data.get('metadata', {})
    
    edge.updated_at = None  # Trigger onupdate
    
    logger.info(f"Arista actualizada: {edge.id} (frontend_id: {edge.frontend_id})")
    return edge

def soft_delete_edge(session: Session, plubot_id: int, edge_id: str):
    """
    Marca una arista como eliminada (soft delete).
    
    Args:
        session (Session): Sesión de SQLAlchemy
        plubot_id (int): ID del plubot
        edge_id (str): ID del frontend de la arista a eliminar
    
    Returns:
        bool: True si se eliminó correctamente
    """
    edge = session.query(FlowEdge).filter_by(
        chatbot_id=plubot_id,
        frontend_id=edge_id,
        is_deleted=False
    ).first()
    
    if not edge:
        logger.warning(f"No se encontró la arista con frontend_id {edge_id} para eliminar")
        return False
    
    edge.is_deleted = True
    edge.updated_at = None  # Trigger onupdate
    
    logger.info(f"Arista marcada como eliminada: {edge.id} (frontend_id: {edge.frontend_id})")
    return True
