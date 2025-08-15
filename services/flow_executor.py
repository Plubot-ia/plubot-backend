"""Motor de ejecución de flujos de chatbot."""

import logging
from typing import Final

from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError

from models import ConversationState, Flow, FlowEdge, db
from services import whatsapp_service

logger: Final = logging.getLogger(__name__)

_FALLBACK_MESSAGE: Final = (
    "Lo siento, no he entendido esa respuesta. "
    "Por favor, intenta de nuevo con una de las opciones disponibles."
)


def _get_conversation_state(plubot_id: str, contact: str) -> ConversationState | None:
    """Recupera el estado de la conversación actual para un contacto."""
    return ConversationState.query.filter_by(
        plubot_id=plubot_id, contact_identifier=contact
    ).first()


def _find_start_node(plubot_id: str) -> Flow | None:
    """Encuentra el nodo de inicio para un Plubot (un nodo sin aristas entrantes)."""
    return Flow.query.filter(
        and_(Flow.chatbot_id == plubot_id, ~Flow.incoming_edges.any())
    ).first()


def _find_next_node_from_message(
    current_node: Flow,
    message_text: str,
) -> Flow | None:
    """Encuentra el siguiente nodo basado en el mensaje del usuario.

    Nota: Esta implementación utiliza una coincidencia parcial insensible a mayúsculas.
    Para un sistema en producción, se recomienda usar NLP o machine learning.
    """
    matching_edge = FlowEdge.query.filter(
        and_(
            FlowEdge.source_flow_id == current_node.id,
            FlowEdge.label.ilike(f"%{message_text}%"),
        )
    ).first()

    if matching_edge:
        return matching_edge.target_node
    return None


def _update_conversation_state(
    state: ConversationState | None,
    plubot_id: str,
    contact: str,
    next_node_id: str,
) -> None:
    """Crea o actualiza el estado de la conversación con el nuevo nodo."""
    if state:
        state.current_node_id = next_node_id
    else:
        new_state = ConversationState(
            plubot_id=plubot_id,
            contact_identifier=contact,
            current_node_id=next_node_id,
        )
        db.session.add(new_state)


def _send_fallback_message(contact: str, plubot_id: str) -> None:
    """Envía un mensaje de fallback cuando no se puede determinar el siguiente paso."""
    logger.warning(
        "No se pudo determinar el siguiente paso para plubot %s y contacto %s.",
        plubot_id,
        contact,
    )
    whatsapp_service.send_whatsapp_message(contact, _FALLBACK_MESSAGE, plubot_id)


def trigger_flow(plubot_id: str, sender_contact: str, message_text: str) -> None:
    """Gestiona el flujo de la conversación basado en el estado del usuario.

    Args:
        plubot_id: El ID del Plubot que gestiona la conversación.
        sender_contact: El identificador del contacto (ej. número de WhatsApp).
        message_text: El texto del mensaje recibido del usuario.
    """
    logger.info(
        "Ejecutando flujo para plubot %s, contacto %s, mensaje '%s'",
        plubot_id,
        sender_contact,
        message_text,
    )

    try:
        state = _get_conversation_state(plubot_id, sender_contact)
        next_node: Flow | None = None

        if state and state.current_node:
            logger.info(
                "Conversación existente. Nodo actual: %s ('%s')",
                state.current_node.id,
                state.current_node.user_message,
            )
            next_node = _find_next_node_from_message(
                state.current_node, message_text
            )
        else:
            logger.info("Nueva conversación. Buscando un nodo de inicio.")
            next_node = _find_start_node(plubot_id)

        if not next_node:
            _send_fallback_message(sender_contact, plubot_id)
            return

        logger.info("Siguiente nodo determinado: %s", next_node.id)
        whatsapp_service.send_whatsapp_message(
            sender_contact, next_node.bot_response, plubot_id
        )

        _update_conversation_state(state, plubot_id, sender_contact, next_node.id)

        db.session.commit()
        logger.info(
            "Estado de la conversación para %s actualizado al nodo %s",
            sender_contact,
            next_node.id,
        )

    except SQLAlchemyError:
        logger.exception(
            "Error de base de datos ejecutando el flujo para plubot %s.", plubot_id
        )
        db.session.rollback()
    except Exception:
        logger.exception(
            "Error inesperado ejecutando el flujo para plubot %s.", plubot_id
        )
        db.session.rollback()


