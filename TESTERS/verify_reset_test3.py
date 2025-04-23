from models.user import User
from config.settings import get_session
import bcrypt

with get_session() as session:
    user = session.query(User).filter_by(email='test3@example.com').first()
    if user:
        user.is_verified = True
        user.password = bcrypt.hashpw('NewPass123!!!'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        session.commit()
        print("Usuario verificado y contraseña actualizada para:", user.email)
    else:
        print("Usuario no encontrado")