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
import time

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
            node_id_map = {}
            new_flows = []
            
            # Primero, crear todos los flujos y guardar sus IDs
            for index, flow in enumerate(flows_to_save):
                if not flow.get('user_message') or not flow.get('bot_response'):
                    continue
                    
                user_message = flow['user_message']
                intent = flow.get('intent', 'general')
                condition = flow.get('condition', '')
                position_x = flow.get('position_x')
                position_y = flow.get('position_y')
                # Obtener el ID original del nodo enviado por el frontend
                original_node_id = flow.get('node_id')
                
                # Asegurarse de que position_x y position_y sean números, usando 0.0 como valor por defecto
                position_x = float(position_x) if position_x is not None else 0.0
                position_y = float(position_y) if position_y is not None else 0.0
                
                # Crear un flujo en la base de datos
                flow_entry = Flow(
                    chatbot_id=plubot_id,
                    user_message=user_message,
                    bot_response=flow['bot_response'],
                    position=index,
                    intent=intent,
                    condition=condition,
                    position_x=position_x,
                    position_y=position_y
                )
                
                session.add(flow_entry)
                new_flows.append(flow_entry)
                session.flush()  # Para obtener el ID generado
                
                # Guardar el mapeo entre el ID original del nodo y el ID de la base de datos
                if original_node_id:
                    node_id_map[original_node_id] = flow_entry.id
                    logger.info(f"Mapeando nodo original {original_node_id} a ID de BD {flow_entry.id}")
                
                # También guardar mapeos por índice y formato node-index para compatibilidad
                flow_id_map[str(index)] = flow_entry.id
                flow_id_map[f"node-{index}"] = flow_entry.id

            # Procesar las aristas con toda la información necesaria
            logger.info(f"Procesando {len(edges_raw)} aristas para guardar")
            
            # Crear un mapa de IDs de nodos para buscar por node_id
            node_id_to_flow_entry = {}
            node_id_map = {}  # Mapa adicional para node_id -> flow_entry.id
            
            # Primero, crear un mapa de posición -> flow_entry.id
            position_to_id = {}
            for flow_entry in new_flows:
                position_to_id[flow_entry.position] = flow_entry.id
                
            # Luego, mapear node_id -> position -> flow_entry.id
            for i, flow in enumerate(flows_to_save):
                node_id = flow.get('node_id')
                if node_id and i < len(new_flows):
                    flow_id = position_to_id.get(i)
                    if flow_id:
                        node_id_to_flow_entry[node_id] = flow_id
                        node_id_map[node_id] = flow_id
                        logger.info(f"Mapeando nodo {node_id} a flow_id {flow_id} (posición {i})")
            
            for i, edge in enumerate(edges_raw):
                try:
                    # Extraer todos los datos relevantes de la arista
                    source = edge.get('source')
                    target = edge.get('target')
                    edge_type = edge.get('type', 'default')
                    label = edge.get('label', '')
                    source_handle = edge.get('sourceHandle')
                    target_handle = edge.get('targetHandle')
                    edge_id = edge.get('id')
                    style = edge.get('style', {})
                    
                    # Intentar obtener los IDs de la base de datos directamente
                    source_id = node_id_to_flow_entry.get(source)
                    target_id = node_id_to_flow_entry.get(target)
                    
                    logger.info(f"Arista {i+1}/{len(edges_raw)}: source={source}->{source_id}, target={target}->{target_id}, type={edge_type}")
                    
                    # Si no se encuentran los IDs, usar los IDs originales directamente
                    if not source_id or not target_id:
                        # Buscar los nodos por su posición en el flujo
                        for flow_entry in new_flows:
                            if not source_id and str(flow_entry.position) == source:
                                source_id = flow_entry.id
                                logger.info(f"Encontrado source_id={source_id} por posición {source}")
                            if not target_id and str(flow_entry.position) == target:
                                target_id = flow_entry.id
                                logger.info(f"Encontrado target_id={target_id} por posición {target}")
                    
                    # No podemos usar los IDs originales directamente como IDs de flujo en la base de datos
                    # porque no existen en la tabla flows. Debemos usar los IDs de los flujos que acabamos de crear.
                    if not source_id or not target_id:
                        logger.info(f"No se encontraron IDs para la arista: {source} -> {target}")
                        
                        # Buscar por posición en el array de flows_to_save
                        source_pos = None
                        target_pos = None
                        
                        for i, flow in enumerate(flows_to_save):
                            if flow.get('node_id') == source:
                                source_pos = i
                                logger.info(f"Nodo source {source} está en posición {i}")
                            if flow.get('node_id') == target:
                                target_pos = i
                                logger.info(f"Nodo target {target} está en posición {i}")
                        
                        # Usar el mapa de posición -> ID
                        if source_pos is not None and source_pos in position_to_id:
                            source_id = position_to_id[source_pos]
                            logger.info(f"Encontrado source_id={source_id} para node_id={source} en posición {source_pos}")
                        
                        if target_pos is not None and target_pos in position_to_id:
                            target_id = position_to_id[target_pos]
                            logger.info(f"Encontrado target_id={target_id} para node_id={target} en posición {target_pos}")
                    
                    # Verificar que tenemos IDs válidos para source y target
                    if not source_id or not target_id:
                        logger.warning(f"No se pudieron mapear los IDs para la arista: {source} -> {target}")
                        # Como último recurso, usar los primeros dos flujos disponibles
                        if len(new_flows) >= 2:
                            source_id = new_flows[0].id
                            target_id = new_flows[1].id
                            logger.info(f"Usando flujos alternativos: {source_id} -> {target_id}")
                        else:
                            continue
                    
                    # Guardar los metadatos de la arista en el campo condition como JSON
                    edge_metadata = {
                        "source_original": source,
                        "target_original": target,
                        "sourceHandle": source_handle,
                        "targetHandle": target_handle,
                        "edge_id": edge_id,
                        "style": style
                    }
                    
                    # Crear la arista en la base de datos
                    try:
                        edge_entry = FlowEdge(
                            chatbot_id=plubot_id,
                            source_flow_id=source_id,
                            target_flow_id=target_id,
                            condition=label + "|||" + json.dumps(edge_metadata) if label else "|||" + json.dumps(edge_metadata),
                            edge_type=edge_type
                        )
                        
                        session.add(edge_entry)
                        logger.info(f"Arista añadida: {source_id} -> {target_id}")
                    except Exception as e:
                        logger.error(f"Error al crear arista: {e}")
                        # Intentar una última alternativa: usar los primeros flujos disponibles
                        if len(new_flows) >= 2:
                            try:
                                # Usar los primeros dos flujos como alternativa
                                alt_source_id = new_flows[0].id
                                alt_target_id = new_flows[1].id
                                
                                edge_entry = FlowEdge(
                                    chatbot_id=plubot_id,
                                    source_flow_id=alt_source_id,
                                    target_flow_id=alt_target_id,
                                    condition=label + "|||" + json.dumps(edge_metadata) if label else "|||" + json.dumps(edge_metadata),
                                    edge_type=edge_type
                                )
                                
                                session.add(edge_entry)
                                logger.info(f"Arista alternativa añadida: {alt_source_id} -> {alt_target_id}")
                            except Exception as e2:
                                logger.error(f"Error al crear arista alternativa: {e2}")
                                continue
                except Exception as e:
                    logger.error(f"Error al procesar arista {i+1}/{len(edges_raw)}: {e}")
                    # Continuar con la siguiente arista
                    continue

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
                }
            }), 200
        except Exception as e:
            session.rollback()
            logger.error(f"Error al actualizar el plubot: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

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

@plubots_bp.route('/<int:plubot_id>/embed', methods=['POST'])
@jwt_required()
def generate_embed_resources(plubot_id):
    try:
        user_id = get_jwt_identity()
        
        # Usar get_session como context manager con with
        with get_session() as session:
            # Verificar que el plubot existe y pertenece al usuario
            plubot = session.query(Plubot).filter(Plubot.id == plubot_id, Plubot.user_id == user_id).first()
            if not plubot:
                return jsonify({'status': 'error', 'message': 'Plubot no encontrado o no tienes permiso para acceder a él'}), 404
            
            # Obtener los datos de personalización del request
            data = request.get_json()
            customization = data.get('customization', {})
            
            # En una implementación real, aquí se generaría un ID público único
            # Para esta implementación, usamos el ID del plubot como ID público
            public_id = str(plubot_id)
            
            # Generar URL para el código QR
            qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={request.host_url}chat/{public_id}"
            
            # Actualizar el estado de webchat_enabled si no está habilitado
            if not plubot.is_webchat_enabled:
                plubot.is_webchat_enabled = True
                session.commit()
        
        return jsonify({
            'status': 'success',
            'data': {
                'publicId': public_id,
                'qrCodeUrl': qr_code_url,
                'customization': customization
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error generando recursos de embebido: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Endpoint público para cargar información del chatbot (sin autenticación JWT)
@plubots_bp.route('/chat/<string:public_id>', methods=['GET'])
def get_public_bot(public_id):
    try:
        # Convertir public_id a int para buscar el plubot
        # En una implementación real, habría una tabla que mapee IDs públicos a IDs de plubot
        try:
            plubot_id = int(public_id)
        except ValueError:
            return jsonify({'status': 'error', 'message': 'ID de chatbot inválido'}), 400
        
        # Variables para almacenar datos que se usarán fuera del bloque with
        plubot_data = None
        flows_data = []
        edges_data = []
        welcome_message = None
        personality = None
        
        # Usar get_session como context manager con with
        with get_session() as session:
            plubot = session.query(Plubot).filter(Plubot.id == plubot_id).first()
            if not plubot:
                return jsonify({'status': 'error', 'message': 'Chatbot no encontrado'}), 404
            
            logger.info(f"Plubot encontrado: {plubot.name} (ID: {plubot.id})")
            
            # Verificar si el webchat está habilitado
            if not plubot.is_webchat_enabled:
                return jsonify({'status': 'error', 'message': 'Este chatbot no está disponible para chat público'}), 403
            
            # Obtener el mensaje de bienvenida según la personalidad
            personality = plubot.tone or "servicial"
            welcome_message = PERSONALITIES.get(personality, PERSONALITIES["servicial"])["welcome"]
            
            # Guardar datos del plubot que necesitaremos fuera del bloque with
            plubot_data = {
                'id': plubot.id,
                'name': plubot.name,
                'color': plubot.color or PERSONALITIES.get(personality, PERSONALITIES["servicial"])["color"],
            }
            
            # Obtener flujos y bordes - Corregido para usar chatbot_id
            flows = session.query(Flow).filter(Flow.chatbot_id == plubot.id).order_by(Flow.position).all()
            edges = session.query(FlowEdge).filter(FlowEdge.chatbot_id == plubot.id).all()
            
            logger.info(f"Flujos encontrados: {len(flows)}, Bordes encontrados: {len(edges)}")
            
            # Crear mapeo de ID de flujo a posición
            flow_id_to_position = {flow.id: str(flow.position) for flow in flows}
            
            # Preparar datos para enviar al frontend
            for flow in flows:
                flow_data = {
                    'position': flow.position,
                    'intent': flow.intent,
                    'user_message': flow.user_message,
                    'bot_response': flow.bot_response,
                    'position_x': flow.position_x,
                    'position_y': flow.position_y,
                    'condition': flow.condition,
                    'actions': flow.actions
                }
                flows_data.append(flow_data)
            
            for edge in edges:
                edge_data = {
                    'source': flow_id_to_position.get(edge.source_flow_id, str(edge.source_flow_id)),
                    'target': flow_id_to_position.get(edge.target_flow_id, str(edge.target_flow_id)),
                    'sourceHandle': edge.condition if edge.condition else None
                }
                edges_data.append(edge_data)
        
        # Construir la respuesta fuera del bloque with usando los datos recopilados
        return jsonify({
            'status': 'success',
            'data': {
                'id': plubot_data['id'],
                'name': plubot_data['name'],
                'color': plubot_data['color'],
                'initialMessage': welcome_message,
                'embedConfig': {
                    'theme': 'light',  # Por defecto
                    'position': 'right'
                },
                'flows': flows_data,
                'edges': edges_data
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error cargando chatbot público: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Endpoint público para manejar mensajes del chat (sin autenticación JWT)
@plubots_bp.route('/chat/<string:public_id>/message', methods=['POST'])
def handle_chat_message(public_id):
    try:
        logger.info(f"Recibida solicitud POST a /chat/{public_id}/message")
        data = request.get_json()
        logger.info(f"Datos recibidos: {data}")
        
        if not data or 'message' not in data:
            logger.warning("No se proporcionó un mensaje en la solicitud")
            return jsonify({'status': 'error', 'message': 'Se requiere un mensaje'}), 400
        
        user_message = data['message']
        current_flow_id = data.get('current_flow_id')
        conversation_history = data.get('conversation_history', [])
        
        logger.info(f"Mensaje del usuario: '{user_message}', current_flow_id: {current_flow_id}")
        
        # Convertir public_id a int para buscar el plubot
        try:
            plubot_id = int(public_id)
            logger.info(f"ID del plubot convertido: {plubot_id}")
        except ValueError:
            logger.warning(f"ID de chatbot inválido: {public_id}")
            return jsonify({'status': 'error', 'message': 'ID de chatbot inválido'}), 400
        
        # Variables para almacenar datos fuera del bloque with
        response = None
        next_flow_id = None  # Almacenar solo el ID, no el objeto
        is_decision_node = False
        options = []
        
        # Usar get_session como context manager con with
        with get_session() as session:
            # Obtener el plubot
            plubot = session.query(Plubot).filter(Plubot.id == plubot_id).first()
            if not plubot:
                logger.warning(f"Chatbot con ID {plubot_id} no encontrado")
                return jsonify({'status': 'error', 'message': 'Chatbot no encontrado'}), 404
            
            logger.info(f"Plubot encontrado: {plubot.name} (ID: {plubot.id})")
            
            # Verificar si el webchat está habilitado
            if not plubot.is_webchat_enabled:
                logger.warning(f"Chatbot {plubot.id} no tiene habilitado el webchat")
                return jsonify({'status': 'error', 'message': 'Este chatbot no está disponible para chat público'}), 403
            
            # Obtener flujos y bordes
            flows = session.query(Flow).filter(Flow.chatbot_id == plubot.id).all()
            edges = session.query(FlowEdge).filter(FlowEdge.chatbot_id == plubot.id).all()
            
            logger.info(f"Flujos encontrados: {len(flows)}, Bordes encontrados: {len(edges)}")
            
            # Crear mapeos útiles
            flow_id_map = {flow.id: flow for flow in flows}
            
            # Lógica para determinar el siguiente flujo
            next_flow = None
            
            # Si tenemos un current_flow_id, buscar los bordes que salen de ese nodo
            if current_flow_id:
                logger.info(f"Usando current_flow_id: {current_flow_id} para determinar el siguiente nodo")
                
                # Buscar bordes que salen del nodo actual
                current_edges = [e for e in edges if e.source_flow_id == current_flow_id]
                logger.info(f"Bordes encontrados desde el nodo actual: {len(current_edges)}")
                
                if current_edges:
                    # Si hay múltiples bordes, intentar encontrar uno que coincida con el mensaje del usuario
                    # Esto es útil para nodos de decisión donde el usuario selecciona una opción
                    matching_edge = None
                    
                    # Primero intentar con coincidencia exacta de condición
                    for edge in current_edges:
                        if edge.condition and user_message.lower() == edge.condition.lower():
                            matching_edge = edge
                            logger.info(f"Coincidencia exacta con condición del borde: {edge.condition}")
                            break
                    
                    # Si no hay coincidencia exacta, intentar con coincidencia parcial
                    if not matching_edge:
                        for edge in current_edges:
                            if edge.condition and user_message.lower() in edge.condition.lower():
                                matching_edge = edge
                                logger.info(f"Coincidencia parcial con condición del borde: {edge.condition}")
                                break
                    
                    # Si aún no hay coincidencia, usar el primer borde (comportamiento por defecto)
                    if not matching_edge and current_edges:
                        matching_edge = current_edges[0]
                        logger.info(f"Usando primer borde por defecto: {matching_edge.source_flow_id} -> {matching_edge.target_flow_id}")
                    
                    # Si encontramos un borde, obtener el flujo destino
                    if matching_edge:
                        target_flow = flow_id_map.get(matching_edge.target_flow_id)
                        if target_flow:
                            logger.info(f"Flujo destino encontrado: ID {target_flow.id}")
                            next_flow = target_flow
                        else:
                            logger.warning(f"No se encontró flujo destino para el borde {matching_edge.id}")
                else:
                    logger.info(f"No se encontraron bordes desde el nodo actual (ID: {current_flow_id})")
                    
                    # Si no hay bordes, verificar si es un nodo final
                    current_flow = flow_id_map.get(current_flow_id)
                    if current_flow and current_flow.intent == 'end':
                        logger.info(f"El nodo actual (ID: {current_flow_id}) es un nodo final, reiniciando al nodo de inicio")
                        
                        # Reiniciar al nodo de inicio
                        start_flows = [f for f in flows if f.intent == 'start']
                        if start_flows:
                            start_flow = start_flows[0]
                            logger.info(f"Nodo de inicio encontrado: ID {start_flow.id}")
                            
                            # Buscar un borde que salga del nodo de inicio
                            start_edge = next((e for e in edges if e.source_flow_id == start_flow.id), None)
                            if start_edge:
                                target_flow = flow_id_map.get(start_edge.target_flow_id)
                                if target_flow:
                                    logger.info(f"Flujo destino desde inicio encontrado: ID {target_flow.id}")
                                    next_flow = target_flow
                                else:
                                    logger.warning(f"No se encontró flujo destino para el borde desde inicio {start_edge.id}")
                            else:
                                logger.info("No se encontraron bordes desde el nodo de inicio, usando el nodo de inicio")
                                next_flow = start_flow
            
            # Si no tenemos un current_flow_id o no pudimos encontrar el siguiente nodo,
            # usar la lógica original
            if not next_flow:
                # 1. Buscar un flujo que coincida con el mensaje del usuario
                for flow in flows:
                    if flow.user_message and user_message.lower() in flow.user_message.lower():
                        logger.info(f"Encontrada coincidencia con flujo ID {flow.id}: '{flow.user_message}'")
                        next_flow = flow
                        break
                
                # 2. Si no hay coincidencia, buscar un nodo de inicio y seguir el primer borde
                if not next_flow:
                    logger.info("No se encontró coincidencia, buscando nodo de inicio")
                    start_flows = [f for f in flows if f.intent == 'start']
                    if start_flows:
                        start_flow = start_flows[0]
                        logger.info(f"Nodo de inicio encontrado: ID {start_flow.id}")
                        
                        # Buscar un borde que salga del nodo de inicio
                        start_edge = next((e for e in edges if e.source_flow_id == start_flow.id), None)
                        if start_edge:
                            logger.info(f"Borde desde nodo de inicio encontrado: {start_edge.source_flow_id} -> {start_edge.target_flow_id}")
                            target_flow = flow_id_map.get(start_edge.target_flow_id)
                            if target_flow:
                                logger.info(f"Flujo destino encontrado: ID {target_flow.id}")
                                next_flow = target_flow
                            else:
                                logger.warning(f"No se encontró flujo destino para el borde {start_edge.id}")
                        else:
                            logger.info("No se encontraron bordes desde el nodo de inicio, usando el nodo de inicio")
                            next_flow = start_flow
                    else:
                        logger.info("No se encontró nodo de inicio, buscando nodos de mensaje")
                        message_flows = [f for f in flows if f.intent == 'message']
                        if message_flows:
                            logger.info(f"Usando primer nodo de mensaje: ID {message_flows[0].id}")
                            next_flow = message_flows[0]
                        else:
                            logger.warning("No se encontraron nodos de mensaje")
            
            # Obtener la respuesta y otros datos necesarios dentro del bloque with
            if next_flow:
                logger.info(f"Usando flujo ID {next_flow.id} para respuesta: '{next_flow.bot_response}'")
                response = next_flow.bot_response
                next_flow_id = next_flow.id  # Guardar solo el ID, no el objeto
                
                # Verificar si es un nodo de decisión
                if next_flow.intent == 'decision':
                    logger.info(f"El flujo ID {next_flow.id} es un nodo de decisión")
                    is_decision_node = True
                    
                    # Buscar bordes que salen del nodo de decisión
                    decision_edges = [e for e in edges if e.source_flow_id == next_flow.id]
                    logger.info(f"Bordes encontrados desde el nodo de decisión: {len(decision_edges)}")
                    
                    # Para cada borde, encontrar el flujo destino y agregarlo como opción
                    for edge in decision_edges:
                        target_flow = flow_id_map.get(edge.target_flow_id)
                        if target_flow:
                            option_label = edge.condition if edge.condition else "Opción"
                            logger.info(f"Opción encontrada: {option_label} -> Flujo ID {target_flow.id}")
                            # Guardar solo los datos necesarios, no el objeto
                            options.append({
                                "id": target_flow.id,
                                "label": option_label,
                                "message": target_flow.user_message
                            })
            else:
                logger.warning("No se encontró un flujo para responder")
                response = "Lo siento, no entiendo tu mensaje. ¿Puedes reformularlo?"
            
            # Incrementar contador de mensajes
            plubot.message_count = (plubot.message_count or 0) + 1
            session.commit()
            logger.info(f"Contador de mensajes incrementado: {plubot.message_count}")
            
            # Crear el historial de conversación dentro del bloque with
            if next_flow:
                # Crear nuevos objetos para el historial, no usar referencias a objetos de la sesión
                new_conversation_history = list(conversation_history) if conversation_history else []
                new_conversation_history.append({
                    "role": "user",
                    "message": user_message
                })
                new_conversation_history.append({
                    "role": "bot",
                    "message": response,
                    "flow_id": next_flow_id  # Usar el ID, no el objeto
                })
                conversation_history = new_conversation_history
                logger.info("Historial de conversación actualizado")
        
        # Construir la respuesta fuera del bloque with usando solo datos primitivos
        result = {
            'status': 'success',
            'response': response,
            'conversation_history': conversation_history
        }
        
        # Si tenemos un flujo siguiente, incluir su ID
        if next_flow_id:
            result['current_flow_id'] = next_flow_id
        
        # Si es un nodo de decisión, incluir las opciones
        if is_decision_node and options:
            result['is_decision'] = True
            result['options'] = options
            logger.info(f"Incluyendo {len(options)} opciones en la respuesta")
        
        logger.info("Enviando respuesta exitosa")
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error procesando mensaje de chat: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@plubots_bp.route('/<int:plubot_id>/flow', methods=['GET', 'POST'])
@jwt_required()
def handle_flow(plubot_id):
    """
    Endpoint para manejar la carga y guardado de flujos de un plubot
    GET: Obtener el flujo actual
    POST: Guardar un nuevo flujo
    """
    user_id = get_jwt_identity()
    
    try:
        with get_session() as session:
            # Verificar que el plubot existe y pertenece al usuario
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                return jsonify({'status': 'error', 'message': 'Plubot no encontrado o no tienes permisos'}), 404
            
            if request.method == 'GET':
                # Obtener todos los flujos y aristas asociados al plubot
                flows = session.query(Flow).filter_by(chatbot_id=plubot_id).all()
                edges = session.query(FlowEdge).filter_by(chatbot_id=plubot_id).all()
                
                logger.debug(f"Flows recuperados para plubot_id {plubot_id}: {len(flows)}")
                logger.debug(f"Edges recuperados para plubot_id {plubot_id}: {len(edges)}")
                
                # Crear un mapa de IDs de flujos a node_ids para reconstruir las aristas
                flow_id_to_node = {}
                for flow in flows:
                    # El node_id será el ID del flujo en la base de datos como string
                    flow_id_to_node[flow.id] = str(flow.id)
                
                # Convertir flujos a formato esperado por el frontend
                nodes = []
                for flow in flows:
                    node = {
                        'id': str(flow.id),
                        'type': flow.intent or 'message',
                        'position': {'x': flow.position_x or 0, 'y': flow.position_y or 0},
                        'data': {
                            'label': flow.user_message,
                            'message': flow.bot_response
                        }
                    }
                    nodes.append(node)
                
                # Convertir aristas a formato esperado por el frontend
                formatted_edges = []
                logger.info(f"Procesando {len(edges)} aristas para enviar al frontend")
                
                for edge in edges:
                    try:
                        # Intentar acceder a edge_type de manera segura
                        edge_type = getattr(edge, 'edge_type', 'default')
                        
                        # Extraer los IDs originales y handles del campo condition si están disponibles
                        source_id = str(edge.source_flow_id)
                        target_id = str(edge.target_flow_id)
                        source_handle = None
                        target_handle = None
                        label = None
                        edge_id = None
                        style = {}
                        
                        # Intentar extraer metadatos del campo condition
                        if edge.condition:
                            # Verificar si tenemos metadatos en el campo condition
                            parts = edge.condition.split('|||')
                            if len(parts) > 1:
                                # Si hay metadatos, extraerlos
                                label = parts[0] if parts[0] else None
                                try:
                                    metadata = json.loads(parts[1])
                                    # Usar los IDs originales si están disponibles
                                    if metadata.get('source_original'):
                                        source_id = metadata.get('source_original')
                                    if metadata.get('target_original'):
                                        target_id = metadata.get('target_original')
                                    source_handle = metadata.get('sourceHandle')
                                    target_handle = metadata.get('targetHandle')
                                    edge_id = metadata.get('edge_id')
                                    style = metadata.get('style', {})
                                    logger.info(f"Metadatos recuperados para arista: {source_id} -> {target_id}")
                                except json.JSONDecodeError as e:
                                    # Si no podemos decodificar los metadatos, usamos la condición como etiqueta
                                    logger.error(f"Error decodificando metadatos: {e}")
                                    label = edge.condition
                            else:
                                # Si no hay metadatos, usamos la condición como etiqueta
                                label = edge.condition
                        
                        # Si no tenemos IDs originales, usar los IDs de la base de datos pero asegurarnos de que sean strings
                        if not source_id:
                            source_id = str(edge.source_flow_id)
                        if not target_id:
                            target_id = str(edge.target_flow_id)
                        
                        # Crear un ID único para la arista
                        if not edge_id:
                            edge_id = f"edge-{source_id}-{target_id}-{int(time.time() * 1000)}"  # Añadir timestamp para garantizar unicidad
                        
                        formatted_edge = {
                            'id': edge_id,
                            'source': source_id,
                            'target': target_id,
                            'type': edge_type,
                            'sourceOriginal': source_id,  # Guardar el ID original como referencia
                            'targetOriginal': target_id   # Guardar el ID original como referencia
                        }
                        
                        # Añadir handles si están disponibles
                        if source_handle:
                            formatted_edge['sourceHandle'] = source_handle
                        if target_handle:
                            formatted_edge['targetHandle'] = target_handle
                        
                        # Añadir estilo si está disponible
                        if style:
                            formatted_edge['style'] = style
                        
                        # Añadir etiqueta si está disponible
                        if label:
                            formatted_edge['label'] = label
                        
                        logger.info(f"Arista formateada: {formatted_edge}")
                        formatted_edges.append(formatted_edge)
                    except Exception as e:
                        logger.error(f"Error al formatear arista {edge.id}: {e}")
                        # Continuar con la siguiente arista
                        continue
                
                logger.info(f"Total de aristas formateadas: {len(formatted_edges)}")
                
                
                return jsonify({
                    'status': 'success',
                    'data': {
                        'nodes': nodes,
                        'edges': formatted_edges,
                        'name': plubot.name
                    }
                }), 200
            
            elif request.method == 'POST':
                data = request.get_json()
                if not data:
                    return jsonify({'status': 'error', 'message': 'No se proporcionaron datos'}), 400
                
                nodes = data.get('nodes', [])
                edges = data.get('edges', [])
                name = data.get('name')
                
                # Actualizar nombre del plubot si se proporciona
                if name:
                    plubot.name = name
                
                # Eliminar flujos y aristas existentes para este plubot
                session.query(Flow).filter_by(chatbot_id=plubot_id).delete()
                session.query(FlowEdge).filter_by(chatbot_id=plubot_id).delete()
                
                # Crear mapa para almacenar la relación entre IDs del frontend y backend
                node_id_map = {}
                
                # Guardar nuevos flujos
                for node in nodes:
                    node_id = node.get('id')
                    node_type = node.get('type', 'message')
                    position = node.get('position', {})
                    data = node.get('data', {})
                    
                    # Crear nuevo flujo
                    flow = Flow(
                        chatbot_id=plubot_id,
                        user_message=data.get('label', ''),
                        bot_response=data.get('message', ''),
                        position=0,  # Posición en la lista (legacy)
                        intent=node_type,
                        position_x=position.get('x', 0),
                        position_y=position.get('y', 0)
                    )
                    
                    session.add(flow)
                    session.flush()  # Para obtener el ID generado
                    
                    # Guardar mapeo de IDs
                    node_id_map[node_id] = flow.id
                
                # Guardar nuevas aristas
                logger.info(f"Procesando {len(edges)} aristas para guardar")
                
                for i, edge in enumerate(edges):
                    try:
                        source_id = edge.get('source')
                        target_id = edge.get('target')
                        edge_type = edge.get('type', 'default')
                        condition = edge.get('label', '')
                        source_handle = edge.get('sourceHandle')
                        target_handle = edge.get('targetHandle')
                        
                        logger.info(f"Arista {i+1}/{len(edges)}: source={source_id}, target={target_id}, type={edge_type}")
                        
                        # Guardar los IDs originales del frontend para recuperarlos después
                        source_original = source_id
                        target_original = target_id
                        
                        # Mapear IDs del frontend a IDs del backend
                        backend_source_id = node_id_map.get(source_id)
                        backend_target_id = node_id_map.get(target_id)
                        
                        logger.info(f"IDs mapeados: source={source_id}->{backend_source_id}, target={target_id}->{backend_target_id}")
                        
                        if backend_source_id and backend_target_id:
                            # Crear el objeto FlowEdge con los campos básicos
                            flow_edge = FlowEdge(
                                chatbot_id=plubot_id,
                                source_flow_id=backend_source_id,
                                target_flow_id=backend_target_id,
                                condition=condition
                            )
                            
                            # Guardar los IDs originales y handles en el campo condition como JSON
                            # Esto nos permitirá recuperar los IDs originales al cargar las aristas
                            edge_metadata = {
                                "source_original": source_original,
                                "target_original": target_original,
                                "sourceHandle": source_handle,
                                "targetHandle": target_handle
                            }
                            
                            # Si ya hay una condición, la preservamos
                            if condition:
                                flow_edge.condition = condition + "|||" + json.dumps(edge_metadata)
                            else:
                                flow_edge.condition = "|||" + json.dumps(edge_metadata)
                            
                            # Intentar establecer edge_type de manera segura
                            try:
                                flow_edge.edge_type = edge_type
                                logger.info(f"edge_type establecido correctamente: {edge_type}")
                            except AttributeError as e:
                                # Si edge_type no está disponible, lo manejamos a nivel de base de datos
                                logger.error(f"Error al establecer edge_type: {e}")
                                # Después de añadir el objeto, actualizaremos edge_type directamente en la base de datos
                            
                            session.add(flow_edge)
                            logger.info(f"Arista añadida a la sesión: {flow_edge.source_flow_id} -> {flow_edge.target_flow_id}")
                            
                            # Guardar el edge_type para actualizarlo después si es necesario
                            if 'edge_type_update' not in locals():
                                edge_type_update = []
                            edge_type_update.append((flow_edge, edge_type))
                        else:
                            logger.warning(f"No se pudo mapear los IDs de la arista: {source_id} -> {target_id}")
                    except Exception as e:
                        logger.error(f"Error al procesar arista {i+1}/{len(edges)}: {e}")
                        # Continuar con la siguiente arista
                        continue
                
                # Primero hacemos commit para obtener los IDs de las aristas
                session.commit()
                
                # Ahora actualizamos edge_type directamente en la base de datos si fue necesario
                if 'edge_type_update' in locals() and edge_type_update:
                    for edge_obj, edge_type_value in edge_type_update:
                        try:
                            # Verificar si podemos acceder al atributo normalmente
                            if hasattr(edge_obj, 'edge_type'):
                                continue  # Si ya tiene el atributo, no necesitamos actualizar
                                
                            # Actualizar directamente en la base de datos
                            session.execute(
                                "UPDATE flow_edges SET edge_type = :edge_type WHERE id = :edge_id",
                                {"edge_type": edge_type_value, "edge_id": edge_obj.id}
                            )
                        except Exception as e:
                            print(f"Error al actualizar edge_type: {e}")
                    
                    # Commit los cambios de la actualización directa
                    session.commit()
                
                return jsonify({
                    'status': 'success',
                    'message': 'Flujo guardado correctamente'
                }), 200
        
    except Exception as e:
        logger.error(f"Error manejando flujo para plubot {plubot_id}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)}), 500