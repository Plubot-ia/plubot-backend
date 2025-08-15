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

def check_and_verify_user(email: str) -> None:
    """Verifica el estado de un usuario y lo marca como verificado si no lo está."""
    with get_session() as session:
        user = session.query(User).filter_by(email=email).first()
        if user:
            logger.info(
                "Usuario encontrado: email=%s, verificado=%s",
                user.email,
                user.is_verified,
            )
            if not user.is_verified:
                user.is_verified = True
                session.commit()
                logger.info("Usuario verificado manualmente: %s", user.email)
        else:
            logger.warning("Usuario no encontrado: %s", email)


if __name__ == "__main__":
    USER_EMAIL = "0-publicar-debuts@icloud.com"
    logger.info("Verificando al usuario: %s", USER_EMAIL)
    check_and_verify_user(USER_EMAIL)

