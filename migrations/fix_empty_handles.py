#!/usr/bin/env python3
"""
Script de migración para corregir handles vacíos en las aristas existentes.
Actualiza todos los source_handle y target_handle vacíos a sus valores por defecto.
"""

import sys
import os
from pathlib import Path
import logging

# Añadir el directorio padre al path para importar la configuración
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Usar la URL de PostgreSQL proporcionada por el usuario
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://plubot_db_user:K8bDdaMaPVWGV6WFidXskFmkvJ579KH2@dpg-cvqulmmuk2gs73c2ea00-a.oregon-postgres.render.com/plubot_db')
logger.info(f"Usando base de datos: {DATABASE_URL.split('@')[0]}@***")

def migrate_empty_handles():
    """Migra todos los handles vacíos a sus valores por defecto."""
    
    try:
        # Determinar el tipo de base de datos y conectar apropiadamente
        if DATABASE_URL.startswith('postgresql://') or DATABASE_URL.startswith('postgres://'):
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            logger.info(f"✅ Conectado a PostgreSQL exitosamente")
        elif DATABASE_URL.startswith('sqlite:///'):
            import sqlite3
            db_path = DATABASE_URL.replace('sqlite:///', '')
            conn = sqlite3.connect(db_path)
            logger.info(f"✅ Conectado a SQLite exitosamente: {db_path}")
        else:
            logger.error(f"❌ Tipo de base de datos no soportado: {DATABASE_URL}")
            return
            
        cursor = conn.cursor()
    except Exception as e:
        logger.error(f"❌ Error conectando a la base de datos: {e}")
        return
    
    try:
        # Primero, descubrir las tablas existentes
        if DATABASE_URL.startswith('postgresql://') or DATABASE_URL.startswith('postgres://'):
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name LIKE '%edge%'
            """)
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%edge%'")
        
        edge_tables = cursor.fetchall()
        logger.info(f"Tablas relacionadas con 'edge' encontradas: {edge_tables}")
        
        # Intentar encontrar la tabla correcta
        table_name = None
        possible_names = ['flow_edges', 'flow_edge', 'flowedge', 'edges', 'edge']
        
        for name in possible_names:
            try:
                if DATABASE_URL.startswith('postgresql://') or DATABASE_URL.startswith('postgres://'):
                    cursor.execute(f"SELECT COUNT(*) FROM {name} LIMIT 1")
                else:
                    cursor.execute(f"SELECT COUNT(*) FROM {name} LIMIT 1")
                table_name = name
                logger.info(f"✅ Tabla encontrada: {table_name}")
                break
            except Exception:
                continue
        
        if not table_name:
            logger.error("❌ No se pudo encontrar la tabla de aristas")
            return
        
        # Contar aristas con handles vacíos antes de la migración
        cursor.execute(f"""
            SELECT COUNT(*) FROM {table_name} 
            WHERE source_handle = '' OR source_handle IS NULL
        """)
        empty_source_count = cursor.fetchone()[0]
        
        cursor.execute(f"""
            SELECT COUNT(*) FROM {table_name} 
            WHERE target_handle = '' OR target_handle IS NULL
        """)
        empty_target_count = cursor.fetchone()[0]
        
        logger.info(f"Encontradas {empty_source_count} aristas con source_handle vacío")
        logger.info(f"Encontradas {empty_target_count} aristas con target_handle vacío")
        
        if empty_source_count == 0 and empty_target_count == 0:
            logger.info("No hay aristas con handles vacíos. No se requiere migración.")
            return
        
        # Actualizar source_handle vacíos a 'output'
        cursor.execute(f"""
            UPDATE {table_name} 
            SET source_handle = 'output' 
            WHERE source_handle = '' OR source_handle IS NULL
        """)
        updated_source = cursor.rowcount
        
        # Actualizar target_handle vacíos a 'input'
        cursor.execute(f"""
            UPDATE {table_name} 
            SET target_handle = 'input' 
            WHERE target_handle = '' OR target_handle IS NULL
        """)
        updated_target = cursor.rowcount
        
        # Confirmar los cambios
        conn.commit()
        
        logger.info(f"✅ Migración completada exitosamente")
        logger.info(f"   - {updated_source} source_handle actualizados a 'output'")
        logger.info(f"   - {updated_target} target_handle actualizados a 'input'")
        
        # Verificar el resultado
        cursor.execute(f"""
            SELECT COUNT(*) FROM {table_name} 
            WHERE source_handle = '' OR source_handle IS NULL
        """)
        remaining_empty_source = cursor.fetchone()[0]
        
        cursor.execute(f"""
            SELECT COUNT(*) FROM {table_name} 
            WHERE target_handle = '' OR target_handle IS NULL
        """)
        remaining_empty_target = cursor.fetchone()[0]
        
        if remaining_empty_source > 0 or remaining_empty_target > 0:
            logger.warning(f"⚠️ Aún quedan {remaining_empty_source} source_handle y {remaining_empty_target} target_handle vacíos")
        else:
            logger.info("✅ Todos los handles han sido actualizados correctamente")
            
    except Exception as e:
        logger.error(f"❌ Error durante la migración: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    logger.info("🔧 Iniciando migración de handles vacíos...")
    migrate_empty_handles()
    logger.info("🎉 Migración finalizada")
