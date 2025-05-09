from sqlalchemy import Column, Integer, Text, ForeignKey
from models import Base

class FlowEdge(Base):
    __tablename__ = 'flow_edges'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chatbot_id = Column(Integer, ForeignKey('plubots.id'), nullable=False)  # Actualizado: referenciar plubots.id
    source_flow_id = Column(Integer, ForeignKey('flows.id', ondelete='CASCADE'), nullable=False)
    target_flow_id = Column(Integer, ForeignKey('flows.id', ondelete='CASCADE'), nullable=False)
    condition = Column(Text, default="")