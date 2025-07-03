"""Utilidades para la gestión de la base de conocimiento."""

import logging
import re
import string
from typing import TYPE_CHECKING

from models.knowledge_item import KnowledgeItem

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def add_knowledge_item(
    session: "Session", category: str, question: str, answer: str, keywords: str
) -> None:
    """Añade un nuevo ítem a la base de conocimiento.

    Args:
        session: La sesión de SQLAlchemy.
        category: La categoría del ítem.
        question: La pregunta o título del ítem.
        answer: La respuesta o contenido.
        keywords: Palabras clave asociadas, separadas por comas.
    """
    item = KnowledgeItem(
        category=category, question=question, answer=answer, keywords=keywords
    )
    session.add(item)


def search_knowledge_base(
    session: "Session", query: str, threshold: float = 0.5
) -> list[dict]:
    """Busca en la base de conocimiento basándose en una consulta.

    Args:
        session: La sesión de SQLAlchemy.
        query: La consulta de búsqueda del usuario.
        threshold: El umbral de relevancia para incluir un resultado.

    Returns:
        Una lista de ítems que coinciden con la consulta, ordenados por relevancia.
    """
    translator = str.maketrans("", "", string.punctuation + "¿¡")
    query_clean = query.translate(translator).lower().strip()
    query_words = {word for word in re.split(r"\s+", query_clean) if word}
    logger.debug("Palabras de la consulta (depuración): %s", query_words)

    results = []
    items = session.query(KnowledgeItem).all()

    for item in items:
        keyword_segments = [seg.strip() for seg in item.keywords.split(",") if seg.strip()]
        logger.debug(
            "Segmentos de palabras clave crudas para '%s': %s",
            item.question,
            keyword_segments,
        )

        keywords_list = []
        for segment in keyword_segments:
            seg_clean = segment.translate(translator).lower().strip()
            words = re.split(r"\s+", seg_clean)
            keywords_list.extend(word for word in words if word)
        keywords_set = set(keywords_list)
        logger.debug("Palabras clave procesadas para '%s': %s", item.question, keywords_set)

        matches = query_words.intersection(keywords_set)
        relevance = len(matches) / max(len(query_words), 1)
        logger.debug(
            "Coincidencias para '%s': %s, Relevancia: %s",
            item.question,
            matches,
            relevance,
        )

        if relevance >= threshold:
            results.append(
                {
                    "id": item.id,
                    "category": item.category,
                    "question": item.question,
                    "answer": item.answer,
                    "relevance": relevance,
                }
            )

    return sorted(results, key=lambda x: x["relevance"], reverse=True)


def get_knowledge_by_category(session: "Session", category: str) -> list[dict]:
    """Obtiene todos los ítems de una categoría específica.

    Args:
        session: La sesión de SQLAlchemy.
        category: La categoría a buscar.

    Returns:
        Una lista de ítems pertenecientes a la categoría.
    """
    items = session.query(KnowledgeItem).filter_by(category=category).all()
    return [
        {"id": item.id, "question": item.question, "answer": item.answer}
        for item in items
    ]
