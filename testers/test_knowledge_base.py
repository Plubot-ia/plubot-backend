"""Script de prueba para la funcionalidad de búsqueda en la base de conocimiento.

Este script inicializa una instancia de la aplicación Flask para proporcionar
el contexto necesario para las operaciones de base de datos y prueba la
funcionalidad de búsqueda de la clase KnowledgeBase.
"""
import logging
from pathlib import Path
import sys

from flask import Flask

# Añadir el directorio raíz del proyecto al sys.path para permitir importaciones locales
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from config.settings import load_config  # noqa: E402
from models import db  # noqa: E402
from models.knowledge_item import KnowledgeItem  # noqa: E402
from utils.knowledge_base import KnowledgeBase  # noqa: E402

# --- Configuración del Logger ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Configuración de la App Flask ---
app = Flask(__name__)
load_config(app)
db.init_app(app)


def test_search() -> None:
    """Ejecuta una prueba de búsqueda en la base de conocimiento."""
    with app.app_context():
        kb = KnowledgeBase()
        query = "¿Qué es Plubot?"
        query_words = set(query.lower().split())
        logger.info("Palabras de la consulta: %s", query_words)

        # Mostrar todos los registros para inspeccionar
        logger.info("\nRegistros en knowledge_items:")
        items = KnowledgeItem.query.all()
        for item in items:
            keywords_set = set(item.keywords.lower().split(","))
            logger.info("- Pregunta: %s", item.question)
            logger.info("  Respuesta: %s", item.answer)
            logger.info("  Palabras clave: %s", keywords_set)

        # Probar búsqueda
        results = kb.search(query, threshold=0.5)
        logger.info("\nResultados para '%s' (threshold=0.5):", query)
        if results:
            for result in results:
                log_message = (
                    f"- {result['question']}: {result['answer']} "
                    f"(relevance: {result['relevance']})"
                )
                logger.info(log_message)
        else:
            logger.info("No se encontraron resultados.")


if __name__ == "__main__":
    logger.info("Probando búsqueda en la base de conocimiento...")
    test_search()
