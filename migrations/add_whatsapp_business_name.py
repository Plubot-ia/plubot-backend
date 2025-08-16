"""Add business_name column to whatsapp_business table

Run this migration with:
python migrations/add_whatsapp_business_name.py
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text

def add_business_name_column():
    """Add business_name column to whatsapp_business table if it doesn't exist"""
    with app.app_context():
        try:
            # Check if column exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='whatsapp_business' 
                AND column_name='business_name'
            """))
            
            if not result.fetchone():
                # Add the column
                db.session.execute(text("""
                    ALTER TABLE whatsapp_business 
                    ADD COLUMN business_name VARCHAR(255)
                """))
                db.session.commit()
                print("✅ Column 'business_name' added successfully to whatsapp_business table")
            else:
                print("ℹ️ Column 'business_name' already exists in whatsapp_business table")
                
        except Exception as e:
            print(f"❌ Error adding column: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    add_business_name_column()
