#!/usr/bin/env python3
"""
Emergency fix for production foreign key issue
Run this directly on Render console
"""
import os
import psycopg2

# Get database URL from environment
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

conn = psycopg2.connect(database_url)
cur = conn.cursor()

try:
    # Drop the problematic constraint
    cur.execute("""
        ALTER TABLE whatsapp_business 
        DROP CONSTRAINT IF EXISTS whatsapp_business_plubot_id_fkey CASCADE
    """)
    print("Dropped old constraint")
    
    # Add correct constraint
    cur.execute("""
        ALTER TABLE whatsapp_business 
        ADD CONSTRAINT whatsapp_business_plubot_id_fkey 
        FOREIGN KEY (plubot_id) 
        REFERENCES plubots(id) 
        ON DELETE CASCADE
    """)
    print("Added new constraint to plubots table")
    
    conn.commit()
    print("✓ Fixed successfully!")
    
except Exception as e:
    print(f"Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
