import logging
import os
import secrets
import string
from typing import Any

from flask import Blueprint, Response, jsonify, redirect, request, session
from flask_jwt_extended import create_access_token
from google.auth.transport import requests
from google.oauth2 import id_token
import requests as http_requests

from config.settings import get_session
from models.user import User

google_auth_bp = Blueprint("google_auth", __name__)
logger = logging.getLogger(__name__)

# Configuración de Google OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://www.plubot.com")

# Determinar si estamos en producción o desarrollo
IS_PRODUCTION = os.getenv("FLASK_ENV", "production") == "production"


def generate_random_password(length: int = 16) -> str:
    """Genera una contraseña aleatoria segura."""
    alphabet: str = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))


@google_auth_bp.route("/google/login", methods=["GET"])
def get_google_auth_url() -> Response:
    """Devuelve la URL para iniciar el flujo de autenticación con Google."""
    try:
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            logger.error("Credenciales de Google OAuth no configuradas")
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Servicio de autenticación con Google no disponible",
                    }
                ),
                500,
            )

        state: str = secrets.token_urlsafe(16)
        session["google_auth_state"] = state

        api_url = os.getenv("API_URL")
        if not api_url:
            logger.critical("La variable de entorno API_URL no está configurada.")
            return (
                jsonify(
                    {"status": "error", "message": "Configuración del servidor incompleta."}
                ),
                500,
            )
        redirect_uri: str = f"{api_url}/api/google/callback"
        logger.info("URL de redirección para Google OAuth: %s", redirect_uri)

        scopes: list[str] = ["openid", "email", "profile"]
        scope_string: str = "%20".join(scopes)

        auth_url: str = (
            f"https://accounts.google.com/o/oauth2/auth?response_type=code"
            f"&client_id={GOOGLE_CLIENT_ID}&redirect_uri={redirect_uri}"
            f"&scope={scope_string}&state={state}&prompt=select_account"
        )

        return jsonify({"success": True, "authUrl": auth_url})
    except Exception:
        logger.exception("Error al generar URL de autenticación con Google")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Error al generar URL de autenticación",
                }
            ),
            500,
        )


@google_auth_bp.route("/google/callback", methods=["GET"])
def google_callback() -> Response:
    """Maneja la respuesta de Google después de la autenticación."""
    error: str | None = request.args.get("error")
    if error:
        error_description: str = request.args.get("error_description", "Error desconocido")
        logger.error("Error de autenticación de Google: %s - %s", error, error_description)
        redirect_url = (
            f"{FRONTEND_URL}/login?error={error}&error_description={error_description}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": error_description or f"Error: {error}",
                    "redirect_url": redirect_url,
                }
            ),
            400,
        )

    state: str | None = request.args.get("state")
    stored_state: str | None = session.get("google_auth_state")
    if not state or state != stored_state:
        logger.error("Estado inválido en la respuesta de Google")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Estado inválido en la respuesta de Google",
                    "redirect_url": f"{FRONTEND_URL}/login?error=invalid_state",
                }
            ),
            400,
        )

    code: str | None = request.args.get("code")
    if not code:
        logger.error("No se recibió código de autorización de Google")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "No se recibió código de autorización",
                    "redirect_url": f"{FRONTEND_URL}/login?error=no_code",
                }
            ),
            400,
        )

    try:
        logger.info("Procesando código de autorización de Google: %s...", code[:10])

        api_url = os.getenv("API_URL")
        if not api_url:
            logger.critical(
                "La variable de entorno API_URL no está configurada para el callback."
            )
            return (
                jsonify(
                    {"status": "error", "message": "Configuración del servidor incompleta."}
                ),
                500,
            )
        redirect_uri: str = f"{api_url}/api/google/callback"
        token_url: str = "https://oauth2.googleapis.com/token"
        token_data: dict[str, str] = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        token_response = http_requests.post(token_url, data=token_data, timeout=10)
        token_json: dict[str, Any] = token_response.json()

        if "error" in token_json:
            error_desc = token_json.get("error_description", token_json["error"])
            logger.error("Error al obtener token de Google: %s", token_json["error"])
            redirect_url = (
                f"{FRONTEND_URL}/login?error=token_error&error_description="
                f"{token_json.get('error_description', '')}"
            )
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Error al obtener token: {error_desc}",
                        "redirect_url": redirect_url,
                    }
                ),
                400,
            )

        id_info: dict[str, Any] = id_token.verify_oauth2_token(
            token_json["id_token"], requests.Request(), GOOGLE_CLIENT_ID
        )

        email = id_info.get("email")
        name: str | None = id_info.get("name")
        picture: str | None = id_info.get("picture")
        google_id: str | None = id_info.get("sub")

        if not email:
            logger.error("No se pudo obtener el email del usuario de Google")
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "No se pudo obtener el email del usuario",
                        "redirect_url": f"{FRONTEND_URL}/login?error=no_email",
                    }
                ),
                400,
            )

        logger.info("Información de usuario de Google obtenida: %s, %s", email, name)

        with get_session() as session_db:
            user: User | None = session_db.query(User).filter_by(email=email).first()

            if user:
                logger.info("Usuario existente encontrado: %s, %s", user.id, user.email)
                if not user.google_id:
                    user.google_id = google_id
                    user.profile_picture = picture
                    session_db.commit()
                    logger.info(
                        "Actualizada información de Google para usuario: %s", user.id
                    )
            else:
                logger.info("Creando nuevo usuario con email: %s", email)
                random_password: str = generate_random_password()
                user = User(
                    email=email,
                    name=name or email.split("@")[0],
                    password=random_password,
                    is_verified=True,
                    google_id=google_id,
                    profile_picture=picture,
                )
                session_db.add(user)
                session_db.commit()
                logger.info("Nuevo usuario creado con ID: %s", user.id)

            access_token: str = create_access_token(identity=str(user.id))
            logger.info("Token JWT creado para usuario: %s", user.id)

            redirect_to_frontend_url = (
                f"{FRONTEND_URL}/auth/google/callback?token={access_token}"
            )
            return redirect(redirect_to_frontend_url)

    except Exception:
        logger.exception("Error en el proceso de autenticación con Google")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Error en el proceso de autenticación",
                    "redirect_url": f"{FRONTEND_URL}/login?error=auth_error",
                }
            ),
            500,
        )



