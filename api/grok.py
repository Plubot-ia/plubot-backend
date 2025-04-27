from flask import Blueprint, jsonify, request
from services.grok_service import call_grok
import logging
from utils.knowledge_base import KnowledgeBase

grok_bp = Blueprint('grok', __name__)
logger = logging.getLogger(__name__)
kb = KnowledgeBase()  # Instancia global de la base de conocimiento

# BYTE ASSISTANT
@grok_bp.route('/byte-assistant', methods=['POST'])
def byte_assistant():
    data = request.get_json()
    user_message = data.get('message', '')
    history = data.get('history', [])
    if not user_message:
        return jsonify({'error': 'No se proporcionó mensaje'}), 400

    # Prompt optimizado para respuestas cortas
    messages = [
        {
            "role": "system",
            "content": (
                "Eres Byte, un asistente de IA especializado en flujos de conversación para Plubots. "
                "Conoces diseño de flujos, buenas prácticas para chatbots, conexiones entre nodos y detección de problemas (ciclos, nodos huérfanos, callejones sin salida). "
                "Responde en 1-2 frases (máx. 50 palabras) con un tono amigable, técnico y metáforas de circuitos. "
                "Incluye una sugerencia práctica breve solo si es relevante. "
                "Evita listas largas o explicaciones detalladas."
            )
        }
    ]

    # Añadir historial
    for msg in history:
        if msg['sender'] == 'user':
            messages.append({"role": "user", "content": msg['text']})
        elif msg['sender'] == 'byte':
            messages.append({"role": "assistant", "content": msg['text']})

    # Añadir mensaje actual
    messages.append({"role": "user", "content": user_message})

    try:
        # Implementar caché
        cache_key = user_message.strip().lower()
        cached_response = get_from_cache('byte_assistant', cache_key)
        
        if cached_response:
            logger.info(f"Respuesta de caché para Byte: {cached_response}")
            response = cached_response
        else:
            response = call_grok(messages, max_tokens=100, temperature=0.5)
            logger.info(f"Respuesta de Byte (API): {response}")
            # Guardar en caché
            store_in_cache('byte_assistant', cache_key, response)

        # Análisis básico de sentimiento
        sentiment = analyze_sentiment(response)

        return jsonify({
            'message': response,
            'sentiment': sentiment
        })
    except Exception as e:
        logger.error(f"Error en /api/byte-assistant: {str(e)}")
        return jsonify({'error': f"Error: {str(e)}"}), 500
    

# BYTE EMBAJADOR
@grok_bp.route('/byte-embajador', methods=['POST'])
def byte_embajador():
    data = request.get_json()
    user_message = data.get('message', '')
    history = data.get('history', [])
    if not user_message:
        return jsonify({'error': 'No se proporcionó mensaje'}), 400

    try:
        # Primero buscar en la base de conocimiento
        kb_results = kb.search(user_message, threshold=0.6)  # Cambiado a 0.6
        
        # Si hay resultados relevantes en la base de conocimiento, usar esa respuesta
        if kb_results and kb_results[0]['relevance'] >= 0.6:  # Ajustado a >= 0.6
            response = kb_results[0]['answer']
            logger.info(f"Respuesta de KB para Byte Embajador: {response}")
        else:
            # Si no hay resultados relevantes, usar el API de Grok
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Eres Byte, el embajador de Plubot, una plataforma para crear asistentes digitales. "
                        "Tu misión es dar información clara y entusiasta sobre Plubot y cómo crear asistentes digitales. "
                        "Responde en 1-2 frases (máx. 50 palabras) con un tono amigable y motivador, usando metáforas de un universo digital. "
                        "Incluye una sugerencia breve solo si es relevante. "
                        "Evita listas largas o explicaciones detalladas."
                    )
                }
            ]

            # Añadir historial con contexto mejorado
            context = ""
            for msg in history[-5:]:
                if msg['sender'] == 'user':
                    messages.append({"role": "user", "content": msg['text']})
                elif msg['sender'] == 'byte':
                    messages.append({"role": "assistant", "content": msg['text']})
                    
            if kb_results:
                context += "\nContexto relevante sobre Plubot:\n"
                for result in kb_results[:2]:
                    context += f"- {result['question']}: {result['answer']}\n"
                
                enhanced_message = f"{user_message}\n\n[NO MENCIONES ESTO: {context}]"
            else:
                enhanced_message = user_message

            messages.append({"role": "user", "content": enhanced_message})
            
            cache_key = user_message.strip().lower()
            cached_response = get_from_cache('byte_embajador', cache_key)
            
            if cached_response:
                logger.info(f"Respuesta de caché para Byte Embajador: {cached_response}")
                response = cached_response
            else:
                response = call_grok(messages, max_tokens=100, temperature=0.5)
                logger.info(f"Respuesta de API para Byte Embajador: {response}")
                store_in_cache('byte_embajador', cache_key, response)

        sentiment = analyze_sentiment(response)

        return jsonify({
            'message': response,
            'sentiment': sentiment
        })
    except Exception as e:
        logger.error(f"Error en /api/byte-embajador: {str(e)}")
        return jsonify({'error': f"Error: {str(e)}"}), 500

# Funciones auxiliares para caché y análisis de sentimiento
def analyze_sentiment(text):
    text_lower = text.lower()
    if any(word in text_lower for word in ['error', 'problema', 'fallo']):
        return 'sad'
    elif any(word in text_lower for word in ['excelente', 'perfecto', 'genial']):
        return 'happy'
    elif any(word in text_lower for word in ['cuidado', 'precaución']) and 'atención al cliente' not in text_lower:
        return 'warning'
    return 'normal'

_response_cache = {}

def get_from_cache(assistant_type, key):
    if assistant_type not in _response_cache:
        return None
    return _response_cache[assistant_type].get(key)

def store_in_cache(assistant_type, key, value, max_items=1000):
    if assistant_type not in _response_cache:
        _response_cache[assistant_type] = {}
    
    if len(_response_cache[assistant_type]) >= max_items:
        oldest_key = next(iter(_response_cache[assistant_type]))
        del _response_cache[assistant_type][oldest_key]
    
    _response_cache[assistant_type][key] = value

# Endpoint para cargar información a la base de conocimiento
@grok_bp.route('/knowledge/add', methods=['POST'])
def add_knowledge():
    data = request.get_json()
    if not all(key in data for key in ['category', 'question', 'answer', 'keywords']):
        return jsonify({'error': 'Faltan campos requeridos'}), 400
    
    try:
        kb.add_item(
            category=data['category'],
            question=data['question'],
            answer=data['answer'],
            keywords=data['keywords']
        )
        return jsonify({'success': True, 'message': 'Conocimiento agregado correctamente'})
    except Exception as e:
        logger.error(f"Error al agregar conocimiento: {str(e)}")
        return jsonify({'error': f"Error: {str(e)}"}), 500

# Endpoint para cargar conocimiento en lote
@grok_bp.route('/knowledge/bulk-add', methods=['POST'])
def bulk_add_knowledge():
    data = request.get_json()
    if not 'items' in data or not isinstance(data['items'], list):
        return jsonify({'error': 'Formato incorrecto. Se requiere una lista de items'}), 400
    
    try:
        added = 0
        for item in data['items']:
            if all(key in item for key in ['category', 'question', 'answer', 'keywords']):
                kb.add_item(
                    category=item['category'],
                    question=item['question'],
                    answer=item['answer'],
                    keywords=item['keywords']
                )
                added += 1
        
        return jsonify({
            'success': True, 
            'message': f'Se agregaron {added} de {len(data["items"])} elementos de conocimiento'
        })
    except Exception as e:
        logger.error(f"Error al agregar conocimiento en lote: {str(e)}")
        return jsonify({'error': f"Error: {str(e)}"}), 500

# Endpoint para consultar la base de conocimiento por categoría
@grok_bp.route('/knowledge/category/<category>', methods=['GET'])
def get_knowledge_by_category(category):
    try:
        items = kb.get_by_category(category)
        return jsonify({'items': items})
    except Exception as e:
        logger.error(f"Error al consultar conocimiento por categoría: {str(e)}")
        return jsonify({'error': f"Error: {str(e)}"}), 500