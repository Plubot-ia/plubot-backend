from sqlalchemy import Column, Integer, Text, ForeignKey
from models import Base

class FlowEdge(Base):
    __tablename__ = 'flow_edges'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chatbot_id = Column(Integer, ForeignKey('chatbots.id'), nullable=False)
    source_flow_id = Column(Integer, ForeignKey('flows.id'), nullable=False)
    target_flow_id = Column(Integer, ForeignKey('flows.id'), nullable=False)
    condition = Column(Text, default="")