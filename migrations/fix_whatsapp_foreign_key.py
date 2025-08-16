#!/usr/bin/env python3
"""
Migration script to fix WhatsApp Business foreign key constraint
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / 'instance' / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    print(f"Warning: {env_path} not found, using system environment variables")

def get_db_connection():
    """Get database connection from DATABASE_URL"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")
    
    # Convert postgres:// to postgresql:// if needed
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    return psycopg2.connect(database_url)

def fix_foreign_key():
    """Fix the foreign key constraint for whatsapp_business table"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # First, check if the constraint exists
        cur.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'whatsapp_business' 
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name LIKE '%plubot_id%'
        """)
        
        constraints = cur.fetchall()
        print(f"Found {len(constraints)} foreign key constraints for plubot_id")
        
        # Drop existing foreign key constraints
        for constraint in constraints:
            constraint_name = constraint[0]
            print(f"Dropping constraint: {constraint_name}")
            cur.execute(f"ALTER TABLE whatsapp_business DROP CONSTRAINT IF EXISTS {constraint_name}")
        
        # Check if plubots table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'plubots'
            )
        """)
        plubots_exists = cur.fetchone()[0]
        
        if not plubots_exists:
            print("ERROR: Table 'plubots' does not exist!")
            # Check what tables do exist
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE 'plu%'
                ORDER BY table_name
            """)
            tables = cur.fetchall()
            print("Available tables starting with 'plu':")
            for table in tables:
                print(f"  - {table[0]}")
            
            # Check if 'plubot' table exists (without 's')
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'plubot'
                )
            """)
            plubot_exists = cur.fetchone()[0]
            
            if plubot_exists:
                print("\nTable 'plubot' exists! Creating foreign key to 'plubot' table instead.")
                # Add new foreign key constraint to plubot table
                cur.execute("""
                    ALTER TABLE whatsapp_business 
                    ADD CONSTRAINT whatsapp_business_plubot_id_fkey 
                    FOREIGN KEY (plubot_id) 
                    REFERENCES plubot(id) 
                    ON DELETE CASCADE
                """)
                print("✓ Foreign key constraint added successfully to 'plubot' table")
            else:
                print("\nERROR: Neither 'plubots' nor 'plubot' table exists!")
                return False
        else:
            # Add new foreign key constraint to plubots table
            print("Adding foreign key constraint to 'plubots' table")
            cur.execute("""
                ALTER TABLE whatsapp_business 
                ADD CONSTRAINT whatsapp_business_plubot_id_fkey 
                FOREIGN KEY (plubot_id) 
                REFERENCES plubots(id) 
                ON DELETE CASCADE
            """)
            print("✓ Foreign key constraint added successfully to 'plubots' table")
        
        # Commit the changes
        conn.commit()
        print("\n✓ Migration completed successfully!")
        
        # Verify the constraint
        cur.execute("""
            SELECT 
                tc.constraint_name,
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' 
                AND tc.table_name = 'whatsapp_business'
                AND kcu.column_name = 'plubot_id'
        """)
        
        result = cur.fetchone()
        if result:
            print(f"\nVerified: Foreign key from whatsapp_business.plubot_id -> {result[3]}.{result[4]}")
        
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    print("Starting foreign key fix migration...")
    success = fix_foreign_key()
    sys.exit(0 if success else 1)
