from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from config.settings import get_session
from models.plubot import Plubot
from models.flow import Flow
from models.flow_edge import FlowEdge
from models.template import Template
from models.user import User
from utils.validators import FlowModel
from utils.helpers import parse_menu_to_flows
from services.grok_service import call_grok
from celery_tasks import process_pdf_async
import logging
import json

plubots_bp = Blueprint('plubots', __name__)
logger = logging.getLogger(__name__)

# Definición de personalidades y mensajes contextuales
PERSONALITIES = {
    "audaz": {
        "welcome": "¡Hey crack! ¿Listo para la acción?",
        "bye": "¡Nos vemos, leyenda! No tardes en volver.",
        "error": "Oops… algo explotó, pero tranquilo, ya lo arreglo.",
        "confirmation": "¡Hecho! Rapidísimo como siempre.",
        "farewell": "¡Chau chau, campeón!",
        "color": "#FF6B00"
    },
    "sabio": {
        "welcome": "Saludos. Es un honor atenderte.",
        "bye": "Gracias por tu tiempo. Hasta pronto.",
        "error": "Lamento el inconveniente. Procedo a corregirlo.",
        "confirmation": "Confirmado. Todo está en orden.",
        "farewell": "Que tengas un excelente día.",
        "color": "#1E3A8A"
    },
    "servicial": {
        "welcome": "¡Hola! ¿En qué puedo ayudarte hoy?",
        "bye": "Me despido, pero recuerda que siempre estoy cerca.",
        "error": "¡Oh no! Déjame arreglar eso para ti.",
        "confirmation": "Perfecto, ya está todo listo.",
        "farewell": "¡Un gusto haberte asistido!",
        "color": "#22C55E"
    },
    "creativo": {
        "welcome": "¡Wiii! Llegaste. Vamos a crear magia.",
        "bye": "¡Chau chau, nos vemos en la próxima locura!",
        "error": "Uy… algo salió raro. ¡Pero lo convertimos en arte!",
        "confirmation": "¡Listo! Esto va a quedar épico.",
        "farewell": "¡Nos vemos! Que las ideas no te falten.",
        "color": "#A855F7"
    },
    "neutral": {
        "welcome": "Hola, ¿cómo puedo asistirte?",
        "bye": "Sesión finalizada. Hasta luego.",
        "error": "Hubo un error. Procedo a solucionarlo.",
        "confirmation": "Acción completada correctamente.",
        "farewell": "Gracias por usar Plubot.",
        "color": "#D1D5DB"
    },
    "misterioso": {
        "welcome": "Te esperaba… dime, ¿qué buscas?",
        "bye": "Nos volveremos a cruzar. Lo sé.",
        "error": "Un contratiempo… déjame encargarme.",
        "confirmation": "Todo está en marcha. Como debía ser.",
        "farewell": "Desaparezco… por ahora.",
        "color": "#1F2937"
    }
}

VALID_CONTEXTS = ["welcome", "bye", "error", "confirmation", "farewell"]

@plubots_bp.route('/create', methods=['POST'])
@jwt_required()
def create_bot():
    user_id = get_jwt_identity()
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No se proporcionaron datos'}), 400

    name = data.get('name')
    tone = data.get('tone', 'amigable')
    purpose = data.get('purpose', 'ayudar a los clientes')
    color = data.get('color')
    powers = data.get('powers', [])
    whatsapp_number = data.get('whatsapp_number')
    business_info = data.get('business_info')
    pdf_url = data.get('pdf_url')
    image_url = data.get('image_url')
    flows_raw = data.get('flows', [])
    edges_raw = data.get('edges', [])
    template_id = data.get('template_id')
    menu_json = data.get('menu_json')
    power_config = data.get('powerConfig', {})
    plan_type = data.get('plan_type', 'free')
    avatar = data.get('avatar')
    menu_options = data.get('menu_options', [])
    response_limit = data.get('response_limit', 100)
    conversation_count = data.get('conversation_count', 0)
    message_count = data.get('message_count', 0)
    is_webchat_enabled = data.get('is_webchat_enabled', True)

    if not name:
        return jsonify({'status': 'error', 'message': 'El nombre del plubot es obligatorio'}), 400

    if not isinstance(powers, list):
        return jsonify({'status': 'error', 'message': 'Los poderes deben ser una lista'}), 400

    flows = []
    user_messages = set()
    for index, flow in enumerate(flows_raw):
        try:
            validated_flow = FlowModel(**flow)
            user_msg = validated_flow.user_message.strip().lower()
            bot_resp = validated_flow.bot_response.strip()
            if not user_msg or not bot_resp:
                return jsonify({
                    'status': 'error',
                    'message': f'El flujo en la posición {index} tiene mensajes vacíos.'
                }), 400
            if user_msg in user_messages:
                return jsonify({
                    'status': 'error',
                    'message': f'El mensaje de usuario "{user_msg}" en la posición {index} está duplicado.'
                }), 400
            user_messages.add(user_msg)
            flows.append(validated_flow.dict())
        except Exception as e:
            logger.error(f"Flujo inválido en posición {index}: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Flujo inválido en posición {index}: {str(e)}'}), 400

    with get_session() as session:
        try:
            flows_to_save = flows
            if template_id:
                template = session.query(Template).filter_by(id=template_id).first()
                if template:
                    tone = template.tone
                    purpose = template.purpose
                    template_flows = json.loads(template.flows)
                    flows_to_save = template_flows + flows if flows else template_flows

            if menu_json:
                menu_flows = parse_menu_to_flows(menu_json)
                flows_to_save = flows_to_save + menu_flows if flows_to_save else menu_flows

            system_message = f"Eres un plubot {tone} llamado '{name}'. Tu propósito es {purpose}."
            if business_info:
                system_message += f"\nNegocio: {business_info}"
            if pdf_url:
                system_message += "\nContenido del PDF será añadido tras procesar."
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": "Dame un mensaje de bienvenida."}
            ]
            initial_message = call_grok(messages, max_tokens=100)

            plubot = Plubot(
                name=name,
                tone=tone,
                purpose=purpose,
                initial_message=initial_message,
                whatsapp_number=whatsapp_number,
                business_info=business_info,
                pdf_url=pdf_url,
                image_url=image_url,
                user_id=user_id,
                color=color,
                powers=powers,
                plan_type=plan_type,
                avatar=avatar,
                menu_options=menu_options,
                response_limit=response_limit,
                conversation_count=conversation_count,
                message_count=message_count,
                is_webchat_enabled=is_webchat_enabled,
                power_config=power_config
            )
            session.add(plubot)
            session.flush()

            if power_config.get('google-sheets', {}).get('credentials'):
                user = session.query(User).filter_by(id=user_id).first()
                if user:
                    user.google_sheets_credentials = power_config['google-sheets']['credentials']
                else:
                    logger.error(f"Usuario con ID {user_id} no encontrado")
                    return jsonify({'status': 'error', 'message': 'Usuario no encontrado'}), 404

            session.commit()
            plubot_id = plubot.id

            if pdf_url:
                process_pdf_async.delay(plubot_id, pdf_url)

            flow_id_map = {}
            for index, flow in enumerate(flows_to_save):
                if flow.get('user_message') and flow.get('bot_response'):
                    intent = flow.get('intent', 'general')
                    condition = flow.get('condition', '')
                    position_x = flow.get('position_x')  # Nuevo: obtener position_x
                    position_y = flow.get('position_y')  # Nuevo: obtener position_y
                    flow_entry = Flow(
                        chatbot_id=plubot_id,
                        user_message=flow['user_message'],
                        bot_response=flow['bot_response'],
                        position=index,
                        intent=intent,
                        condition=condition,
                        position_x=position_x,  # Nuevo: asignar position_x
                        position_y=position_y   # Nuevo: asignar position_y
                    )
                    session.add(flow_entry)
                    session.flush()
                    flow_id_map[str(index)] = flow_entry.id

            for edge in edges_raw:
                source_id = flow_id_map.get(edge.get('source'))
                target_id = flow_id_map.get(edge.get('target'))
                if source_id and target_id:
                    edge_entry = FlowEdge(
                        chatbot_id=plubot_id,
                        source_flow_id=source_id,
                        target_flow_id=target_id,
                        condition=""
                    )
                    session.add(edge_entry)

            session.commit()
            return jsonify({
                'status': 'success',
                'message': f"Plubot '{name}' creado con éxito. ID: {plubot_id}.",
                'plubot': {
                    'id': plubot.id,
                    'name': plubot.name,
                    'tone': plubot.tone,
                    'purpose': plubot.purpose,
                    'color': plubot.color,
                    'powers': plubot.powers,
                    'whatsapp_number': plubot.whatsapp_number,
                    'initial_message': plubot.initial_message,
                    'business_info': plubot.business_info,
                    'pdf_url': plubot.pdf_url,
                    'image_url': plubot.image_url,
                    'created_at': plubot.created_at.isoformat() if plubot.created_at else None,
                    'updated_at': plubot.updated_at.isoformat() if plubot.updated_at else None,
                    'plan_type': plubot.plan_type,
                    'avatar': plubot.avatar,
                    'menu_options': plubot.menu_options,
                    'response_limit': plubot.response_limit,
                    'conversation_count': plubot.conversation_count,
                    'message_count': plubot.message_count,
                    'is_webchat_enabled': plubot.is_webchat_enabled,
                    'power_config': plubot.power_config
                }
            }), 200
        except Exception as e:
            logger.exception(f"Error al crear plubot: {str(e)}")
            session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

@plubots_bp.route('/create_despierto', methods=['POST'])
@jwt_required()
def create_despierto_bot():
    user_id = get_jwt_identity()
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No se proporcionaron datos'}), 400

    name = data.get('name')
    tone = data.get('tone', 'neutral').lower()
    purpose = data.get('purpose', 'ayudar a los clientes')
    avatar = data.get('avatar', 'default_avatar.png')
    menu_options = data.get('menu_options', [])
    color = data.get('color', PERSONALITIES.get(tone, {}).get('color', '#D1D5DB'))

    if tone not in PERSONALITIES:
        return jsonify({
            'status': 'error',
            'message': f"Tono inválido. Opciones válidas: {', '.join(PERSONALITIES.keys())}"
        }), 400

    if not name:
        return jsonify({'status': 'error', 'message': 'El nombre del plubot es obligatorio'}), 400

    if len(menu_options) > 3:
        return jsonify({'status': 'error', 'message': 'Máximo 3 opciones de menú permitidas'}), 400

    for option in menu_options:
        if not option.get('label') or not option.get('action'):
            return jsonify({
                'status': 'error',
                'message': 'Cada opción de menú debe tener un label y una acción'
            }), 400

    with get_session() as session:
        try:
            initial_message = PERSONALITIES[tone]['welcome']
            plubot = Plubot(
                name=name,
                tone=tone,
                purpose=purpose,
                initial_message=initial_message,
                user_id=user_id,
                plan_type='free',
                avatar=avatar,
                menu_options=menu_options,
                response_limit=100,
                conversation_count=0,
                message_count=0,
                is_webchat_enabled=True,
                power_config={},
                color=color
            )
            session.add(plubot)
            session.commit()
            plubot_id = plubot.id

            flows = []
            for index, option in enumerate(menu_options):
                flows.append({
                    'user_message': option['label'].lower(),
                    'bot_response': f"Has seleccionado {option['label']}. ¿Cómo puedo ayudarte con esto?",
                    'position': index,
                    'intent': 'menu_option',
                    'condition': '',
                    'position_x': 100.0 * index,  # Nuevo: posición predeterminada
                    'position_y': 100.0           # Nuevo: posición predeterminada
                })

            flow_id_map = {}
            for index, flow in enumerate(flows):
                flow_entry = Flow(
                    chatbot_id=plubot_id,
                    user_message=flow['user_message'],
                    bot_response=flow['bot_response'],
                    position=flow['position'],
                    intent=flow['intent'],
                    condition=flow['condition'],
                    position_x=flow['position_x'],  # Nuevo: asignar position_x
                    position_y=flow['position_y']   # Nuevo: asignar position_y
                )
                session.add(flow_entry)
                session.flush()
                flow_id_map[str(index)] = flow_entry.id

            session.commit()
            return jsonify({
                'status': 'success',
                'message': f"Plubot Despierto '{name}' creado con éxito. ID: {plubot_id}.",
                'plubot': {
                    'id': plubot.id,
                    'name': plubot.name,
                    'tone': plubot.tone,
                    'purpose': plubot.purpose,
                    'initial_message': plubot.initial_message,
                    'plan_type': plubot.plan_type,
                    'avatar': plubot.avatar,
                    'menu_options': plubot.menu_options,
                    'response_limit': plubot.response_limit,
                    'conversation_count': plubot.conversation_count,
                    'message_count': plubot.message_count,
                    'is_webchat_enabled': plubot.is_webchat_enabled,
                    'power_config': plubot.power_config,
                    'color': plubot.color
                }
            }), 200
        except Exception as e:
            logger.exception(f"Error al crear Plubot Despierto: {str(e)}")
            session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

@plubots_bp.route('/list', methods=['GET', 'OPTIONS'])
@jwt_required()
def list_bots():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    user_id = get_jwt_identity()
    with get_session() as session:
        plubots = session.query(Plubot).filter_by(user_id=user_id).all()
        plubots_data = [
            {
                'id': bot.id,
                'name': bot.name,
                'tone': bot.tone,
                'purpose': bot.purpose,
                'color': bot.color,
                'powers': bot.powers,
                'whatsapp_number': bot.whatsapp_number,
                'initial_message': bot.initial_message,
                'business_info': bot.business_info,
                'pdf_url': bot.pdf_url,
                'image_url': bot.image_url,
                'created_at': bot.created_at.isoformat() if bot.created_at else None,
                'updated_at': bot.updated_at.isoformat() if bot.updated_at else None,
                'plan_type': bot.plan_type,
                'avatar': bot.avatar,
                'menu_options': bot.menu_options,
                'response_limit': bot.response_limit,
                'conversation_count': bot.conversation_count,
                'message_count': bot.message_count,
                'is_webchat_enabled': bot.is_webchat_enabled,
                'power_config': bot.power_config
            } for bot in plubots
        ]
        return jsonify({'plubots': plubots_data}), 200

@plubots_bp.route('/messages/<int:plubot_id>/<string:context>', methods=['GET'])
@jwt_required()
def get_contextual_message(plubot_id, context):
    user_id = get_jwt_identity()
    if context not in VALID_CONTEXTS:
        return jsonify({
            'status': 'error',
            'message': f"Contexto inválido. Opciones válidas: {', '.join(VALID_CONTEXTS)}"
        }), 400

    with get_session() as session:
        plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
        if not plubot:
            return jsonify({
                'status': 'error',
                'message': 'Plubot no encontrado o no tienes permisos'
            }), 404

        tone = plubot.tone.lower()
        if tone not in PERSONALITIES:
            logger.warning(f"Plubot {plubot_id} tiene tono inválido: {tone}")
            tone = 'neutral'
        message = PERSONALITIES[tone].get(context)
        return jsonify({
            'status': 'success',
            'message': message,
            'tone': tone,
            'context': context
        }), 200

@plubots_bp.route('/update/<int:plubot_id>', methods=['PUT', 'OPTIONS'])
@jwt_required()
def update_bot(plubot_id):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    logger.info(f"Received PUT request to update plubot_id={plubot_id}, data={request.get_json()}")
    user_id = get_jwt_identity()
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No se proporcionaron datos'}), 400

    name = data.get('name')
    tone = data.get('tone')
    purpose = data.get('purpose')
    color = data.get('color')
    powers = data.get('powers', [])
    whatsapp_number = data.get('whatsapp_number')
    business_info = data.get('business_info')
    pdf_url = data.get('pdf_url')
    image_url = data.get('image_url')
    flows_raw = data.get('flows', [])
    edges_raw = data.get('edges', [])
    template_id = data.get('template_id')
    menu_json = data.get('menu_json')
    power_config = data.get('powerConfig', {})
    plan_type = data.get('plan_type')
    avatar = data.get('avatar')
    menu_options = data.get('menu_options')
    response_limit = data.get('response_limit')
    conversation_count = data.get('conversation_count')
    message_count = data.get('message_count')
    is_webchat_enabled = data.get('is_webchat_enabled')
    initial_message = data.get('initial_message')

    if not name:
        return jsonify({'status': 'error', 'message': 'El nombre del plubot es obligatorio'}), 400

    if not isinstance(powers, list):
        return jsonify({'status': 'error', 'message': 'Los poderes deben ser una lista'}), 400

    flows = []
    user_messages = set()
    for index, flow in enumerate(flows_raw):
        try:
            validated_flow = FlowModel(**flow)
            user_msg = validated_flow.user_message.lower()
            if not user_msg or not validated_flow.bot_response:
                return jsonify({
                    'status': 'error',
                    'message': f'El flujo en la posición {index} tiene mensajes vacíos.'
                }), 400
            if user_msg in user_messages:
                return jsonify({
                    'status': 'error',
                    'message': f'El mensaje de usuario "{user_msg}" en la posición {index} está duplicado.'
                }), 400
            user_messages.add(user_msg)
            flows.append(validated_flow.dict())
        except Exception as e:
            logger.error(f"Flujo inválido en posición {index}: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Flujo inválido en posición {index}: {str(e)}'}), 400

    with get_session() as session:
        try:
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                return jsonify({'status': 'error', 'message': 'Plubot no encontrado o no tienes permisos'}), 404

            plubot.name = name
            if tone:
                if tone.lower() not in PERSONALITIES:
                    return jsonify({
                        'status': 'error',
                        'message': f"Tono inválido. Opciones válidas: {', '.join(PERSONALITIES.keys())}"
                    }), 400
                plubot.tone = tone.lower()
                if not initial_message:
                    plubot.initial_message = PERSONALITIES[tone.lower()]['welcome']
                plubot.color = PERSONALITIES[tone.lower()]['color']
            if purpose:
                plubot.purpose = purpose
            if color:
                plubot.color = color
            if powers:
                plubot.powers = powers
            if whatsapp_number:
                plubot.whatsapp_number = whatsapp_number
            if business_info is not None:
                plubot.business_info = business_info
            if pdf_url is not None:
                plubot.pdf_url = pdf_url
                process_pdf_async.delay(plubot_id, pdf_url)
            if image_url is not None:
                plubot.image_url = image_url
            if power_config:
                plubot.power_config = power_config
            if plan_type:
                plubot.plan_type = plan_type
            if avatar is not None:
                plubot.avatar = avatar
            if menu_options is not None:
                plubot.menu_options = menu_options
            if response_limit is not None:
                plubot.response_limit = response_limit
            if conversation_count is not None:
                plubot.conversation_count = conversation_count
            if message_count is not None:
                plubot.message_count = message_count
            if is_webchat_enabled is not None:
                plubot.is_webchat_enabled = is_webchat_enabled
            if initial_message:
                plubot.initial_message = initial_message

            if power_config.get('google-sheets', {}).get('credentials'):
                user = session.query(User).filter_by(id=user_id).first()
                if user:
                    user.google_sheets_credentials = power_config['google-sheets']['credentials']
                else:
                    logger.error(f"Usuario con ID {user_id} no encontrado")
                    return jsonify({'status': 'error', 'message': 'Usuario no encontrado'}), 404

            flows_to_save = flows
            if template_id:
                template = session.query(Template).filter_by(id=template_id).first()
                if template:
                    plubot.tone = template.tone
                    plubot.purpose = template.purpose
                    template_flows = json.loads(template.flows)
                    flows_to_save = template_flows + flows if flows else template_flows

            if menu_json:
                menu_flows = parse_menu_to_flows(menu_json)
                flows_to_save = flows_to_save + menu_flows if flows_to_save else menu_flows

            existing_flows = session.query(Flow).filter_by(chatbot_id=plubot_id).order_by(Flow.position).all()
            existing_flow_ids = [flow.id for flow in existing_flows]

            # Eliminar primero las aristas (FlowEdge) y luego los flujos (Flow)
            if existing_flow_ids:
                session.query(FlowEdge).filter(
                    (FlowEdge.source_flow_id.in_(existing_flow_ids)) | (FlowEdge.target_flow_id.in_(existing_flow_ids))
                ).delete(synchronize_session=False)
                session.query(Flow).filter_by(chatbot_id=plubot_id).delete(synchronize_session=False)

            flow_id_map = {}
            new_flows = []
            for index, flow in enumerate(flows_to_save):
                if not flow.get('user_message') or not flow.get('bot_response'):
                    continue
                user_message = flow['user_message']
                intent = flow.get('intent', 'general')
                condition = flow.get('condition', '')
                position_x = flow.get('position_x')  # Nuevo: obtener position_x
                position_y = flow.get('position_y')  # Nuevo: obtener position_y
                flow_entry = Flow(
                    chatbot_id=plubot_id,
                    user_message=user_message,
                    bot_response=flow['bot_response'],
                    position=index,
                    intent=intent,
                    condition=condition,
                    position_x=position_x,  # Nuevo: asignar position_x
                    position_y=position_y   # Nuevo: asignar position_y
                )
                session.add(flow_entry)
                new_flows.append(flow_entry)
                session.flush()
                flow_id_map[str(index)] = flow_entry.id

            for edge in edges_raw:
                source_id = flow_id_map.get(edge.get('source'))
                target_id = flow_id_map.get(edge.get('target'))
                if source_id and target_id:
                    edge_entry = FlowEdge(
                        chatbot_id=plubot_id,
                        source_flow_id=source_id,
                        target_flow_id=target_id,
                        condition=edge.get('sourceHandle', '')
                    )
                    session.add(edge_entry)

            session.commit()
            return jsonify({
                'status': 'success',
                'message': f"Plubot '{name}' actualizado con éxito.",
                'plubot': {
                    'id': plubot.id,
                    'name': plubot.name,
                    'tone': plubot.tone,
                    'purpose': plubot.purpose,
                    'color': plubot.color,
                    'powers': plubot.powers,
                    'whatsapp_number': plubot.whatsapp_number,
                    'initial_message': plubot.initial_message,
                    'business_info': plubot.business_info,
                    'pdf_url': plubot.pdf_url,
                    'image_url': plubot.image_url,
                    'created_at': plubot.created_at.isoformat() if plubot.created_at else None,
                    'updated_at': plubot.updated_at.isoformat() if plubot.updated_at else None,
                    'plan_type': plubot.plan_type,
                    'avatar': plubot.avatar,
                    'menu_options': plubot.menu_options,
                    'response_limit': plubot.response_limit,
                    'conversation_count': plubot.conversation_count,
                    'message_count': plubot.message_count,
                    'is_webchat_enabled': plubot.is_webchat_enabled,
                    'power_config': plubot.power_config
                }
            }), 200
        except Exception as e:
            session.rollback()
            logger.error(f"Error al actualizar el Plubot {plubot_id}: {str(e)}")
            if "ForeignKeyViolation" in str(e):
                return jsonify({
                    'status': 'error',
                    'message': 'No se puede actualizar el Plubot porque tiene flujos con conexiones activas. Por favor, elimina las conexiones primero o contacta al soporte.'
                }), 400
            return jsonify({'status': 'error', 'message': f'Error al actualizar el Plubot: {str(e)}'}), 500

@plubots_bp.route('/delete/<int:plubot_id>', methods=['DELETE'])
@jwt_required()
def delete_bot(plubot_id):
    user_id = get_jwt_identity()
    with get_session() as session:
        try:
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                return jsonify({'status': 'error', 'message': 'Plubot no encontrado o no tienes permisos'}), 404

            existing_flows = session.query(Flow).filter_by(chatbot_id=plubot_id).all()
            existing_flow_ids = [flow.id for flow in existing_flows]
            if existing_flow_ids:
                session.query(FlowEdge).filter(
                    (FlowEdge.source_flow_id.in_(existing_flow_ids)) | (FlowEdge.target_flow_id.in_(existing_flow_ids))
                ).delete(synchronize_session=False)
            session.query(Flow).filter_by(chatbot_id=plubot_id).delete(synchronize_session=False)
            session.query(Plubot).filter_by(id=plubot_id).delete(synchronize_session=False)
            session.commit()
            return jsonify({'status': 'success', 'message': f"Plubot '{plubot.name}' eliminado con éxito."}), 200
        except Exception as e:
            session.rollback()
            logger.error(f"Error al eliminar el Plubot {plubot_id}: {str(e)}")
            if "ForeignKeyViolation" in str(e):
                return jsonify({
                    'status': 'error',
                    'message': 'No se puede eliminar el Plubot porque tiene flujos con conexiones activas. Por favor, elimina las conexiones primero o contacta al soporte.'
                }), 400
            return jsonify({'status': 'error', 'message': f'Error al eliminar el Plubot: {str(e)}'}), 500

@plubots_bp.route('/<int:plubot_id>', methods=['GET', 'OPTIONS'])
@jwt_required()
def get_bot(plubot_id):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    user_id = get_jwt_identity()
    with get_session() as session:
        plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
        if not plubot:
            return jsonify({'status': 'error', 'message': 'Plubot no encontrado o no tienes permisos'}), 404

        flows = session.query(Flow).filter_by(chatbot_id=plubot_id).order_by(Flow.position).all()
        edges = session.query(FlowEdge).filter_by(chatbot_id=plubot_id).all()
        logger.info(f"[DEBUG] Edges recuperados para plubot_id {plubot_id}: {[(e.source_flow_id, e.target_flow_id) for e in edges]}")

        flow_id_to_position = {flow.id: str(flow.position) for flow in flows}
        flows_data = [
            {
                'position': flow.position,
                'user_message': flow.user_message,
                'bot_response': flow.bot_response,
                'intent': flow.intent,
                'condition': flow.condition,
                'position_x': flow.position_x,  # Nuevo: incluir position_x
                'position_y': flow.position_y   # Nuevo: incluir position_y
            } for flow in flows
        ]
        edges_data = [
            {
                'source': flow_id_to_position.get(edge.source_flow_id, str(edge.source_flow_id)),
                'target': flow_id_to_position.get(edge.target_flow_id, str(edge.target_flow_id)),
                'sourceHandle': edge.condition if edge.condition else None
            } for edge in edges
        ]
        logger.info(f"[DEBUG] Edges_data generados: {edges_data}")

        return jsonify({
            'status': 'success',
            'plubot': {
                'id': plubot.id,
                'name': plubot.name,
                'tone': plubot.tone,
                'purpose': plubot.purpose,
                'color': plubot.color,
                'powers': plubot.powers,
                'whatsapp_number': plubot.whatsapp_number,
                'initial_message': plubot.initial_message,
                'business_info': plubot.business_info,
                'pdf_url': plubot.pdf_url,
                'image_url': plubot.image_url,
                'created_at': plubot.created_at.isoformat() if plubot.created_at else None,
                'updated_at': plubot.updated_at.isoformat() if plubot.updated_at else None,
                'plan_type': plubot.plan_type,
                'avatar': plubot.avatar,
                'menu_options': plubot.menu_options,
                'response_limit': plubot.response_limit,
                'conversation_count': plubot.conversation_count,
                'message_count': plubot.message_count,
                'is_webchat_enabled': plubot.is_webchat_enabled,
                'power_config': plubot.power_config,
                'flows': flows_data,
                'edges': edges_data
            }
        }), 200