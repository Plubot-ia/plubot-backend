import logging
from pathlib import Path
import sys

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

def verify_user(email: str) -> None:
    """Busca un usuario por email y marca su cuenta como verificada."""
    with get_session() as session:
        user = session.query(User).filter_by(email=email).first()
        if user:
            user.is_verified = True
            session.commit()
            logger.info(
                "Usuario verificado: email=%s, is_verified=%s",
                user.email,
                user.is_verified,
            )
        else:
            logger.warning("Usuario no encontrado: %s", email)


if __name__ == "__main__":
    USER_EMAIL = "test2@example.com"
    logger.info("Intentando verificar al usuario: %s", USER_EMAIL)
    verify_user(USER_EMAIL)

