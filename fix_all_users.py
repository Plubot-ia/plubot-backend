from models.user import User
from config.settings import get_session
from datetime import datetime, timezone

with get_session() as session:
    users = session.query(User).all()
    for user in users:
        user.level = user.level or 1
        user.plucoins = user.plucoins or 0
        user.created_at = user.created_at or datetime.now(timezone.utc)
    session.commit()
    print("Usuarios actualizados:", len(users))