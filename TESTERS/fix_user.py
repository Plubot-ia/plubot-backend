from models.user import User
from config.settings import get_session
from datetime import datetime, timezone  # Añade timezone

with get_session() as session:
    user = session.query(User).filter_by(email='0-publicar-debuts@icloud.com').first()
    if user:
        user.name = user.name or 'Sebastian'
        user.level = user.level or 1
        user.plucoins = user.plucoins or 0
        user.created_at = user.created_at or datetime.now(timezone.UTC)  # Cambiado
        session.commit()
        print("Usuario actualizado:", user.email, user.name, user.level, user.plucoins, user.created_at)
    else:
        print("Usuario no encontrado")