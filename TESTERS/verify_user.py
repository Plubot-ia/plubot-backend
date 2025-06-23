from models.user import User
from config.settings import get_session

with get_session() as session:
    user = session.query(User).filter_by(email='0-publicar-debuts@icloud.com').first()
    if user:
        print(f"Usuario encontrado: {user.email}, Verificado: {user.is_verified}")
        if not user.is_verified:
            user.is_verified = True
            session.commit()
            print("Usuario verificado manualmente")
    else:
        print("Usuario no encontrado")