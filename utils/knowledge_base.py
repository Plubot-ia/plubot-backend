# plubot-backend/utils/knowledge_base.py
from typing import List, Dict
from flask_sqlalchemy import SQLAlchemy
from models import db
import string
import re

class KnowledgeBase:
    def __init__(self):
        self.db = db
    
    def init_db(self):
        pass

    def add_item(self, category: str, question: str, answer: str, keywords: str):
        from models.knowledge_item import KnowledgeItem
        item = KnowledgeItem(
            category=category,
            question=question,
            answer=answer,
            keywords=keywords
        )
        self.db.session.add(item)
        self.db.session.commit()
    
    def search(self, query: str, threshold: float = 0.5) -> List[Dict]:
        from models.knowledge_item import KnowledgeItem
        # Normalizar la consulta: eliminar puntuación, convertir a minúsculas
        translator = str.maketrans('', '', string.punctuation + '¿¡')
        query_clean = query.translate(translator).lower().strip()
        query_words = set(word for word in re.split(r'\s+', query_clean) if word)
        print(f"Palabras de la consulta (depuración): {query_words}")
        
        results = []
        items = KnowledgeItem.query.all()
        for item in items:
            # Dividir palabras clave por comas primero
            keyword_segments = [seg.strip() for seg in item.keywords.split(',') if seg.strip()]
            print(f"Segmentos de palabras clave crudas para '{item.question}' (depuración): {keyword_segments}")
            # Procesar cada segmento: eliminar puntuación y dividir en palabras
            keywords_list = []
            for segment in keyword_segments:
                seg_clean = segment.translate(translator).lower().strip()
                words = re.split(r'\s+', seg_clean)
                keywords_list.extend(word for word in words if word)
            keywords_set = set(keywords_list)
            print(f"Palabras clave procesadas para '{item.question}' (depuración): {keywords_set}")
            
            matches = query_words.intersection(keywords_set)
            relevance = len(matches) / max(len(query_words), 1)
            print(f"Coincidencias para '{item.question}' (depuración): {matches}, Relevancia: {relevance}")
            
            if relevance >= threshold:
                results.append({
                    'id': item.id,
                    'category': item.category,
                    'question': item.question,
                    'answer': item.answer,
                    'relevance': relevance
                })
        
        return sorted(results, key=lambda x: x['relevance'], reverse=True)
    
    def get_by_category(self, category: str) -> List[Dict]:
        from models.knowledge_item import KnowledgeItem
        items = KnowledgeItem.query.filter_by(category=category).all()
        return [{'id': item.id, 'question': item.question, 'answer': item.answer} for item in items]