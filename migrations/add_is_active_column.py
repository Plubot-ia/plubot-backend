#!/usr/bin/env python3
"""
Migración para agregar columna is_active a la tabla whatsapp_business
"""

import os
import sys
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', '.env'))

def add_is_active_column():
    """Agrega la columna is_active a la tabla whatsapp_business"""
    
    # Obtener la URL de la base de datos directamente del entorno
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ Error: DATABASE_URL no configurada")
        print("Asegúrate de tener el archivo instance/.env con DATABASE_URL")
        return False
    
    # Convertir postgres:// a postgresql:// si es necesario
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    # Parsear la URL de la base de datos
    parsed = urlparse(database_url)
    
    try:
        # Conectar a la base de datos
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            sslmode='require'
        )
        
        cursor = conn.cursor()
        
        # Verificar si la columna ya existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'whatsapp_business' 
            AND column_name = 'is_active'
        """)
        
        if cursor.fetchone():
            print("✅ La columna is_active ya existe en whatsapp_business")
            return True
        
        # Agregar la columna is_active
        print("📝 Agregando columna is_active a whatsapp_business...")
        cursor.execute("""
            ALTER TABLE whatsapp_business 
            ADD COLUMN is_active BOOLEAN DEFAULT true
        """)
        
        # Confirmar los cambios
        conn.commit()
        print("✅ Columna is_active agregada exitosamente")
        
        # Verificar la estructura actualizada
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'whatsapp_business'
            ORDER BY ordinal_position
        """)
        
        print("\n📊 Estructura actualizada de whatsapp_business:")
        for col in cursor.fetchall():
            print(f"  - {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error ejecutando migración: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando migración para agregar columna is_active...")
    
    if add_is_active_column():
        print("\n✅ Migración completada exitosamente")
    else:
        print("\n❌ La migración falló")
        sys.exit(1)
