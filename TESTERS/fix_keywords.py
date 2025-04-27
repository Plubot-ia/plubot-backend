# plubot-backend/TESTERS/fix_keywords.py
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from config.settings import load_config
from models import db
from models.knowledge_item import KnowledgeItem

app = Flask(__name__)
load_config(app)
db.init_app(app)

def fix_keywords():
    with app.app_context():
        items = KnowledgeItem.query.all()
        for item in items:
            # Limpiar espacios adicionales en las palabras clave
            cleaned_keywords = ','.join(kw.strip() for kw in item.keywords.split(','))
            item.keywords = cleaned_keywords
        db.session.commit()
        print("Palabras clave corregidas en la base de datos.")

if __name__ == "__main__":
    print("Corrigiendo palabras clave en knowledge_items...")
    fix_keywords()