# plubot-backend/testers/fix_keywords.py
import logging
from pathlib import Path
import sys

from flask import Flask

# Añadir el directorio raíz del proyecto al sys.path para poder importar los módulos
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Imports de la aplicación (después de modificar el path)
from config.settings import load_config  # noqa: E402
from models import db  # noqa: E402
from models.knowledge_item import KnowledgeItem  # noqa: E402

# Configuración del logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
load_config(app)
db.init_app(app)

def fix_keywords() -> None:
    """Limpia y normaliza las palabras clave en todos los KnowledgeItem."""
    with app.app_context():
        items = KnowledgeItem.query.all()
        for item in items:
            # Limpiar y normalizar las palabras clave
            cleaned_keywords = [
                kw.strip().lower() for kw in item.keywords.split(",") if kw.strip()
            ]
            item.keywords = ",".join(cleaned_keywords)
        db.session.commit()
        logger.info("Palabras clave corregidas en la base de datos.")

if __name__ == "__main__":
    logger.info("Corrigiendo palabras clave en knowledge_items...")
    fix_keywords()

