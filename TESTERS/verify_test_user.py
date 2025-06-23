from models.user import User
from config.settings import get_session

with get_session() as session:
    user = session.query(User).filter_by(email='test2@example.com').first()
    if user:
        user.is_verified = True
        session.commit()
        print("Usuario verificado:", user.email, user.is_verified)
    else:
        print("Usuario no encontrado")