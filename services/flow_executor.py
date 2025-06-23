import logging
from sqlalchemy import and_
from models import db, Plubot, Flow, FlowEdge, WhatsappConnection, ConversationState
from services import whatsapp_service

logger = logging.getLogger(__name__)

def trigger_flow(plubot_id, sender_contact, message_text):
    """
    Manages the conversation flow based on the user's state.
    """
    logger.info(f"Executing flow for plubot {plubot_id}, contact {sender_contact}, message '{message_text}'")

    # 1. Find the current state of the conversation
    conversation_state = ConversationState.query.filter_by(
        plubot_id=plubot_id,
        contact_identifier=sender_contact
    ).first()

    next_node = None

    if conversation_state:
        # 2. If a conversation exists, find the next node based on the current node and message
        current_node = conversation_state.current_node
        logger.info(f"Existing conversation. Current node is {current_node.id} ('{current_node.user_message}')")
        
        # Find an edge from the current node whose label matches the user's message
        # Note: This is a simple implementation. Real-world scenarios might use intents or NLP.
        matching_edge = FlowEdge.query.filter(
            and_(
                FlowEdge.source_flow_id == current_node.id,
                FlowEdge.label.ilike(f'%{message_text}%') # Case-insensitive partial match
            )
        ).first()

        if matching_edge:
            next_node = matching_edge.target_node
            logger.info(f"Found matching edge {matching_edge.id}. Next node is {next_node.id}")
        else:
            logger.warning(f"No matching edge found from node {current_node.id} for message '{message_text}'")
            # Fallback logic could be implemented here

    else:
        # 3. If no conversation exists, find the start node
        logger.info("New conversation. Looking for a start node.")
        # A start node is one with no incoming edges
        start_node = Flow.query.filter(
            and_(
                Flow.chatbot_id == plubot_id,
                ~Flow.incoming_edges.any()
            )
        ).first()
        
        if start_node:
            next_node = start_node
            logger.info(f"Found start node: {start_node.id}")
        else:
            logger.error(f"Could not find a start node for plubot {plubot_id}. Flow cannot begin.")

    # 4. If we have a node to proceed to, send the message and update the state
    if next_node:
        # Send the bot's response from the target node
        whatsapp_service.send_whatsapp_message(sender_contact, next_node.bot_response, plubot_id)
        
        # Update or create the conversation state
        if conversation_state:
            conversation_state.current_node_id = next_node.id
        else:
            new_state = ConversationState(
                plubot_id=plubot_id,
                contact_identifier=sender_contact,
                current_node_id=next_node.id
            )
            db.session.add(new_state)
        
        db.session.commit()
        logger.info(f"Conversation state for {sender_contact} updated to node {next_node.id}")
    else:
        # Fallback for when no next node is determined
        logger.warning(f"Could not determine next step for plubot {plubot_id} and contact {sender_contact}. No message sent.")
        # Send a generic fallback message
        fallback_message = "Lo siento, no he entendido esa respuesta. Por favor, intenta de nuevo con una de las opciones disponibles."
        whatsapp_service.send_whatsapp_message(sender_contact, fallback_message, plubot_id)

