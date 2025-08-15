from datetime import UTC, datetime
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

def fix_all_users() -> None:
    """Itera sobre todos los usuarios y establece valores predeterminados.

    Establece valores para los campos level, plucoins y created_at si están
    vacíos.
    """
    with get_session() as session:
        users = session.query(User).all()
        for user in users:
            user.level = user.level or 1
            user.plucoins = user.plucoins or 0
            user.created_at = user.created_at or datetime.now(UTC)
        session.commit()
        logger.info("Usuarios actualizados: %d", len(users))


if __name__ == "__main__":
    logger.info("Iniciando la corrección de todos los usuarios...")
    fix_all_users()

