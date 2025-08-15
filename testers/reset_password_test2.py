import logging
from pathlib import Path
import sys

import bcrypt

# Añadir el directorio raíz del proyecto al sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from config.settings import get_session  # noqa: E402
from models.user import User  # noqa: E402

# Configuración del logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def reset_password(email: str, new_pass: str) -> None:
    """Busca un usuario por email y resetea su contraseña."""
    with get_session() as session:
        user = session.query(User).filter_by(email=email).first()
        if user:
            hashed_pw = bcrypt.hashpw(new_pass.encode("utf-8"), bcrypt.gensalt())
            user.password = hashed_pw.decode("utf-8")
            session.commit()
            logger.info("Contraseña actualizada para: %s", user.email)
        else:
            logger.warning("Usuario no encontrado: %s", email)


if __name__ == "__main__":
    USER_EMAIL = "test2@example.com"
    NEW_PASSWORD = "NewPass123!!!"  # noqa: S105
    logger.info("Intentando resetear la contraseña para: %s", USER_EMAIL)
    reset_password(USER_EMAIL, NEW_PASSWORD)

