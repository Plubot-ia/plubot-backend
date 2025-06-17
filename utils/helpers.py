import json
import time
import logging
from models.conversation import Conversation
from models.message_quota import MessageQuota
from .validators import MenuModel

def summarize_history(history):
    if len(history) > 5:
        return "Resumen: " + " ".join([conv.message[:50] for conv in history[-5:]])
    return " ".join([conv.message for conv in history])

def parse_menu_to_flows(menu_json):
    try:
        if isinstance(menu_json, str):
            menu_data = json.loads(menu_json)
        else:
            menu_data = menu_json
        validated_menu = MenuModel(root=menu_data).root
        flows = []
        for category, items in validated_menu.items():
            category_response = f"📋 {category.capitalize()} disponibles:\n"
            for item_name, details in items.items():
                category_response += f"- {item_name}: {details['descripcion']} (${details['precio']})\n"
                flows.append({
                    "user_message": f"quiero {item_name.lower()}",
                    "bot_response": f"¡Buena elección! {item_name}: {details['descripcion']} por ${details['precio']}. ¿Confirmas el pedido?"
                })
            flows.append({
                "user_message": f"ver {category.lower()}",
                "bot_response": category_response
            })
        flows.append({
            "user_message": "ver menú",
            "bot_response": "¡Claro! Aquí tienes nuestro menú completo:\n" + "\n".join(
                f"📋 {category.capitalize()}: {', '.join(items.keys())}" for category, items in validated_menu.items()
            )
        })
        return flows
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error al procesar menú: {str(e)}")
        return []

def check_quota(user_id, session):
    current_month = time.strftime("%Y-%m")
    quota = session.query(MessageQuota).filter_by(user_id=user_id, month=current_month).first()
    if not quota:
        quota = MessageQuota(user_id=user_id, month=current_month)
        session.add(quota)
        session.commit()
    if quota.plan == 'free':
        return quota.message_count < 100
    return True

def increment_quota(user_id, session):
    current_month = time.strftime("%Y-%m")
    quota = session.query(MessageQuota).filter_by(user_id=user_id, month=current_month).first()
    if not quota:
        quota = MessageQuota(user_id=user_id, month=current_month)
        session.add(quota)
    quota.message_count += 1
    session.commit()
    return quota