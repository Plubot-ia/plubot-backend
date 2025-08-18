#!/usr/bin/env python3
"""Script para ejecutar la corrección de foreign keys en producción."""
import os
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv
import psycopg2

# Load environment variables
env_path = Path(__file__).parent / "instance" / ".env"
if env_path.exists():
    load_dotenv(env_path)

database_url = os.getenv("DATABASE_URL")
if not database_url:
    sys.exit(1)

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

conn = psycopg2.connect(database_url)
cur = conn.cursor()

try:
    # Drop ALL foreign key constraints on plubot_id
    cur.execute("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'whatsapp_business'
        AND constraint_type = 'FOREIGN KEY'
    """)

    constraints = cur.fetchall()
    for constraint in constraints:
        constraint_name = constraint[0]
        cur.execute(f"ALTER TABLE whatsapp_business DROP CONSTRAINT {constraint_name} CASCADE")

    # Add correct constraint
    cur.execute("""
        ALTER TABLE whatsapp_business
        ADD CONSTRAINT whatsapp_business_plubot_id_fkey
        FOREIGN KEY (plubot_id)
        REFERENCES plubots(id)
        ON DELETE CASCADE
    """)

    conn.commit()

except (subprocess.CalledProcessError, OSError):
    conn.rollback()
finally:
    cur.close()
    conn.close()
