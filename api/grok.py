from flask import Blueprint, jsonify, request
from services.grok_service import call_grok
import logging

grok_bp = Blueprint('grok', __name__)
logger = logging.getLogger(__name__)

@grok_bp.route('', methods=['POST'])
def grok_api():
    data = request.get_json()
    user_message = data.get('message', '')
    history = data.get('history', [])
    if not user_message:
        return jsonify({'error': 'No se proporcionó mensaje'}), 400
    messages = [
        {"role": "system", "content": "Eres Plubot de Plubot Web. Responde amigable, breve y con tono alegre (máx. 2-3 frases). Usa emojis si aplica."}
    ] + history + [{"role": "user", "content": user_message}]
    try:
        response = call_grok(messages, max_tokens=50)
        logger.info(f"Respuesta de Grok: {response}")
        return jsonify({'response': response})
    except Exception as e:
        logger.error(f"Error en /api/grok: {str(e)}")
        return jsonify({'error': f"Error: {str(e)}"}), 500