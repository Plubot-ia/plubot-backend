import logging
from typing import Any

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import jwt_required

from services.grok_service import analyze_emotion, call_grok
from utils.knowledge_base import (
    add_knowledge_item,
    search_knowledge_base,
)
from utils.knowledge_base import (
    get_knowledge_by_category as get_kb_by_category,
)

grok_bp = Blueprint("grok", __name__)
logger = logging.getLogger(__name__)

@grok_bp.route("/emotion-detect", methods=["POST"])
@jwt_required()
def emotion_detect_route() -> Response:
    """API endpoint to detect emotion from a given text."""
    data = request.get_json()
    text = data.get("text")

    if not text:
        return jsonify({"error": "Text for analysis is required."}), 400

    try:
        detected_emotion = analyze_emotion(text)
        return jsonify({"emotion": detected_emotion})
    except Exception:
        logger.exception("Error during emotion detection")
        return jsonify({"error": "An error occurred during emotion detection."}), 500





# BYTE ASSISTANT
@grok_bp.route("/byte-assistant", methods=["POST"])
def byte_assistant() -> Response:
    data = request.get_json()
    user_message = data.get("message", "")
    history = data.get("history", [])
    if not user_message:
        return jsonify({"error": "No se proporcionó mensaje"}), 400

    # Prompt optimizado para respuestas cortas
    messages = [
        {
            "role": "system",
            "content": (
                "Eres Byte, un asistente de IA especializado en flujos de conversación para "
                "Plubots. Conoces diseño de flujos, buenas prácticas para chatbots, "
                "conexiones entre nodos y detección de problemas (ciclos, nodos huérfanos, "
                "callejones sin salida). Responde en 1-2 frases (máx. 50 palabras) con un "
                "tono amigable, técnico y metáforas de circuitos. Incluye una sugerencia "
                "práctica breve solo si es relevante. Evita listas largas o explicaciones "
                "detalladas."
            ),
        }
    ]

    # Añadir historial
    for msg in history:
        if msg["sender"] == "user":
            messages.append({"role": "user", "content": msg["text"]})
        elif msg["sender"] == "byte":
            messages.append({"role": "assistant", "content": msg["text"]})

    # Añadir mensaje actual
    messages.append({"role": "user", "content": user_message})

    try:
        # Implementar caché
        cache_key = user_message.strip().lower()
        cached_response = get_from_cache("byte_assistant", cache_key)

        if cached_response:
            logger.info("Respuesta de caché para Byte: %s", cached_response)
            response = cached_response
        else:
            response = call_grok(messages, max_tokens=100, temperature=0.5)
            logger.info("Respuesta de Byte (API): %s", response)
            # Guardar en caché
            store_in_cache("byte_assistant", cache_key, response)

        # Análisis básico de sentimiento
        sentiment = analyze_sentiment(response)

        return jsonify({"message": response, "sentiment": sentiment})
    except Exception:
        logger.exception("Error in /api/byte-assistant")
        return jsonify({"error": "Error processing request"}), 500


@grok_bp.route("/byte-embajador", methods=["POST"])
def byte_embajador() -> Response:
    """API endpoint to get a response from Grok based on user input and knowledge base."""
    try:
        data = request.get_json()
        user_input = data.get("message")

        if not user_input:
            return jsonify({"error": "User message is required."}), 400

        knowledge_results: list[dict[str, Any]] = search_knowledge_base(
            query=user_input
        )

        system_prompt = (
            "Eres Byte Embajador, una IA experta en marketing y publicidad. "
            "Tu tarea es responder preguntas y ofrecer insights basados "
            "en la base de conocimiento. "
            "Utiliza la información proporcionada para dar respuestas precisas y útiles. "
            "Si no encuentras información relevante, ofrece una respuesta general basada en tu "
            "conocimiento. Responde siempre en el idioma del usuario."
        )

        context = "Información de la base de conocimiento:\n"
        if knowledge_results:
            knowledge_text = " ".join(
                f"Q: {item['question']} A: {item['answer']}" for item in knowledge_results
            )
            prompt = (
                f"Basado en este conocimiento: '{knowledge_text}', "
                f"responde la siguiente pregunta: '{user_input}'"
            )
            context += prompt

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{context}\nPregunta del usuario: {user_input}"},
        ]

        grok_response = call_grok(messages, max_tokens=2048, temperature=0.7)
        return jsonify({"response": grok_response})

    except Exception as e:
        logger.exception("Error al llamar a Grok en Byte Embajador")
        return jsonify({"error": str(e)}), 500


@grok_bp.route("/ai-node", methods=["POST"])
def ai_node() -> Response:
    data: dict[str, Any] = request.get_json()
    prompt: str = data.get("prompt", "")
    temperature: float = data.get("temperature", 0.7)
    max_tokens: int = data.get("maxTokens", 150)
    system_message: str = data.get("systemMessage", "")
    temperature = data.get("temperature", 0.7)
    max_tokens = data.get("maxTokens", 150)
    system_message = data.get("systemMessage", "")

    if not prompt and not system_message:
        return jsonify({"error": "No se proporcionó prompt ni mensaje de sistema"}), 400

    messages: list[dict[str, str]] = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})

    try:
        response = call_grok(messages, max_tokens=max_tokens, temperature=temperature)
        logger.info("Respuesta de Grok para AiNode: %s", response)
        return jsonify({"response": response})
    except Exception:
        logger.exception("Error in /api/ai-node")
        return jsonify({"error": "Error processing request"}), 500

# Funciones auxiliares para caché y análisis de sentimiento
def analyze_sentiment(text: str) -> str:
    text_lower = text.lower()
    if any(word in text_lower for word in ["error", "problema", "fallo"]):
        return "sad"
    if any(word in text_lower for word in ["excelente", "perfecto", "genial"]):
        return "happy"
    if (
        any(word in text_lower for word in ["cuidado", "precaución"])
        and "atención al cliente" not in text_lower
    ):
        return "warning"
    return "normal"

_response_cache: dict[str, dict[str, str]] = {}

def get_from_cache(assistant_type: str, key: str) -> str | None:
    if assistant_type not in _response_cache:
        return None
    return _response_cache[assistant_type].get(key)

def store_in_cache(
    assistant_type: str, key: str, value: str, max_items: int = 1000
) -> None:
    if assistant_type not in _response_cache:
        _response_cache[assistant_type] = {}

    if len(_response_cache[assistant_type]) >= max_items:
        oldest_key = next(iter(_response_cache[assistant_type]))
        _response_cache[assistant_type].pop(oldest_key)

    _response_cache[assistant_type][key] = value

# Endpoint para cargar información a la base de conocimiento
@grok_bp.route("/knowledge/add", methods=["POST"])
def add_knowledge() -> Response:
    data = request.get_json()
    if not all(key in data for key in ["category", "question", "answer", "keywords"]):
        return jsonify({"error": "Faltan campos requeridos"}), 400

    try:
        add_knowledge_item(
            category=data["category"],
            question=data["question"],
            answer=data["answer"],
            keywords=data["keywords"],
        )
        return jsonify({"success": True, "message": "Conocimiento agregado correctamente"})
    except Exception:
        logger.exception("Error al agregar conocimiento")
        return jsonify({"error": "Error processing request"}), 500

# Endpoint para cargar conocimiento en lote
@grok_bp.route("/knowledge/bulk-add", methods=["POST"])
def bulk_add_knowledge() -> Response:
    data = request.get_json()
    if "items" not in data or not isinstance(data["items"], list):
        return jsonify({"error": "Formato incorrecto. Se requiere una lista de items"}), 400

    try:
        added = 0
        for item in data["items"]:
            if all(key in item for key in ["category", "question", "answer", "keywords"]):
                add_knowledge_item(
                    category=item["category"],
                    question=item["question"],
                    answer=item["answer"],
                    keywords=item["keywords"],
                )
                added += 1

        message = (
            f"Se agregaron {added} de {len(data['items'])} elementos de conocimiento"
        )
        return jsonify(
            {
                "success": True,
                "message": message,
            }
        )
    except Exception:
        logger.exception("Error al agregar conocimiento en lote")
        return jsonify({"error": "Error processing request"}), 500

# Endpoint para consultar la base de conocimiento por categoría
@grok_bp.route("/knowledge/category/<category>", methods=["GET"])
def get_knowledge_by_category(category: str) -> Response:
    try:
        items = get_kb_by_category(category)
        return jsonify({"items": items})
    except Exception:
        logger.exception("Error al consultar conocimiento por categoría")
        return jsonify({"error": "Error processing request"}), 500
