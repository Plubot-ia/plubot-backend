#!/usr/bin/env python3
"""
Script para forzar la recarga de los modelos SQLAlchemy y limpiar la caché.
Esto ayudará a resolver el problema con el atributo edge_type en el modelo FlowEdge.
"""

import os
import sys
import importlib

# Añadir el directorio actual al path para poder importar los módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importar los módulos necesarios
from models import Base, get_engine, get_session
from models.flow_edge import FlowEdge

def refresh_models():
    """Forzar la recarga de los modelos y verificar que edge_type existe"""
    print("Verificando modelo FlowEdge...")
    
    # Recargar el módulo
    importlib.reload(sys.modules['models.flow_edge'])
    
    # Verificar que el atributo edge_type existe en el modelo
    if hasattr(FlowEdge, 'edge_type'):
        print("✅ El atributo edge_type existe en el modelo FlowEdge")
    else:
        print("❌ El atributo edge_type NO existe en el modelo FlowEdge")
    
    # Verificar las columnas del modelo
    columns = [column.name for column in FlowEdge.__table__.columns]
    print(f"Columnas del modelo FlowEdge: {columns}")
    
    # Verificar si edge_type está en las columnas
    if 'edge_type' in columns:
        print("✅ edge_type está en las columnas del modelo")
    else:
        print("❌ edge_type NO está en las columnas del modelo")
    
    # Verificar la estructura de la tabla en la base de datos
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'flow_edges'")
        db_columns = [row[0] for row in result]
        print(f"Columnas en la base de datos: {db_columns}")
        
        # Verificar si edge_type está en las columnas de la base de datos
        if 'edge_type' in db_columns:
            print("✅ edge_type está en la base de datos")
        else:
            print("❌ edge_type NO está en la base de datos")
    
    # Verificar si podemos crear y acceder a un objeto FlowEdge con edge_type
    try:
        edge = FlowEdge(
            chatbot_id=1,
            source_flow_id=1,
            target_flow_id=2,
            condition="test",
            edge_type="test_type"
        )
        print(f"✅ Creado objeto FlowEdge con edge_type={edge.edge_type}")
    except Exception as e:
        print(f"❌ Error al crear objeto FlowEdge: {e}")
    
    # Verificar si podemos acceder a edge_type en objetos existentes
    with get_session() as session:
        try:
            edge = session.query(FlowEdge).first()
            if edge:
                print(f"✅ Primer objeto FlowEdge en la base de datos tiene edge_type={edge.edge_type}")
            else:
                print("ℹ️ No hay objetos FlowEdge en la base de datos")
        except Exception as e:
            print(f"❌ Error al acceder a edge_type en objeto existente: {e}")
    
    print("\nPara resolver el problema, reinicia el servidor backend.")

if __name__ == "__main__":
    refresh_models()
