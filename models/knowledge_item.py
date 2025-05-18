# plubot-backend/models/knowledge_item.py
from models import db

class KnowledgeItem(db.Model):
    __tablename__ = 'knowledge_items'

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    keywords = db.Column(db.Text, nullable=False)