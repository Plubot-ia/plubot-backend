from datetime import UTC, datetime, timedelta
import json
import logging
import os
import threading

import bcrypt
import boto3
from botocore.exceptions import ClientError
from extensions import limiter
from flask import Blueprint, Flask, Response, current_app, jsonify, request
from flask.blueprints import BlueprintSetupState
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from flask_mail import Mail, Message
from jwt.exceptions import ExpiredSignatureError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from werkzeug.utils import secure_filename

from config.settings import get_session
from models.flow import Flow
from models.flow_edge import FlowEdge
from models.plubot import Plubot
from models.token_blocklist import TokenBlocklist
from models.user import User
from utils.validators import LoginModel, PasswordModel, RegisterModel

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)
mail = Mail()

# Configuración de S3 para fotos de perfil
s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)
BUCKET_NAME = os.getenv("AWS_S3_BUCKET", "plubot-profile-pics")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename: str) -> bool:
    """Check if the file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@auth_bp.record
def setup(state: BlueprintSetupState) -> None:
    """Initialize mail with app context."""
    mail.init_app(state.app)

@auth_bp.route("/register", methods=["POST", "OPTIONS"])
@limiter.limit("5 per minute")
def register() -> tuple[Response, int]:
    """Handle user registration."""
    logger.info(
        "Recibida solicitud para /api/auth/register con método %s", request.method
    )
    if request.method == "OPTIONS":
        logger.info("Respondiendo a solicitud OPTIONS para /api/auth/register")
        return jsonify({"message": "Preflight OK"}), 200
    try:
        if not request.is_json:
            return (
                jsonify({"status": "error", "message": "Content-Type must be application/json"}),
                415,
            )

        data = RegisterModel(**request.get_json())

    except ValidationError as e:
        # Usamos e.errors() que devuelve una lista de diccionarios
        # y sí incluye el campo 'ctx' que necesitamos en el frontend.
        error_details = e.errors()
        logger.warning("Error de validación en registro: %s", error_details)
        # Devolvemos directamente la lista de errores. El frontend la procesará.
        return jsonify(error_details), 422

    try:
        with get_session() as session:
            existing_user = session.query(User).filter_by(email=data.email).first()
            if existing_user:
                if not existing_user.is_verified:
                    send_verification_email(existing_user)
                    return (
                        jsonify(
                            {
                                "status": "success",
                                "message": (
                                    "El email ya está registrado pero no verificado. "
                                    "Se ha enviado un nuevo correo de verificación."
                                ),
                            }
                        ),
                        200,
                    )
                return jsonify({"status": "error", "message": "El email ya está registrado"}), 409

            hashed_password = bcrypt.hashpw(
                data.password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            user = User(
                email=data.email, password=hashed_password, name=data.name, is_verified=False
            )
            session.add(user)
            session.commit()

            send_verification_email(user)
            return (
                jsonify({"success": True, "message": "Revisa tu correo para verificar tu cuenta."}),
                201,
            )

    except IntegrityError:
        logger.warning(
            "Intento de registro con email ya existente (race condition): %s",
            data.email,
        )
        return jsonify({"status": "error", "message": "El email ya está registrado"}), 409
    except Exception:
        logger.exception("Error inesperado en /register")
        return jsonify({"status": "error", "message": "Ha ocurrido un error interno."}), 500


def send_async_email(app: Flask, msg: Message) -> None:
    with app.app_context():
        try:
            mail.send(msg)
            logger.info("Correo asíncrono enviado exitosamente a %s", msg.recipients)
        except Exception:
            logger.exception("FALLO CRÍTICO al enviar correo asíncrono")


def send_verification_email(user: User) -> None:
    """Sends a verification email to the user asynchronously."""
    logger.info("Iniciando envío de email de verificación para %s", user.email)

    sender_email = os.getenv("MAIL_USERNAME")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

    if not sender_email:
        logger.error("MAIL_USERNAME no está configurado. No se puede enviar el correo.")
        return

    token = create_access_token(
        identity=str(user.id),
        expires_delta=timedelta(hours=24),
        additional_claims={"purpose": "email_verify"},
    )
    verification_url = f"{frontend_url}/auth/verify-email/{token}"

    msg = Message(
        "Verifica tu cuenta de Plubot",
        sender=sender_email,
        recipients=[user.email],
    )
    msg.body = (
        f"¡Bienvenido a Plubot!\n\n"
        f"Para activar tu cuenta, por favor haz clic en el siguiente enlace:\n"
        f"{verification_url}\n\n"
        f"Si no te registraste en Plubot, por favor ignora este correo.\n\n"
        f"Saludos,\nEl equipo de Plubot"
    )

    try:
        # ruff: noqa: SLF001 - _get_current_object is required to pass the real app
        # instance to a background thread, as is common practice without Celery.
        app: Flask = current_app._get_current_object()
        thread = threading.Thread(target=send_async_email, args=[app, msg])
        thread.start()
        logger.info(
            "Correo de verificación encolado para envío asíncrono a %s", user.email
        )
    except Exception:
        logger.exception("FALLO CRÍTICO al encolar correo para %s", user.email)


@auth_bp.route("/verify-email/<token>", methods=["GET"])
def verify_email(token: str) -> tuple[Response, int]:
    """Verify user's email with a token."""
    try:
        decoded_token = decode_token(token)
        # We must check that the token's purpose is for email verification.
        if decoded_token.get("purpose") != "email_verify":
            return (
                jsonify({"status": "error", "message": "Token inválido para esta acción."}),
                403,
            )

        user_id = decoded_token["sub"]
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({"status": "error", "message": "Usuario no encontrado."}), 404

            if user.is_verified:
                # If the user is already verified, return a success response.
                return jsonify({"success": True, "message": "Email ya estaba verificado."}), 200

            logger.debug(
                "Verificando al usuario %s (ID: %s). Estado actual: %s",
                user.email,
                user.id,
                user.is_verified,
            )
            user.is_verified = True
            session.commit()
            logger.debug(
                "Commit realizado. El nuevo estado de is_verified para %s es True.", user.email
            )

            # Return a success JSON response, the frontend will handle the redirect.
            return jsonify({"success": True, "message": "Email verificado correctamente."}), 200

    except ExpiredSignatureError:
        # Here we should offer to resend the verification email.
        # For now, just return an error.
        return jsonify({"status": "error", "message": "El token de verificación ha expirado."}), 401
    except Exception:
        logger.exception("Error al verificar el email con token: %s", token)
        return jsonify({"status": "error", "message": "Token inválido o error interno."}), 400


@auth_bp.route("/resend-verification", methods=["POST"])
def resend_verification_email() -> tuple[Response, int]:
    """Resend the verification email for an unverified account."""
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"status": "error", "message": "Email no proporcionado."}), 400

    with get_session() as session:
        user = session.query(User).filter_by(email=email.strip().lower()).first()
        # To prevent user enumeration, we don't reveal if the user was found.
        # We only send the email if the user actually exists and is not verified.
        if user and not user.is_verified:
            logger.info(
                "Usuario '%s' encontrado y no verificado. Intentando reenviar email.",
                user.email,
            )
            try:
                send_verification_email(user)
            except Exception:
                logger.exception(
                    "FALLO CRÍTICO al intentar reenviar email de verificación a %s",
                    user.email,
                )
                # Even if mail fails, we don't expose the error to the client.
        elif user:
            logger.warning(
                "Intento de reenvío para usuario '%s' que ya está verificado. No se envió correo.",
                user.email,
            )
        else:
            logger.info(
                (
                    "Intento de reenvío para email no registrado: '%s'. "
                    "No se envió correo para evitar enumeración."
                ),
                email,
            )

    # Always return a generic success message.
    return (
        jsonify(
            {
                "success": True,
                "message": (
                    "Si existe una cuenta con ese correo y no está verificada, "
                    "se ha enviado un nuevo enlace de verificación."
                ),
            }
        ),
        200,
    )


@auth_bp.route("/login", methods=["POST", "OPTIONS"])
@limiter.limit("10 per minute")
def login() -> tuple[Response, int]:
    """Handle user login."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200
    try:
        if not request.is_json:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Content-Type must be application/json"
                    }
                ),
                415,
            )

        data = LoginModel(**request.get_json())

        with get_session() as session:
            user = (
                session.query(User)
                .options(selectinload(User.plubots))
                .filter_by(email=data.email)
                .first()
            )

            if not user or not bcrypt.checkpw(
                data.password.encode("utf-8"), user.password.encode("utf-8")
            ):
                logger.warning("Intento de login fallido para el email: %s", data.email)
                return (
            jsonify({"status": "error", "message": "Credenciales inválidas"}),
            401,
        )

            if not user.is_verified:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": (
                                "Registro exitoso. Por favor, verifica tu correo "
                                "electrónico antes de iniciar sesión."
                            ),
                        }
                    ),
                    403,
                )

            user_data = _serialize_user_profile(user)

            access_token = create_access_token(identity=str(user.id))
            refresh_token = create_refresh_token(identity=str(user.id))

            return (
                jsonify(
                    {
                        "success": True,
                        "user": user_data,
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                    }
                ),
                200,
            )

    except Exception as e:
        logger.exception("Error en /login")
        return jsonify({"status": "error", "message": str(e)}), 500


def _serialize_user_profile(user: User) -> dict:
    """Helper function to serialize user profile data."""
    chatbots_data = [
        {
            "id": bot.id,
            "name": bot.name,
            "tone": bot.tone,
            "purpose": bot.purpose,
            "whatsapp_number": bot.whatsapp_number,
            "initial_message": bot.initial_message,
            "business_info": bot.business_info,
            "pdf_url": bot.pdf_url,
            "image_url": bot.image_url,
            "created_at": bot.created_at.isoformat() if bot.created_at else None,
            "updated_at": bot.updated_at.isoformat() if bot.updated_at else None,
            "color": bot.color,
            "powers": bot.powers,
        }
        for bot in user.plubots
    ]

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "profile_picture": user.profile_picture,
        "bio": user.bio,
        "preferences": user.preferences,
        "level": user.level,
        "plucoins": user.plucoins,
        "role": user.role,
        "powers": user.powers,
        "is_verified": user.is_verified,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "plubots": chatbots_data,
    }


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout() -> tuple[Response, int]:
    """Logs out the user by revoking the JWT."""
    jti = get_jwt()["jti"]
    with get_session() as session:
        session.add(TokenBlocklist(jti=jti))
        session.commit()
    return jsonify({"message": "Successfully logged out"}), 200


@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_user_profile() -> tuple[Response, int]:
    """Get the profile of the currently authenticated user."""
    user_id = get_jwt_identity()
    with get_session() as session:
        user = (
            session.query(User)
            .options(selectinload(User.plubots))
            .filter_by(id=user_id)
            .first()
        )
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        user_data = _serialize_user_profile(user)
        return jsonify({"success": True, "user": user_data}), 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh() -> tuple[Response, int]:
    """Refresca un token de acceso y rota el token de refresco."""
    identity = get_jwt_identity()
    jti = get_jwt()["jti"]

    # Revocar el token de refresco antiguo
    with get_session() as session:
        session.add(TokenBlocklist(jti=jti, created_at=datetime.now(UTC)))
        session.commit()

    # Crear nuevos tokens
    new_access_token = create_access_token(identity=identity, fresh=False)
    new_refresh_token = create_refresh_token(identity=identity)

    return jsonify(
        {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token
        }
    ), 200


@auth_bp.route("/forgot-password", methods=["POST", "OPTIONS"])
@limiter.limit("30 per minute")
def forgot_password() -> tuple[Response, int]:
    """Handle forgot password request."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    try:
        email = (
            request.get_json().get("email")
            if request.is_json
            else request.form.get("email")
        )

        if not email:
            return jsonify({"status": "error", "message": "Email no proporcionado."}), 400

        with get_session() as session:
            user = session.query(User).filter_by(email=email.strip().lower()).first()
            # To prevent user enumeration, always return a success-like message,
            # but only send the email if the user actually exists.
            if user:
                token = create_access_token(
                    identity=str(user.id),
                    expires_delta=timedelta(hours=1),
                    additional_claims={"purpose": "password_reset"},
                )
                frontend_url = os.getenv("FRONTEND_URL", "https://www.plubot.com")
                reset_link = f"{frontend_url}/reset-password/{token}"
                msg_body = (
                    f"Hola,\n\nPara restablecer tu contraseña, haz clic en el siguiente enlace: "
                    f"{reset_link}\n\nSi no solicitaste esto, ignora este correo.\n\n"
                    f"Saludos,\nEl equipo de Plubot"
                )
                msg = Message(
                    subject="Restablecer tu contraseña",
                    recipients=[user.email],
                    body=msg_body,
                )
                mail.send(msg)
                logger.info(
                    "Solicitud de reseteo de contraseña enviada para el email: %s", user.email
                )

        return (
            jsonify(
                {
                    "success": True,
                    "message": (
                        "Si existe una cuenta con ese correo, se ha enviado un enlace "
                        "de restablecimiento."
                    ),
                }
            ),
            200,
        )

    except Exception:
        logger.exception("Error en /forgot_password")
        return (
            jsonify({"status": "error", "message": "Ocurrió un error al procesar la solicitud."}),
            500,
        )


@auth_bp.route("/reset-password", methods=["POST", "OPTIONS"])
def reset_password() -> tuple[Response, int]:
    """Handle password reset."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    try:
        if request.is_json:
            data = request.get_json()
            token = data.get("token")
            new_password = data.get("new_password")
        else:
            token = request.form.get("token")
            new_password = request.form.get("new_password")

        if not token or not new_password:
            return (
                jsonify({"status": "error", "message": "Token y nueva contraseña son requeridos."}),
                400,
            )

        try:
            PasswordModel(password=new_password)
        except ValidationError as e:
            # Extraer y formatear el mensaje de error para el usuario
            error_messages = [err["msg"] for err in e.errors()]
            return jsonify({"status": "error", "message": "; ".join(error_messages)}), 400

        decoded_token = decode_token(token)
        if decoded_token.get("purpose") != "password_reset":
            logger.warning(
                "Intento de reseteo de contraseña con token de propósito incorrecto: %s",
                decoded_token.get("purpose"),
            )
            return (
                jsonify({"status": "error", "message": "Token inválido para esta acción."}),
                403,
            )

        user_id = decoded_token["sub"]
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({"status": "error", "message": "Usuario no encontrado."}), 404

            hashed_password = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
            user.password = hashed_password.decode("utf-8")
            user.password_changed_at = datetime.now(UTC)
            session.commit()

            logger.info("Contraseña actualizada para el usuario con ID: %s", user.id)
            return (
                jsonify({"success": True, "message": "Contraseña restablecida con éxito."}),
                200,
            )

    except ExpiredSignatureError:
        logger.warning("Intento de reseteo de contraseña con token expirado.")
        return jsonify({"status": "error", "message": "El enlace ha expirado."}), 400
    except Exception:
        logger.exception("Error en /reset_password")
        return (
            jsonify(
                {"status": "error", "message": "Ocurrió un error al restablecer la contraseña."}
            ),
            500,
        )


@auth_bp.route("/change-password", methods=["POST", "OPTIONS"])
@jwt_required()
def change_password() -> tuple[Response, int]:
    """Handle password change for authenticated user."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    try:
        user_id = get_jwt_identity()
        if request.is_json:
            data = request.get_json()
            current_password = data.get("current_password")
            new_password = data.get("new_password")
        else:
            current_password = request.form.get("current_password")
            new_password = request.form.get("new_password")

        if not current_password or not new_password:
            return (
                jsonify(
                    {"status": "error", "message": "Contraseña actual y nueva son requeridas."}
                ),
                400,
            )

        try:
            PasswordModel(password=new_password)
        except ValidationError as e:
            error_messages = [err["msg"] for err in e.errors()]
            return jsonify({"status": "error", "message": "; ".join(error_messages)}), 400

        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user or not bcrypt.checkpw(
                current_password.encode("utf-8"), user.password.encode("utf-8")
            ):
                return (
                    jsonify({"status": "error", "message": "La contraseña actual es incorrecta."}),
                    401,
                )

            hashed_password = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
            user.password = hashed_password.decode("utf-8")
            user.password_changed_at = datetime.now(UTC)
            session.commit()

            msg_body = (
                "Hola,\n\nTu contraseña ha sido cambiada exitosamente.\n\n"
                "Si no realizaste este cambio, por favor contáctanos de inmediato.\n\n"
                "Saludos,\nEl equipo de Plubot"
            )
            msg = Message(
                subject="Tu contraseña ha sido cambiada",
                recipients=[user.email],
                body=msg_body,
            )
            mail.send(msg)
            return jsonify({"success": True, "message": "Contraseña cambiada con éxito."}), 200

    except Exception:
        logger.exception("Error en /change_password")
        return (
            jsonify({"status": "error", "message": "Ocurrió un error al cambiar la contraseña."}),
            500,
        )


@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile() -> tuple[Response, int]:
    """Get the profile of the authenticated user."""
    try:
        user_id = get_jwt_identity()
        logger.info("Solicitud recibida en /profile para user_id: %s", user_id)
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({"status": "error", "message": "Usuario no encontrado."}), 404

            chatbots_data = [
                {
                    "id": bot.id,
                    "name": bot.name,
                    "tone": bot.tone,
                    "purpose": bot.purpose,
                    "whatsapp_number": bot.whatsapp_number,
                    "initial_message": bot.initial_message,
                    "business_info": bot.business_info,
                    "pdf_url": bot.pdf_url,
                    "image_url": bot.image_url,
                    "created_at": bot.created_at.isoformat() if bot.created_at else None,
                    "updated_at": bot.updated_at.isoformat() if bot.updated_at else None,
                    "color": bot.color,
                    "powers": bot.powers,
                }
                for bot in user.plubots
            ]

            user_data = {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "profile_picture": user.profile_picture,
                "bio": user.bio,
                "preferences": user.preferences,
                "level": user.level,
                "plucoins": user.plucoins,
                "role": user.role,
                "powers": user.powers,
                "is_verified": user.is_verified,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                "plubots": chatbots_data,
            }
            return jsonify({"success": True, "user": user_data}), 200
    except Exception:
        logger.exception("Error en /profile")
        return (
            jsonify({"status": "error", "message": "Error al obtener los datos del perfil."}),
            500,
        )


@auth_bp.route("/profile", methods=["PUT", "OPTIONS"])
@jwt_required()
def update_profile() -> tuple[Response, int]:
    """Update user profile data, including profile picture."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    try:
        user_id = get_jwt_identity()
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({"status": "error", "message": "Usuario no encontrado."}), 404

            # Handle file upload
            if "profile_picture" in request.files:
                file = request.files["profile_picture"]
                if file and allowed_file(file.filename):
                    try:
                        filename = secure_filename(f"{user_id}_{file.filename}")
                        s3_client.upload_fileobj(
                            file,
                            BUCKET_NAME,
                            filename,
                            ExtraArgs={"ContentType": file.content_type},
                        )
                        user.profile_picture = f"https://{BUCKET_NAME}.s3.amazonaws.com/{filename}"
                    except ClientError:
                        logger.exception("Error al subir la foto de perfil a S3")
                        return (
                            jsonify(
                                {"status": "error", "message": "Error al subir la foto de perfil"}
                            ),
                            500,
                        )
                elif file:  # File exists but is not allowed
                    return (
                        jsonify({"status": "error", "message": "Tipo de archivo no permitido."}),
                        400,
                    )

            # Handle form data
            data = request.form
            user.name = data.get("name", user.name)
            user.bio = data.get("bio", user.bio)
            if "preferences" in data:
                try:
                    user.preferences = json.loads(data["preferences"])
                except json.JSONDecodeError:
                    return (
                        jsonify(
                            {"status": "error", "message": "Formato de preferencias inválido"}
                        ),
                        400,
                    )

            session.commit()
            updated_user_data = {
                "name": user.name,
                "bio": user.bio,
                "profile_picture": user.profile_picture,
                "preferences": user.preferences,
            }
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Perfil actualizado correctamente",
                        "user": updated_user_data,
                    }
                ),
                200,
            )
    except Exception:
        logger.exception("Error en /profile (PUT)")
        return jsonify({"status": "error", "message": "Error al actualizar el perfil"}), 500


@auth_bp.route("/profile/powers", methods=["POST", "OPTIONS"])
@jwt_required()
def add_power() -> tuple[Response, int]:
    """Add a power to the user's profile."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        if not data or "powerId" not in data:
            return jsonify({"status": "error", "message": "Se requiere el ID del poder."}), 400

        power_id = data["powerId"]
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({"status": "error", "message": "Usuario no encontrado."}), 404

            current_powers = user.powers.split(",") if user.powers else []

            if power_id in current_powers:
                return jsonify({"status": "error", "message": "El poder ya ha sido agregado."}), 409

            if len(current_powers) >= 3:
                return (
                    jsonify({"status": "error", "message": "Límite de 3 poderes alcanzado."}),
                    400,
                )

            current_powers.append(power_id)
            user.powers = ",".join(current_powers)
            session.commit()

            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Poder agregado correctamente.",
                        "powers": user.powers,
                    }
                ),
                200,
            )

    except Exception:
        logger.exception("Error al agregar poder")
        return (
            jsonify({"status": "error", "message": "Error interno al agregar el poder."}),
            500,
        )


@auth_bp.route("/profile/powers", methods=["DELETE", "OPTIONS"])
@jwt_required()
def remove_power() -> tuple[Response, int]:
    """Remove a power from the user's profile."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        if not data or "powerId" not in data:
            return jsonify({"status": "error", "message": "Se requiere el ID del poder."}), 400

        power_id = data["powerId"]
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({"status": "error", "message": "Usuario no encontrado."}), 404

            current_powers = user.powers or []

            if power_id not in current_powers:
                return jsonify({"status": "error", "message": "El poder no ha sido agregado."}), 404

            user.powers = [p for p in current_powers if p != power_id]
            session.commit()

            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Poder eliminado correctamente.",
                        "powers": user.powers,
                    }
                ),
                200,
            )

    except Exception:
        logger.exception("Error al eliminar poder")
        return (
            jsonify({"status": "error", "message": "Error interno al eliminar el poder."}),
            500,
        )

@auth_bp.route("/plubots", methods=["POST", "OPTIONS"])
@jwt_required()
def create_plubot() -> tuple[Response, int]:
    """Create a new Plubot for the user."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        if not data or not data.get("name") or not data.get("tone"):
            return jsonify({"status": "error", "message": "Nombre y tono son requeridos."}), 400

        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({"status": "error", "message": "Usuario no encontrado."}), 404

            google_sheets_credentials = (
                data.get("powerConfig", {}).get("google-sheets", {}).get("credentials")
            )
            if google_sheets_credentials:
                user.google_sheets_credentials = google_sheets_credentials

            powers_data = data.get("powers", [])
            powers_str = (
                ",".join(powers_data) if isinstance(powers_data, list) else str(powers_data)
            )

            new_plubot = Plubot(
                name=data["name"],
                tone=data["tone"],
                purpose=data.get("purpose", "asistir a los clientes"),
                initial_message=data.get(
                    "initial_message", "¡Hola! Soy tu Plubot, aquí para ayudarte."
                ),
                color=data.get("color"),
                powers=powers_str,
                user_id=user_id,
            )
            session.add(new_plubot)
            session.commit()

            plubot_data = {
                "id": new_plubot.id,
                "name": new_plubot.name,
                "tone": new_plubot.tone,
                "color": new_plubot.color,
                "powers": new_plubot.powers,
                "purpose": new_plubot.purpose,
                "initial_message": new_plubot.initial_message,
                "created_at": new_plubot.created_at.isoformat()
                if new_plubot.created_at
                else None,
                "updated_at": new_plubot.updated_at.isoformat()
                if new_plubot.updated_at
                else None,
            }
            return jsonify({"success": True, "plubot": plubot_data}), 201

    except Exception:
        logger.exception("Error al crear Plubot")
        return (
            jsonify({"status": "error", "message": "Error interno al crear el Plubot."}),
            500,
        )

@auth_bp.route("/profile/plubots/<int:plubot_id>", methods=["DELETE", "OPTIONS"])
@jwt_required()
def delete_plubot(plubot_id: int) -> tuple[Response, int]:
    """Delete a Plubot and its associated flows and edges."""
    if request.method == "OPTIONS":
        return jsonify({"message": "Preflight OK"}), 200

    try:
        user_id = get_jwt_identity()
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({"status": "error", "message": "Usuario no encontrado."}), 404

            plubot = session.query(Plubot).filter_by(id=plubot_id, user_id=user_id).first()
            if not plubot:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Plubot no encontrado o no pertenece al usuario.",
                        }
                    ),
                    404,
                )

            flows = session.query(Flow).filter_by(chatbot_id=plubot_id).all()
            if flows:
                flow_ids = [flow.id for flow in flows]
                session.query(FlowEdge).filter(FlowEdge.source_flow_id.in_(flow_ids)).delete(
                    synchronize_session=False
                )
                session.query(Flow).filter_by(chatbot_id=plubot_id).delete(
                    synchronize_session=False
                )

            session.delete(plubot)
            session.commit()

            updated_plubots_data = [
                {
                    "id": bot.id,
                    "name": bot.name,
                    "tone": bot.tone,
                    "purpose": bot.purpose,
                    "whatsapp_number": bot.whatsapp_number,
                    "initial_message": bot.initial_message,
                    "business_info": bot.business_info,
                    "pdf_url": bot.pdf_url,
                    "image_url": bot.image_url,
                    "created_at": bot.created_at.isoformat() if bot.created_at else None,
                    "updated_at": bot.updated_at.isoformat() if bot.updated_at else None,
                    "color": bot.color,
                    "powers": bot.powers,
                }
                for bot in user.plubots
            ]

            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Plubot eliminado correctamente.",
                        "plubots": updated_plubots_data,
                    }
                ),
                200,
            )
    except IntegrityError:
        logger.warning(
            "Intento de eliminar un Plubot con dependencias activas (ForeignKeyViolation)."
        )
        session.rollback()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": (
                        "No se puede eliminar este Plubot porque tiene dependencias activas."
                    ),
                }
            ),
            409,
        )
    except Exception:
        logger.exception("Error al eliminar Plubot")
        session.rollback()
        return (
            jsonify({"status": "error", "message": "Error interno al eliminar el Plubot."}),
            500,
        )
