from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Float
from models import Base

class Flow(Base):
    __tablename__ = 'flows'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chatbot_id = Column(Integer, ForeignKey('plubots.id'), nullable=False)
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    position = Column(Integer, nullable=False)
    intent = Column(String)
    condition = Column(Text, default="")
    actions = Column(JSON, nullable=True)
    position_x = Column(Float, nullable=True)  # Nuevo campo para la coordenada X
    position_y = Column(Float, nullable=True)  # Nuevo campo para la coordenada Y