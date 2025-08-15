#!/usr/bin/env python3
"""Script para crear las tablas de WhatsApp Business directamente"""
import psycopg2
from psycopg2 import sql

# Conexión a la base de datos
conn = psycopg2.connect(
    "postgresql://plubot_db_user:K8bDdaMaPVWGV6WFidXskFmkvJ579KH2@dpg-cvqulmmuk2gs73c2ea00-a.oregon-postgres.render.com/plubot_db"
)
cur = conn.cursor()

try:
    # Crear tabla whatsapp_business
    cur.execute("""
        CREATE TABLE IF NOT EXISTS whatsapp_business (
            id SERIAL PRIMARY KEY,
            plubot_id INTEGER NOT NULL REFERENCES plubots(id),
            access_token TEXT,
            waba_id VARCHAR(100),
            phone_number_id VARCHAR(100),
            phone_number VARCHAR(20),
            business_name VARCHAR(255),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Crear índices para whatsapp_business
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_whatsapp_business_plubot_id ON whatsapp_business(plubot_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_business_phone_number_id ON whatsapp_business(phone_number_id);")
    
    # Crear tabla whatsapp_messages
    cur.execute("""
        CREATE TABLE IF NOT EXISTS whatsapp_messages (
            id SERIAL PRIMARY KEY,
            whatsapp_business_id INTEGER NOT NULL REFERENCES whatsapp_business(id),
            message_id VARCHAR(255),
            from_number VARCHAR(20),
            to_number VARCHAR(20),
            message_type VARCHAR(50),
            content TEXT,
            is_inbound BOOLEAN,
            status VARCHAR(50),
            message_metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delivered_at TIMESTAMP,
            read_at TIMESTAMP
        );
    """)
    
    # Crear índices para whatsapp_messages
    cur.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_message_id ON whatsapp_messages(message_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_from_number ON whatsapp_messages(from_number);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_to_number ON whatsapp_messages(to_number);")
    
    # Crear tabla whatsapp_webhook_events
    cur.execute("""
        CREATE TABLE IF NOT EXISTS whatsapp_webhook_events (
            id SERIAL PRIMARY KEY,
            whatsapp_business_id INTEGER NOT NULL REFERENCES whatsapp_business(id),
            event_type VARCHAR(50),
            event_data JSONB,
            processed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Crear índices para whatsapp_webhook_events
    cur.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_webhook_events_event_type ON whatsapp_webhook_events(event_type);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_webhook_events_created_at ON whatsapp_webhook_events(created_at);")
    
    # Confirmar los cambios
    conn.commit()
    print("✅ Tablas de WhatsApp Business creadas exitosamente")
    
    # Verificar las tablas creadas
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE 'whatsapp%'
        ORDER BY table_name;
    """)
    
    tables = cur.fetchall()
    print("\n📋 Tablas creadas:")
    for table in tables:
        print(f"  - {table[0]}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
