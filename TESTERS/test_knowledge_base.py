# plubot-backend/TESTERS/test_knowledge_base.py
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from utils.knowledge_base import KnowledgeBase
from config.settings import load_config
from models.knowledge_item import KnowledgeItem

app = Flask(__name__)
load_config(app)
from models import db
db.init_app(app)

def test_search():
    with app.app_context():
        kb = KnowledgeBase()
        query = "¿Qué es Plubot?"
        query_words = set(query.lower().split())
        print(f"Palabras de la consulta: {query_words}")

        # Mostrar todos los registros para inspeccionar
        print("\nRegistros en knowledge_items:")
        items = KnowledgeItem.query.all()
        for item in items:
            keywords_set = set(item.keywords.lower().split(','))
            print(f"- Pregunta: {item.question}")
            print(f"  Respuesta: {item.answer}")
            print(f"  Palabras clave: {keywords_set}")

        # Probar búsqueda
        results = kb.search(query, threshold=0.5)
        print(f"\nResultados para '{query}' (threshold=0.5):")
        if results:
            for result in results:
                print(f"- {result['question']}: {result['answer']} (relevance: {result['relevance']})")
        else:
            print("No se encontraron resultados.")

if __name__ == "__main__":
    print("Probando búsqueda en la base de conocimiento...")
    test_search()