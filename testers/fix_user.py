from datetime import datetime, timezone
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

def fix_user(email: str) -> None:
    """Busca un usuario por email y actualiza sus campos si están vacíos."""
    with get_session() as session:
        user = session.query(User).filter_by(email=email).first()
        if user:
            user.name = user.name or "Sebastian"
            user.level = user.level or 1
            user.plucoins = user.plucoins or 0
            user.created_at = user.created_at or datetime.now(timezone.UTC)
            session.commit()
            logger.info(
                "Usuario actualizado: email=%s, name=%s, level=%s, plucoins=%s, created_at=%s",
                user.email,
                user.name,
                user.level,
                user.plucoins,
                user.created_at,
            )
        else:
            logger.warning("Usuario no encontrado: %s", email)

if __name__ == "__main__":
    USER_EMAIL = "0-publicar-debuts@icloud.com"
    logger.info("Intentando corregir al usuario: %s", USER_EMAIL)
    fix_user(USER_EMAIL)
