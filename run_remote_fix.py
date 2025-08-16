#!/usr/bin/env python3
"""
Run foreign key fix remotely on production database
"""
import os
import sys
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / 'instance' / '.env'
if env_path.exists():
    load_dotenv(env_path)

database_url = os.getenv('DATABASE_URL')
if not database_url:
    print("ERROR: DATABASE_URL not found")
    sys.exit(1)

if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

print("Connecting to production database...")
conn = psycopg2.connect(database_url)
cur = conn.cursor()

try:
    # Drop ALL foreign key constraints on plubot_id
    print("Dropping all foreign key constraints on plubot_id...")
    cur.execute("""
        SELECT constraint_name 
        FROM information_schema.table_constraints 
        WHERE table_name = 'whatsapp_business' 
        AND constraint_type = 'FOREIGN KEY'
    """)
    
    constraints = cur.fetchall()
    for constraint in constraints:
        constraint_name = constraint[0]
        print(f"  Dropping: {constraint_name}")
        cur.execute(f"ALTER TABLE whatsapp_business DROP CONSTRAINT {constraint_name} CASCADE")
    
    # Add correct constraint
    print("Adding correct foreign key constraint...")
    cur.execute("""
        ALTER TABLE whatsapp_business 
        ADD CONSTRAINT whatsapp_business_plubot_id_fkey 
        FOREIGN KEY (plubot_id) 
        REFERENCES plubots(id) 
        ON DELETE CASCADE
    """)
    
    conn.commit()
    print("\n✅ FIXED! Foreign key now points to plubots table")
    print("Try connecting WhatsApp again - it should work now!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
