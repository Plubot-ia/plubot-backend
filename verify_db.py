#!/usr/bin/env python3
import psycopg2
from psycopg2 import sql

# Conexión directa a la base de datos
DATABASE_URL = "postgresql://plubot_db_user:K8bDdaMaPVWGV6WFidXskFmkvJ579KH2@dpg-cvqulmmuk2gs73c2ea00-a.oregon-postgres.render.com/plubot_db?sslmode=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # 1. Verificar qué tablas existen
    cur.execute("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
        ORDER BY tablename;
    """)
    
    print("Tablas en la base de datos:")
    tables = cur.fetchall()
    for table in tables:
        print(f"  - {table[0]}")
    
    # 2. Verificar la estructura de la tabla plubots
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'plubots' 
        AND table_schema = 'public'
        ORDER BY ordinal_position;
    """)
    
    print("\nColumnas en tabla 'plubots':")
    columns = cur.fetchall()
    for col in columns:
        print(f"  - {col[0]}: {col[1]}")
    
    # 3. Verificar constraints actuales en whatsapp_business
    cur.execute("""
        SELECT 
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.table_name = 'whatsapp_business'
        AND tc.table_schema = 'public';
    """)
    
    print("\nConstraints en tabla 'whatsapp_business':")
    constraints = cur.fetchall()
    for const in constraints:
        if const[1] == 'FOREIGN KEY':
            print(f"  - {const[0]}: {const[2]} -> {const[3]}.{const[4]}")
        else:
            print(f"  - {const[0]}: {const[1]} on {const[2]}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
