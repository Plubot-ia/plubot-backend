"""Módulo con funciones de utilidad para diversas tareas en la aplicación."""

import json
import logging
import time
from typing import Any, Final

from pydantic import ValidationError
from sqlalchemy.orm import Session

from models.message_quota import MessageQuota

from .validators import MenuModel

logger: Final = logging.getLogger(__name__)


def summarize_history(history: list[Any]) -> str:
    """Genera un resumen conciso del historial de conversación.

    Args:
        history: Una lista de objetos de conversación con un atributo `message`.

    Returns:
        Un string con el resumen del historial.
    """
    if len(history) > 5:
        summary_messages = [str(conv.message)[:50] for conv in history[-5:]]
        return f"Resumen: {' '.join(summary_messages)}"
    return " ".join([str(conv.message) for conv in history])


def parse_menu_to_flows(menu_json: str | dict[str, Any]) -> list[dict[str, str]]:
    """Convierte un menú en formato JSON a una lista de flujos de chatbot.

    Args:
        menu_json: El menú en formato JSON (string) o como un diccionario.

    Returns:
        Una lista de diccionarios que representan los flujos del chatbot,
        o una lista vacía si ocurre un error de parseo.
    """
    try:
        menu_data = (
            json.loads(menu_json) if isinstance(menu_json, str) else menu_json
        )
        validated_menu = MenuModel(root=menu_data).root
    except (json.JSONDecodeError, ValidationError):
        logger.exception("Error al procesar el menú. Se retorna una lista vacía.")
        return []

    flows: list[dict[str, str]] = []
    all_categories: list[str] = []
    for category, items in validated_menu.items():
        all_categories.append(category.capitalize())
        details_list = [
            f"- {name}: {details['descripcion']} (${details['precio']})"
            for name, details in items.items()
        ]
        category_response = f"📋 {category.capitalize()} disponibles:\n" + "\n".join(
            details_list
        )

        for item_name, details in items.items():
            bot_response = (
                f"¡Buena elección! {item_name}: {details['descripcion']} "
                f"por ${details['precio']}. ¿Confirmas el pedido?"
            )
            flows.append({
                "user_message": f"quiero {item_name.lower()}",
                "bot_response": bot_response,
            })
        flows.append({
            "user_message": f"ver {category.lower()}",
            "bot_response": category_response,
        })

    menu_summary_items = [
        f"📋 {cat}: {', '.join(validated_menu[cat.lower()].keys())}"
        for cat in all_categories
    ]
    flows.append({
        "user_message": "ver menú",
        "bot_response": (
            "¡Claro! Aquí tienes nuestro menú completo:\n" + "\n".join(menu_summary_items)
        ),
    })
    return flows


def check_quota(user_id: str, session: Session) -> bool:
    """Verifica si el usuario ha excedido su cuota de mensajes gratuitos.

    Args:
        user_id: El ID del usuario.
        session: La sesión de base de datos.

    Returns:
        True si el usuario tiene cuota disponible, False en caso contrario.
    """
    current_month = time.strftime("%Y-%m")
    quota = (
        session.query(MessageQuota)
        .filter_by(user_id=user_id, month=current_month)
        .first()
    )
    if not quota:
        quota = MessageQuota(user_id=user_id, month=current_month)
        session.add(quota)
        session.commit()

    if quota.plan == "free":
        return quota.message_count < 100
    return True


def increment_quota(user_id: str, session: Session) -> None:
    """Incrementa el contador de mensajes para la cuota del usuario.

    Si no existe una cuota para el mes actual, se crea una nueva.

    Args:
        user_id: El ID del usuario.
        session: La sesión de base de datos.
    """
    current_month = time.strftime("%Y-%m")
    quota = (
        session.query(MessageQuota)
        .filter_by(user_id=user_id, month=current_month)
        .first()
    )
    if not quota:
        quota = MessageQuota(user_id=user_id, month=current_month)
        session.add(quota)

    quota.message_count += 1
    session.commit()

    quota.message_count += 1
    session.commit()
    return quota
