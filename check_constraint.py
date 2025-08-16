#!/usr/bin/env python3
"""Check WhatsApp Business foreign key constraint in production database"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment")
    exit(1)

try:
    # Add sslmode if not present
    if 'sslmode=' not in DATABASE_URL:
        if '?' in DATABASE_URL:
            DATABASE_URL += '&sslmode=require'
        else:
            DATABASE_URL += '?sslmode=require'
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Check foreign key constraints on whatsapp_business table
    cur.execute("""
        SELECT 
            tc.constraint_name,
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM 
            information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' 
          AND tc.table_name = 'whatsapp_business';
    """)
    
    constraints = cur.fetchall()
    
    print("Foreign key constraints on whatsapp_business table:")
    print("-" * 80)
    for constraint in constraints:
        print(f"Constraint: {constraint[0]}")
        print(f"  Column: {constraint[2]}")
        print(f"  References: {constraint[3]}.{constraint[4]}")
        print()
    
    if not constraints:
        print("No foreign key constraints found on whatsapp_business table")
    
    # Also check if plubots table exists
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('plubot', 'plubots')
        ORDER BY table_name;
    """)
    
    tables = cur.fetchall()
    print("\nExisting tables:")
    print("-" * 80)
    for table in tables:
        print(f"  - {table[0]}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
