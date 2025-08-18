#!/usr/bin/env python3
"""Script para corregir las foreign keys de WhatsApp Business en producción.

Este script debe ejecutarse con la DATABASE_URL de producción.
"""
import os

import psycopg2

# Get database URL from environment
database_url = os.getenv("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

try:
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    # Drop existing constraint if it exists
    cur.execute("""
        ALTER TABLE whatsapp_business
        DROP CONSTRAINT IF EXISTS whatsapp_business_plubot_id_fkey CASCADE
    """)

    # Add correct constraint
    cur.execute("""
        ALTER TABLE whatsapp_business
        ADD CONSTRAINT whatsapp_business_plubot_id_fkey
        FOREIGN KEY (plubot_id)
        REFERENCES plubots(id)
        ON DELETE CASCADE
    """)

    conn.commit()

except (psycopg2.Error, ValueError):
    conn.rollback()
finally:
    cur.close()
    conn.close()
