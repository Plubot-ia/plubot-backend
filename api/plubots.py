"""API endpoints for Plubot management."""
from __future__ import annotations

from contextlib import suppress
import json
import logging
import time
from typing import TYPE_CHECKING, Any
import uuid

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from pydantic import BaseModel, Field, ValidationError, validator
from sqlalchemy import or_

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from celery_tasks import process_pdf_async

from config import settings
from config.settings import get_session
from models.flow import Flow
from models.flow_edge import FlowEdge
from models.plubot import Plubot
from models.template import Template
from models.user import User
from services.grok_service import call_grok
from utils.helpers import parse_menu_to_flows

plubots_bp = Blueprint("plubots", __name__)
logger = logging.getLogger(__name__)

# --- Data Transfer Objects (DTOs) and Payloads ---

class FlowPayload(BaseModel):
    """Payload for a single flow node."""
    user_message: str
    bot_response: str
    intent: str = "general"
    condition: str = ""
    position_x: float | None = None
    position_y: float | None = None

class EdgePayload(BaseModel):
    """Payload for a single edge connecting flows."""
    source: str
    target: str

class PowerConfigPayload(BaseModel):
    """Payload for power configurations."""
    google_sheets: dict[str, Any] | None = None
    # Add other power configs as needed

class PlubotCreatePayload(BaseModel):
    """Payload for creating a new Plubot."""
    name: str
    tone: str = "amigable"
    purpose: str = "ayudar a los clientes"
    color: str | None = None
    powers: list[str] = []
    whatsapp_number: str | None = None
    business_info: str | None = None
    pdf_url: str | None = None
    image_url: str | None = None
    flows: list[FlowPayload] = Field(default_factory=list)
    edges: list[EdgePayload] = Field(default_factory=list)
    template_id: int | None = None
    menu_json: str | None = None
    power_config: PowerConfigPayload = Field(default_factory=PowerConfigPayload)
    plan_type: str = "free"
    avatar: str | None = None
    menu_options: list[dict[str, Any]] = []
    response_limit: int = 100
    conversation_count: int = 0
    message_count: int = 0
    is_webchat_enabled: bool = True

    @validator("powers")
    def powers_must_be_list(cls, v: object) -> list[str]:  # noqa: N805
        """Ensure powers is a list."""
        if not isinstance(v, list):
            msg = "Los poderes deben ser una lista"
            raise TypeError(msg)
        return v

class PlubotUpdatePayload(BaseModel):
    """Payload for updating an existing Plubot. All fields are optional."""

    name: str | None = None
    tone: str | None = None
    purpose: str | None = None
    color: str | None = None
    powers: list[str] | None = None
    whatsapp_number: str | None = None
    business_info: str | None = None
    pdf_url: str | None = None
    image_url: str | None = None
    flows: list[FlowPayload] | None = None
    edges: list[EdgePayload] | None = None
    initial_message: str | None = None
    power_config: PowerConfigPayload | None = None
    plan_type: str | None = None
    avatar: str | None = None
    menu_options: list[dict[str, Any]] | None = None
    response_limit: int | None = None
    conversation_count: int | None = None
    message_count: int | None = None
    is_webchat_enabled: bool | None = None

    @validator("powers", pre=True)
    def powers_must_be_list(cls, v: object) -> list[str] | None:  # noqa: N805
        """Ensure powers is a list if provided."""
        if v is not None and not isinstance(v, list):
            msg = "Los poderes deben ser una lista"
            raise TypeError(msg)
        return v


# --- Helper Functions ---

def _plubot_to_dict(plubot: Plubot) -> dict[str, Any]:
    """Serializes a Plubot SQLAlchemy object to a dictionary."""
    return {
        "id": plubot.id,
        "name": plubot.name,
        "tone": plubot.tone,
        "purpose": plubot.purpose,
        "color": plubot.color,
        "powers": plubot.powers,
        "whatsapp_number": plubot.whatsapp_number,
        "initial_message": plubot.initial_message,
        "business_info": plubot.business_info,
        "pdf_url": plubot.pdf_url,
        "image_url": plubot.image_url,
        "created_at": plubot.created_at.isoformat() if plubot.created_at else None,
        "updated_at": plubot.updated_at.isoformat() if plubot.updated_at else None,
        "plan_type": plubot.plan_type,
        "avatar": plubot.avatar,
        "menu_options": plubot.menu_options,
        "response_limit": plubot.response_limit,
        "conversation_count": plubot.conversation_count,
        "message_count": plubot.message_count,
        "is_webchat_enabled": plubot.is_webchat_enabled,
        "power_config": plubot.power_config,
        "public_id": plubot.public_id,
    }


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

def _validate_flows(flows_data: list[FlowPayload]) -> None:
    """Validate a list of flows for empty or duplicate messages."""
    user_messages = set()
    for index, flow_payload in enumerate(flows_data):
        user_msg = flow_payload.user_message.strip().lower()
        bot_resp = flow_payload.bot_response.strip()
        if not user_msg or not bot_resp:
            msg = f"El flujo en la posición {index} tiene mensajes vacíos."
            raise ValueError(msg)
        if user_msg in user_messages:
            msg = f'El mensaje de usuario "{user_msg}" en la posición {index} está duplicado.'
            raise ValueError(msg)
        user_messages.add(user_msg)


def _create_plubot_instance(
    payload: PlubotCreatePayload, user_id: int, initial_message: str
) -> Plubot:
    """Create a Plubot instance from a payload."""
    return Plubot(
        user_id=user_id,
        name=payload.name,
        tone=payload.tone,
        purpose=payload.purpose,
        initial_message=initial_message,
        whatsapp_number=payload.whatsapp_number,
        business_info=payload.business_info,
        pdf_url=payload.pdf_url,
        image_url=payload.image_url,
        color=payload.color,
        powers=payload.powers,
        plan_type=payload.plan_type,
        avatar=payload.avatar,
        menu_options=payload.menu_options,
        response_limit=payload.response_limit,
        conversation_count=payload.conversation_count,
        message_count=payload.message_count,
        is_webchat_enabled=payload.is_webchat_enabled,
        power_config=payload.power_config.model_dump(),
    )


def _save_flows_and_edges(
    session: Session,
    plubot_id: int,
    flows_to_save: list[dict[str, Any]],
    edges_raw: list[EdgePayload],
) -> None:
    """Save flows and edges to the database."""
    flow_id_map = {}
    for index, flow_data in enumerate(flows_to_save):
        if flow_data.get("user_message") and flow_data.get("bot_response"):
            flow_entry = Flow(
                chatbot_id=plubot_id,
                user_message=flow_data["user_message"],
                bot_response=flow_data["bot_response"],
                position=index,
                intent=flow_data.get("intent", "general"),
                condition=flow_data.get("condition", ""),
                position_x=flow_data.get("position_x"),
                position_y=flow_data.get("position_y"),
            )
            session.add(flow_entry)
            session.flush()
            # Assuming the frontend provides a temporary ID for mapping
            # This part might need adjustment based on frontend implementation
            flow_id_map[str(index)] = flow_entry.id

    for edge in edges_raw:
        source_id = flow_id_map.get(edge.source)
        target_id = flow_id_map.get(edge.target)
        if source_id and target_id:
            edge_entry = FlowEdge(
                chatbot_id=plubot_id,
                source_flow_id=source_id,
                target_flow_id=target_id,
                condition="",
            )
            session.add(edge_entry)


def _replace_flows_and_edges(
    session: Session,
    plubot_id: int,
    flows_data: list[FlowPayload],
    edges_data: list[EdgePayload],
) -> None:
    """Delete all existing flows and edges and create new ones."""
    logger.debug("Replacing flows and edges for plubot_id=%s", plubot_id)
    session.query(FlowEdge).filter_by(chatbot_id=plubot_id).delete()
    session.query(Flow).filter_by(chatbot_id=plubot_id).delete()
    session.flush()

    flows_to_save = [f.model_dump() for f in flows_data]
    _save_flows_and_edges(session, plubot_id, flows_to_save, edges_data)


@plubots_bp.route("/create", methods=["POST"])
@jwt_required()
def create_bot() -> tuple[Response, int]:
    """Create a new Plubot, including its flows and configurations."""
    user_id = get_jwt_identity()
    json_data = request.get_json()
    if not json_data:
        return jsonify({"status": "error", "message": "No se proporcionaron datos"}), 400

    try:
        payload = PlubotCreatePayload(**json_data)
        _validate_flows(payload.flows)
    except (ValidationError, ValueError) as e:
        logger.warning("Error de validación al crear Plubot: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 400

    with get_session() as session:
        try:
            flows_to_save = [f.model_dump() for f in payload.flows]
            tone, purpose = payload.tone, payload.purpose

            if payload.template_id:
                template = session.get(Template, payload.template_id)
                if template:
                    tone = template.tone
                    purpose = template.purpose
                    template_flows = json.loads(template.flows)
                    flows_to_save = template_flows + flows_to_save

            if payload.menu_json:
                menu_flows = parse_menu_to_flows(payload.menu_json)
                flows_to_save.extend(menu_flows)

            system_message = (
                f"Eres un plubot {tone} llamado '{payload.name}'. "
                f"Tu propósito es {purpose}."
            )
            if payload.business_info:
                system_message += f"\nNegocio: {payload.business_info}"
            if payload.pdf_url:
                system_message += "\nContenido del PDF será añadido tras procesar."

            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": "Dame un mensaje de bienvenida."},
            ]
            initial_message = call_grok(messages, max_tokens=100)

            plubot = _create_plubot_instance(payload, user_id, initial_message)
            session.add(plubot)
            session.flush()
            plubot_id = plubot.id

            if payload.power_config.google_sheets and payload.power_config.google_sheets.get(
                "credentials"
            ):
                user = session.get(User, user_id)
                if not user:
                    error_message = f"Usuario con ID {user_id} no encontrado"
                    raise ValueError(error_message)  # noqa: TRY301
                user.google_sheets_credentials = payload.power_config.google_sheets[
                    "credentials"
                ]

            _save_flows_and_edges(session, plubot_id, flows_to_save, payload.edges)
            session.commit()

            if payload.pdf_url:
                process_pdf_async.delay(plubot_id, payload.pdf_url)

            return jsonify(
                {
                    "status": "success",
                    "message": f"Plubot '{payload.name}' creado con éxito. ID: {plubot_id}.",
                    "plubot": _plubot_to_dict(plubot),
                }
            )

        except Exception:
            logger.exception("Error al crear plubot")
            session.rollback()
            return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

class MenuOptionPayload(BaseModel):
    """Payload for a single menu option."""
    label: str
    action: str

class DespiertoCreatePayload(BaseModel):
    """Payload for creating a 'despierto' Plubot."""
    name: str
    tone: str = "neutral"
    purpose: str = "ayudar a los clientes"
    avatar: str = "default_avatar.png"
    menu_options: list[MenuOptionPayload] = Field(default_factory=list)
    color: str | None = None

    @validator("tone")
    def tone_must_be_valid(cls, v: str) -> str:  # noqa: N805
        """Validate that the tone is one of the predefined personalities."""
        if v.lower() not in PERSONALITIES:
            msg = f"Tono inválido. Opciones válidas: {', '.join(PERSONALITIES.keys())}"
            raise ValueError(msg)
        return v.lower()

    @validator("menu_options")
    def menu_options_must_be_valid(cls, v: list[MenuOptionPayload]) -> list[MenuOptionPayload]:  # noqa: N805
        """Validate menu options constraints."""
        if len(v) > 3:
            msg = "Máximo 3 opciones de menú permitidas"
            raise ValueError(msg)
        return v

@plubots_bp.route("/create_despierto", methods=["POST"])
@jwt_required()
def create_despierto_bot() -> tuple[Response, int]:
    """Crea un nuevo plubot de tipo 'despierto' con configuración inicial."""
    json_data = request.get_json()
    if not json_data:
        return jsonify({"status": "error", "message": "No se proporcionaron datos"}), 400

    try:
        payload = DespiertoCreatePayload(**json_data)
    except ValidationError as e:
        logger.warning("Error de validación al crear Plubot Despierto: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 400

    user_id = get_jwt_identity()

    with get_session() as session:
        try:
            initial_message = PERSONALITIES[payload.tone]["welcome"]
            color = payload.color or PERSONALITIES.get(payload.tone, {}).get("color", "#D1D5DB")

            plubot = Plubot(
                user_id=user_id,
                name=payload.name,
                tone=payload.tone,
                purpose=payload.purpose,
                initial_message=initial_message,
                plan_type="free",
                avatar=payload.avatar,
                menu_options=[opt.model_dump() for opt in payload.menu_options],
                response_limit=100,
                conversation_count=0,
                message_count=0,
                is_webchat_enabled=True,
                power_config={},
                color=color,
            )
            session.add(plubot)
            session.flush()
            plubot_id = plubot.id

            for index, option in enumerate(payload.menu_options):
                flow_entry = Flow(
                    chatbot_id=plubot_id,
                    user_message=option.label.lower(),
                    bot_response=(
                        f"Has seleccionado {option.label}. "
                        f"¿Cómo puedo ayudarte con esto?"
                    ),
                    position=index,
                    intent="menu_option",
                    condition="",
                    position_x=100.0 * index,
                    position_y=100.0,
                )
                session.add(flow_entry)

            session.commit()

            return jsonify(
                {
                    "status": "success",
                    "message": f"Plubot '{payload.name}' creado con éxito. ID: {plubot_id}.",
                    "plubot": _plubot_to_dict(plubot),
                }
            )
        except Exception:
            logger.exception("Error al crear plubot despierto")
            session.rollback()
            return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

@plubots_bp.route("/", methods=["GET"])
@jwt_required()
def get_plubots() -> tuple[Response, int]:
    """Retrieve all Plubots for the authenticated user."""
    user_id = get_jwt_identity()
    with get_session() as session:
        try:
            plubots = session.query(Plubot).filter_by(user_id=user_id).all()
            plubots_data = [_plubot_to_dict(p) for p in plubots]
            return jsonify(plubots_data)
        except Exception:
            logger.exception("Error al obtener plubots")
            return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

@plubots_bp.route("/<int:plubot_id>", methods=["GET"])
@jwt_required()
def get_plubot(plubot_id: int) -> tuple[Response, int]:
    """Retrieve a single Plubot by its ID."""
    user_id = get_jwt_identity()
    with get_session() as session:
        try:
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                response = {"status": "error", "message": "Plubot no encontrado o no autorizado"}
                return jsonify(response), 404

            return jsonify(_plubot_to_dict(plubot))
        except Exception:
            logger.exception("Error al obtener el plubot")
            return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

@plubots_bp.route("/list", methods=["GET", "OPTIONS"])
@jwt_required()
def list_bots() -> tuple[Response, int]:
    """List all plubots for the current user (legacy support)."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"})

    user_id = get_jwt_identity()
    with get_session() as session:
        try:
            plubots = session.query(Plubot).filter_by(user_id=user_id).all()
            plubots_data = [_plubot_to_dict(bot) for bot in plubots]
            return jsonify({"plubots": plubots_data})
        except Exception:
            logger.exception("Error al listar plubots")
            return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

@plubots_bp.route("/messages/<int:plubot_id>/<string:context>", methods=["GET"])
@jwt_required()
def get_contextual_message(plubot_id: int, context: str) -> tuple[Response, int]:
    """Get a contextual message for a plubot based on its tone."""
    user_id = get_jwt_identity()
    if context not in VALID_CONTEXTS:
        return jsonify(
            {
                "status": "error",
                "message": f"Contexto inválido. Opciones válidas: {', '.join(VALID_CONTEXTS)}",
            }
        ), 400

    with get_session() as session:
        try:
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                return jsonify(
                    {"status": "error", "message": "Plubot no encontrado o no tienes permisos"}
                ), 404

            tone = plubot.tone.lower()
            if tone not in PERSONALITIES:
                logger.warning("Plubot %s tiene tono inválido: %s", plubot_id, tone)
                tone = "neutral"

            message = PERSONALITIES[tone].get(context)

            return jsonify(
                {"status": "success", "message": message, "tone": tone, "context": context}
            )
        except Exception:
            logger.exception("Error al obtener mensaje contextual")
            return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

@plubots_bp.route("/update/<int:plubot_id>", methods=["PUT", "OPTIONS"])
@jwt_required()
def update_bot(plubot_id: int) -> tuple[Response, int]:
    """Update an existing Plubot's attributes, flows, and edges."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"})

    user_id = get_jwt_identity()
    json_data = request.get_json()
    if not json_data:
        return jsonify({"status": "error", "message": "No se proporcionaron datos"}), 400

    try:
        payload = PlubotUpdatePayload(**json_data)
        if payload.flows is not None:
            _validate_flows(payload.flows)
    except (ValidationError, ValueError) as e:
        logger.warning("Error de validación al actualizar Plubot: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 400

    with get_session() as session:
        try:
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                response = {"status": "error", "message": "Plubot no encontrado o no autorizado"}
                return jsonify(response), 404

            # Update plubot fields from payload if they are provided
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                if key not in ["flows", "edges"]:
                    setattr(plubot, key, value)

            # If flows or edges are part of the payload, replace them completely.
            if payload.flows is not None and payload.edges is not None:
                _replace_flows_and_edges(session, plubot_id, payload.flows, payload.edges)

            session.commit()
            return jsonify(
                {
                    "status": "success",
                    "message": "Plubot actualizado con éxito",
                    "plubot": _plubot_to_dict(plubot),
                }
            )

        except Exception:
            session.rollback()
            logger.exception("Error al actualizar el plubot")
            return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

@plubots_bp.route("/delete/<int:plubot_id>", methods=["DELETE"])
@jwt_required()
def delete_bot(plubot_id: int) -> tuple[Response, int]:
    user_id = get_jwt_identity()
    with get_session() as session:
        try:
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                response = {
                    "status": "error",
                    "message": "Plubot no encontrado o no tienes permisos",
                }
                return jsonify(response), 404

            existing_flows = session.query(Flow).filter_by(chatbot_id=plubot_id).all()
            existing_flow_ids = [flow.id for flow in existing_flows]
            if existing_flow_ids:
                session.query(FlowEdge).filter(
                    or_(
                        FlowEdge.source_flow_id.in_(existing_flow_ids),
                        FlowEdge.target_flow_id.in_(existing_flow_ids),
                    )
                ).delete(synchronize_session=False)
            session.query(Flow).filter_by(chatbot_id=plubot_id).delete(synchronize_session=False)
            session.delete(plubot)
            session.commit()
            logger.info(
                "Plubot con id=%s eliminado exitosamente por user_id=%s",
                plubot_id,
                user_id,
            )
            return jsonify({"status": "success", "message": "Plubot eliminado con éxito"})

        except Exception:
            logger.exception("Error al eliminar plubot con id=%s", plubot_id)
            session.rollback()
            return jsonify({"status": "error", "message": "Error interno del servidor"}), 500


@plubots_bp.route("/plubots/<int:plubot_id>/embed", methods=["POST"])
@jwt_required()
def create_embeddable_plubot(plubot_id: int) -> Response:
    """Generates a public ID for a plubot to make it embeddable."""
    user_id = get_jwt_identity()
    try:
        with get_session() as session:
            plubot = (
                session.query(Plubot)
                .filter_by(id=plubot_id, user_id=user_id)
                .first()
            )
            if not plubot:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Plubot no encontrado o no tienes permisos.",
                        }
                    ),
                    404,
                )

            if not plubot.public_id:
                plubot.public_id = uuid.uuid4().hex
                session.add(plubot)
                session.commit()
                session.refresh(plubot)

            frontend_url = settings.FRONTEND_URL
            direct_link = f"{frontend_url}/chat/{plubot.public_id}"

            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Plubot preparado para ser embebido.",
                        "data": {
                            "publicId": plubot.public_id,
                            "directLink": direct_link,
                        },
                    }
                ),
                200,
            )
    except Exception:
        logger.exception(
            "Error al crear la versión embebible del plubot_id=%s", plubot_id
        )
        return (
            jsonify({"status": "error", "message": "Error interno del servidor."}),
            500,
        )

@plubots_bp.route("/clone/<int:plubot_id>", methods=["POST", "OPTIONS"])
@jwt_required()
def clone_bot(plubot_id: int) -> tuple[Response, int]:
    """Clone an existing Plubot, including its flows and edges."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"})

    user_id = get_jwt_identity()
    with get_session() as session:
        try:
            original_plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not original_plubot:
                return jsonify({"status": "error", "message": "Plubot a clonar no encontrado"}), 404

            with session.begin_nested():
                new_plubot = Plubot(
                    user_id=user_id,
                    name=f"{original_plubot.name} (Copia)",
                    tone=original_plubot.tone,
                    purpose=original_plubot.purpose,
                    initial_message=original_plubot.initial_message,
                    plan_type=original_plubot.plan_type,
                    avatar=original_plubot.avatar,
                    menu_options=original_plubot.menu_options,
                    response_limit=original_plubot.response_limit,
                    conversation_count=0,
                    message_count=0,
                    is_webchat_enabled=original_plubot.is_webchat_enabled,
                    power_config=original_plubot.power_config,
                    color=original_plubot.color,
                )
                session.add(new_plubot)
                session.flush()

                original_flows = session.query(Flow).filter_by(chatbot_id=original_plubot.id).all()
                if original_flows:
                    flow_map = {}
                    new_flows_to_add = [
                        Flow(
                            chatbot_id=new_plubot.id,
                            user_message=flow.user_message,
                            bot_response=flow.bot_response,
                            position=flow.position,
                            intent=flow.intent,
                            condition=flow.condition,
                            position_x=flow.position_x,
                            position_y=flow.position_y,
                        )
                        for flow in original_flows
                    ]
                    session.add_all(new_flows_to_add)
                    session.flush()

                    for original, new in zip(
                        original_flows, new_flows_to_add, strict=True
                    ):
                        flow_map[original.id] = new.id

                    original_edges = (
                        session.query(FlowEdge)
                        .filter(FlowEdge.chatbot_id == original_plubot.id)
                        .all()
                    )
                    for edge in original_edges:
                        if (
                            source_id := flow_map.get(edge.source_flow_id)
                        ) and (target_id := flow_map.get(edge.target_flow_id)):
                            session.add(
                                FlowEdge(
                                    chatbot_id=new_plubot.id,
                                    source_flow_id=source_id,
                                    target_flow_id=target_id,
                                    condition=edge.condition,
                                )
                            )

            session.commit()
            logger.info("Plubot id=%s clonado a id=%s", plubot_id, new_plubot.id)
            return jsonify(
                {
                    "status": "success",
                    "message": "Plubot clonado con éxito",
                    "plubot": _plubot_to_dict(new_plubot),
                }
            )

        except Exception:
            logger.exception("Error al clonar plubot con id=%s", plubot_id)
            session.rollback()
            return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

def _serialize_public_flows(flows: list[Flow]) -> list[dict[str, Any]]:
    """Serialize flow data for public consumption."""
    return [
        {
            "position": flow.position,
            "intent": flow.intent,
            "user_message": flow.user_message,
            "bot_response": flow.bot_response,
            "position_x": flow.position_x,
            "position_y": flow.position_y,
            "condition": flow.condition,
            "actions": flow.actions,
        }
        for flow in flows
    ]

def _serialize_public_edges(
    edges: list[FlowEdge], flow_map: dict[int, str]
) -> list[dict[str, Any]]:
    """Serialize edge data for public consumption."""
    return [
        {
            "source": flow_map.get(edge.source_flow_id),
            "target": flow_map.get(edge.target_flow_id),
            "sourceHandle": edge.condition or None,
        }
        for edge in edges
    ]


@plubots_bp.route("/chat/<string:public_id>", methods=["GET"])
def get_public_bot(public_id: str) -> tuple[Response, int]:
    """Load public chatbot information for the webchat client."""
    with get_session() as session:
        try:
            plubot = session.query(Plubot).filter_by(public_id=public_id).first()

            if not plubot:
                return jsonify({"status": "error", "message": "Chatbot no encontrado"}), 404

            if not plubot.is_webchat_enabled:
                return (
                    jsonify({"status": "error", "message": "Este chatbot no está disponible"}),
                    403,
                )

            personality = plubot.tone or "servicial"
            personality_details = PERSONALITIES.get(personality, PERSONALITIES["servicial"])
            welcome_message = personality_details["welcome"]
            color = plubot.color or personality_details["color"]

            flows = (
                session.query(Flow)
                .filter_by(chatbot_id=plubot.id)
                .order_by(Flow.position)
                .all()
            )
            edges = session.query(FlowEdge).filter_by(chatbot_id=plubot.id).all()

            flow_id_to_position = {flow.id: str(flow.position) for flow in flows}

            return jsonify(
                {
                    "status": "success",
                    "data": {
                        "id": plubot.public_id,
                        "name": plubot.name,
                        "color": color,
                        "welcomeMessage": welcome_message,
                        "personality": personality,
                        "flows": _serialize_public_flows(flows),
                        "edges": _serialize_public_edges(edges, flow_id_to_position),
                    },
                }
            )

        except Exception:
            logger.exception(
                "Error al cargar plubot público con public_id=%s", public_id
            )
            return (
                jsonify({"status": "error", "message": "Error interno del servidor"}),
                500,
            )

def _get_start_flow(
    flows: list[Flow], edges: list[FlowEdge], flow_id_map: dict[int, Flow]
) -> Flow | None:
    """Busca el flujo de inicio o un sucesor válido."""
    logger.info("Buscando nodo de inicio")
    start_flows = [f for f in flows if f.intent == "start"]
    if not start_flows:
        logger.info("No se encontró nodo de inicio, buscando nodos de mensaje")
        message_flows = [f for f in flows if f.intent == "message"]
        if message_flows:
            logger.info("Usando primer nodo de mensaje: ID %s", message_flows[0].id)
            return message_flows[0]
        logger.warning("No se encontraron nodos de mensaje ni de inicio")
        return None

    start_flow = start_flows[0]
    logger.info("Nodo de inicio encontrado: ID %s", start_flow.id)

    edges_from_start = (e for e in edges if e.source_flow_id == start_flow.id)
    start_edge = next(edges_from_start, None)
    if not start_edge:
        logger.info("No se encontraron bordes desde el nodo de inicio, usando el nodo de inicio")
        return start_flow

    target_flow = flow_id_map.get(start_edge.target_flow_id)
    if target_flow:
        logger.info("Flujo destino desde inicio encontrado: ID %s", target_flow.id)
        return target_flow

    logger.warning("No se encontró flujo destino para el borde desde inicio %s", start_edge.id)
    return start_flow


def _find_next_flow_from_node(
    current_flow_id: int,
    user_message: str,
    edges: list[FlowEdge],
    flow_id_map: dict[int, Flow],
) -> Flow | None:
    """Encuentra el siguiente flujo a partir de un nodo y mensaje de usuario dados."""
    current_edges = [e for e in edges if e.source_flow_id == current_flow_id]
    if not current_edges:
        return None

    matching_edge = None
    for edge in current_edges:
        if edge.condition and user_message.lower() == edge.condition.lower():
            matching_edge = edge
            logger.info("Coincidencia exacta con condición del borde: %s", edge.condition)
            break
    if not matching_edge:
        for edge in current_edges:
            if edge.condition and user_message.lower() in edge.condition.lower():
                matching_edge = edge
                logger.info("Coincidencia parcial con condición del borde: %s", edge.condition)
                break
    if not matching_edge:
        matching_edge = current_edges[0]
        logger.info(
            "Usando primer borde por defecto: %s -> %s",
            matching_edge.source_flow_id,
            matching_edge.target_flow_id,
        )

    return flow_id_map.get(matching_edge.target_flow_id)


def _find_next_flow_globally(
    user_message: str,
    flows: list[Flow],
    edges: list[FlowEdge],
    flow_id_map: dict[int, Flow],
) -> Flow | None:
    """Busca un flujo que coincida con el mensaje del usuario o recurre al de inicio."""
    for flow in flows:
        if flow.user_message and user_message.lower() in flow.user_message.lower():
            logger.info("Encontrada coincidencia con flujo ID %s: '%s'", flow.id, flow.user_message)
            return flow

    return _get_start_flow(flows, edges, flow_id_map)


# --- Error Messages ---
CHAT_INVALID_ID_MSG = "ID de chatbot inválido"
CHAT_NOT_FOUND_MSG = "Chatbot no encontrado"
CHAT_NOT_ENABLED_MSG = "Este chatbot no está disponible"
CHAT_NO_MESSAGE_MSG = "Se requiere un mensaje"


# --- Chat Message Handling Helpers ---


class ChatError(Exception):
    """Base exception for chat handling errors."""

    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def _get_plubot_for_chat(session: Session, public_id: str) -> Plubot:
    """Load and validate a Plubot for a public chat, raising ChatError on failure."""
    try:
        plubot_id = int(public_id)
    except ValueError as e:
        logger.warning("ID de chatbot inválido: %s", public_id)
        raise ChatError(CHAT_INVALID_ID_MSG, 400) from e

    plubot = session.query(Plubot).filter(Plubot.id == plubot_id).first()
    if not plubot:
        logger.warning("Chatbot con ID %s no encontrado", plubot_id)
        raise ChatError(CHAT_NOT_FOUND_MSG, 404)

    if not plubot.is_webchat_enabled:
        logger.warning("Chatbot %s no tiene habilitado el webchat", plubot.id)
        raise ChatError(CHAT_NOT_ENABLED_MSG, 403)

    return plubot


def _determine_response_flow(
    current_flow_id: int | None,
    user_message: str,
    flows: list[Flow],
    edges: list[FlowEdge],
    flow_id_map: dict[int, Flow],
) -> Flow | None:
    """Determine the next flow based on the current state and user message."""
    next_flow = None
    if current_flow_id:
        next_flow = _find_next_flow_from_node(
            current_flow_id, user_message, edges, flow_id_map
        )
        current_flow = flow_id_map.get(current_flow_id)
        if not next_flow and current_flow and current_flow.intent == "end":
            logger.info("Nodo final alcanzado, reiniciando.")
            next_flow = _get_start_flow(flows, edges, flow_id_map)

    if not next_flow:
        next_flow = _find_next_flow_globally(
            user_message, flows, edges, flow_id_map
        )
    return next_flow


def _parse_chat_request() -> tuple[str, int | None, list]:
    """Parse and validate the incoming chat request data."""
    data = request.get_json()
    if not data or "message" not in data:
        raise ChatError(CHAT_NO_MESSAGE_MSG, 400)

    user_message = data["message"]
    current_flow_id = data.get("current_flow_id")
    conversation_history = data.get("conversation_history", [])
    return user_message, current_flow_id, conversation_history


def _build_response_payload(
    next_flow: Flow | None,
    edges: list[FlowEdge],
    flow_id_map: dict[int, Flow],
    conversation_history: list,
    user_message: str,
) -> dict[str, Any]:
    """Build the JSON payload for the chat response."""
    if next_flow:
        response_text = next_flow.bot_response
        next_flow_id = next_flow.id
        is_decision_node = next_flow.intent == "decision"
        options = []
        if is_decision_node:
            decision_edges = [e for e in edges if e.source_flow_id == next_flow.id]
            options = [
                {
                    "id": target_flow.id,
                    "label": edge.condition or "Opción",
                    "message": target_flow.user_message,
                }
                for edge in decision_edges
                if (target_flow := flow_id_map.get(edge.target_flow_id))
            ]
    else:
        logger.warning("No se encontró un flujo para responder al mensaje.")
        response_text = "Lo siento, no entiendo tu mensaje. ¿Puedes reformularlo?"
        next_flow_id = None
        options = []
        is_decision_node = False

    new_history = list(conversation_history)
    new_history.append({"role": "user", "message": user_message})
    new_history.append({"role": "bot", "message": response_text, "flow_id": next_flow_id})

    return {
        "status": "success",
        "response": response_text,
        "conversation_history": new_history,
        "current_flow_id": next_flow_id,
        "is_decision": is_decision_node,
        "options": options,
    }


# Endpoint público para manejar mensajes del chat (sin autenticación JWT)
@plubots_bp.route("/chat/<string:public_id>/message", methods=["POST"])
def handle_chat_message(public_id: str) -> tuple[Response, int]:
    """Maneja los mensajes entrantes del chat público de forma modular."""
    try:
        user_message, current_flow_id, conversation_history = _parse_chat_request()
        logger.info(
            "Msg: '%s', FlowID: %s, PublicID: %s",
            user_message,
            current_flow_id,
            public_id,
        )

        with get_session() as session:
            plubot = _get_plubot_for_chat(session, public_id)
            flows = session.query(Flow).filter(Flow.chatbot_id == plubot.id).all()
            edges = session.query(FlowEdge).filter(FlowEdge.chatbot_id == plubot.id).all()
            flow_id_map = {flow.id: flow for flow in flows}

            next_flow = _determine_response_flow(
                current_flow_id, user_message, flows, edges, flow_id_map
            )

            result = _build_response_payload(
                next_flow, edges, flow_id_map, conversation_history, user_message
            )

            plubot.message_count = (plubot.message_count or 0) + 1
            session.commit()

            return jsonify(result), 200

    except ChatError as e:
        return jsonify({"status": "error", "message": e.message}), e.status_code
    except Exception:
        logger.exception("Error fatal en handle_chat_message para public_id=%s", public_id)
        return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

def _get_flow_data(
    session: Session, plubot_id: int, plubot_name: str
) -> Response:
    """Recupera y formatea los datos de flujos y aristas para el frontend."""
    flows = session.query(Flow).filter_by(chatbot_id=plubot_id).all()
    edges = session.query(FlowEdge).filter_by(chatbot_id=plubot_id).all()
    logger.debug("Flows recuperados para plubot_id %s: %s", plubot_id, len(flows))

    nodes = [
        {
            "id": str(flow.id),
            "type": flow.intent or "message",
            "position": {"x": flow.position_x or 0, "y": flow.position_y or 0},
            "data": {"label": flow.user_message, "message": flow.bot_response},
        }
        for flow in flows
    ]

    formatted_edges = []
    for edge in edges:
        with suppress(Exception):  # Simplificado para brevedad
            source_id = str(edge.source_flow_id)
            target_id = str(edge.target_flow_id)
            label, source_handle, target_handle, edge_id, style = None, None, None, None, {}

            if edge.condition and "|||" in edge.condition:
                parts = edge.condition.split("|||")
                label = parts[0] or None
                try:
                    metadata = json.loads(parts[1])
                    source_handle = metadata.get("sourceHandle")
                    target_handle = metadata.get("targetHandle")
                    edge_id = metadata.get("edge_id")
                    style = metadata.get("style", {})
                except json.JSONDecodeError:
                    logger.warning("Error decodificando metadatos para la arista %s", edge.id)
                    label = edge.condition
            else:
                label = edge.condition

            if not edge_id:
                timestamp = int(time.time() * 1000)
                edge_id = f"edge-{source_id}-{target_id}-{timestamp}"

            formatted_edge = {
                "id": edge_id,
                "source": source_id,
                "target": target_id,
                "type": getattr(edge, "edge_type", "default"),
                "style": style,
            }
            if source_handle:
                formatted_edge["sourceHandle"] = source_handle
            if target_handle:
                formatted_edge["targetHandle"] = target_handle
            if label:
                formatted_edge["label"] = label

            formatted_edges.append(formatted_edge)

    return jsonify({
        "status": "success",
        "data": {"nodes": nodes, "edges": formatted_edges, "name": plubot_name},
    })

def _process_flow_nodes(
    session: Session, plubot_id: int, nodes_data: list
) -> dict[str, int]:
    """Procesa y guarda los nodos de flujo, devolviendo un mapa de IDs."""
    node_id_map = {}
    for node in nodes_data:
        flow = Flow(
            chatbot_id=plubot_id,
            user_message=node.get("data", {}).get("label", ""),
            bot_response=node.get("data", {}).get("message", ""),
            intent=node.get("type", "message"),
            position_x=node.get("position", {}).get("x"),
            position_y=node.get("position", {}).get("y"),
            node_id=node.get("id"),
        )
        session.add(flow)
        session.flush()  # Para obtener el ID asignado por la BD
        node_id_map[node.get("id")] = flow.id
    return node_id_map

def _process_flow_edges(
    session: Session, plubot_id: int, edges_data: list, node_id_map: dict
) -> None:
    """Procesa y guarda las aristas de flujo."""
    for edge in edges_data:
        source_id = node_id_map.get(edge.get("source"))
        target_id = node_id_map.get(edge.get("target"))

        if not source_id or not target_id:
            logger.warning("Omitiendo arista con IDs no encontrados: %s", edge)
            continue

        metadata = {
            "source_original": edge.get("source"),
            "target_original": edge.get("target"),
            "sourceHandle": edge.get("sourceHandle"),
            "targetHandle": edge.get("targetHandle"),
            "edge_id": edge.get("id"),
            "style": edge.get("style", {}),
        }
        condition = f"{edge.get('label', '')}|||{json.dumps(metadata)}"

        flow_edge = FlowEdge(
            chatbot_id=plubot_id,
            source_flow_id=source_id,
            target_flow_id=target_id,
            condition=condition,
            edge_type=edge.get("type", "default"),
        )
        session.add(flow_edge)

@plubots_bp.route("/<int:plubot_id>/flow", methods=["GET", "POST"])
@jwt_required()
def handle_flow(plubot_id: int) -> Response:
    """Endpoint orquestador para manejar la carga y guardado de flujos."""
    user_id = get_jwt_identity()
    try:
        with get_session() as session:
            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                return jsonify({
                    "status": "error",
                    "message": "Plubot no encontrado o no tienes permisos",
                }), 404

            if request.method == "GET":
                return _get_flow_data(session, plubot_id, plubot.name)

            if request.method == "POST":
                data = request.get_json()
                if not data:
                    return jsonify({
                        "status": "error", "message": "No se proporcionaron datos"
                    }), 400

                nodes = data.get("nodes", [])
                edges = data.get("edges", [])
                if name := data.get("name"):
                    plubot.name = name

                # Limpieza y procesamiento
                session.query(FlowEdge).filter_by(chatbot_id=plubot_id).delete()
                session.query(Flow).filter_by(chatbot_id=plubot_id).delete()
                session.flush()

                node_id_map = _process_flow_nodes(session, plubot_id, nodes)
                _process_flow_edges(session, plubot_id, edges, node_id_map)

                session.commit()
                return jsonify({"status": "success", "message": "Flujo guardado"}), 200

    except Exception:
        logger.exception("Error fatal en handle_flow para plubot_id=%s", plubot_id)
        return jsonify({"status": "error", "message": "Error interno del servidor"}), 500
