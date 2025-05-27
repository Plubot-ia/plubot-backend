from sqlalchemy import Column, Integer, String, Text
from models import Base

class Template(Base):
    __tablename__ = 'templates'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    tone = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    flows = Column(Text, nullable=False)
    description = Column(Text, nullable=False)