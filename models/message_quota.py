from sqlalchemy import Column, Integer, String, ForeignKey
from models import Base

class MessageQuota(Base):
    __tablename__ = 'message_quotas'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    month = Column(String, nullable=False)
    message_count = Column(Integer, default=0)
    plan = Column(String, default='free')