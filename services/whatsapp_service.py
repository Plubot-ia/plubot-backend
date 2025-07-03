"""Servicio para la integración con la API de WhatsApp."""

import logging
from threading import Thread
from typing import Any, Final

from flask import Flask, current_app
import requests
from sqlalchemy.exc import SQLAlchemyError

from models import WhatsAppConnection, db
from services import flow_executor

logger: Final = logging.getLogger(__name__)

# --- Constantes de Configuración ---
API_TIMEOUT: Final[int] = 15  # segundos

# --- Constantes de Estado ---
STATUS_CONNECTED: Final = "connected"
STATUS_DISCONNECTED: Final = "disconnected"
STATUS_ERROR: Final = "error"


class WhatsAppService:
    """Gestiona la comunicación con la API de WhatsApp."""

    def __init__(self, app: Flask | None = None) -> None:
        """Inicializa el servicio con la configuración de la app Flask."""
        self.app = app or current_app
        self.api_url: str | None = self.app.config.get("WHATSAPP_API_URL")
        self.api_key: str | None = self.app.config.get("WHATSAPP_API_KEY")

    def _get_headers(self) -> dict[str, str]:
        """Construye los encabezados de autorización para la API."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _make_request(
        self, method: str, endpoint: str, **kwargs: Any  # noqa: ANN401
    ) -> requests.Response:
        """Realiza una petición a la API de WhatsApp con manejo de errores y timeout."""
        if not self.api_url:
            msg = "La URL de la API de WhatsApp no está configurada."
            raise ValueError(msg)

        url = f"{self.api_url}/{endpoint}"
        headers = self._get_headers()

        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=API_TIMEOUT,
                **kwargs,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException:
            logger.exception("Error en la comunicación con la API de WhatsApp")
            raise
        else:
            return response

    def _extract_qr_code(self, response: requests.Response) -> str:
        """Extrae el código QR de la respuesta de la API."""
        data = response.json()
        qr_base64 = data.get("qr")
        if not qr_base64:
            msg = "La respuesta de la API no contiene un código QR."
            raise ValueError(msg)
        return qr_base64

    def initiate_connection(self) -> tuple[dict[str, Any], int]:
        """Inicia una nueva conexión y devuelve un código QR para escanear."""
        if not self.api_key:
            msg = "La integración con WhatsApp no está configurada."
            return {"status": STATUS_ERROR, "message": msg}, 500

        try:
            response = self._make_request("get", "users/login")
            qr_base64 = self._extract_qr_code(response)
        except (requests.exceptions.RequestException, ValueError):
            logger.exception("No se pudo iniciar la conexión con WhatsApp")
            msg = "No se pudo comunicar con el proveedor de WhatsApp."
            return {"status": STATUS_ERROR, "message": msg}, 502
        else:
            qr_code_url = f"data:image/png;base64,{qr_base64}"
            return {"qrCodeUrl": qr_code_url}, 200

    def get_connection_status(self, plubot_id: str) -> tuple[dict[str, Any], int]:
        """Verifica y actualiza el estado de la conexión de un Plubot."""
        try:
            response = self._make_request("get", "users/profile")
            data = response.json()
        except requests.exceptions.RequestException as e:
            if e.response and e.response.status_code in (401, 404):
                self._update_connection_record(plubot_id, STATUS_DISCONNECTED)
                return {"status": STATUS_DISCONNECTED}, 200

            logger.exception("Error al verificar el estado de WhatsApp para %s", plubot_id)
            connection = WhatsAppConnection.query.filter_by(plubot_id=plubot_id).first()
            if connection:
                return {
                    "status": connection.status,
                    "whatsappNumber": connection.whatsapp_number,
                }, 200
            return {"status": STATUS_DISCONNECTED}, 200
        else:
            if data.get("id") or data.get("pushname"):
                whatsapp_number = data.get("id", {}).get("user")
                self._update_connection_record(
                    plubot_id, STATUS_CONNECTED, whatsapp_number
                )
                return {
                    "status": STATUS_CONNECTED,
                    "whatsappNumber": whatsapp_number,
                }, 200

            self._update_connection_record(plubot_id, STATUS_DISCONNECTED)
            return {"status": STATUS_DISCONNECTED}, 200

    def _update_connection_record(
        self, plubot_id: str, status: str, whatsapp_number: str | None = None
    ) -> None:
        """Actualiza el registro de conexión en la base de datos."""
        try:
            connection = WhatsAppConnection.query.filter_by(plubot_id=plubot_id).first()

            if status == STATUS_DISCONNECTED:
                if connection:
                    db.session.delete(connection)
            elif status == STATUS_CONNECTED:
                # Desconectar cualquier otro plubot para evitar conflictos
                existing = WhatsAppConnection.query.filter(
                    WhatsAppConnection.plubot_id != plubot_id,
                    WhatsAppConnection.status == STATUS_CONNECTED,
                ).first()
                if existing:
                    db.session.delete(existing)

                if not connection:
                    connection = WhatsAppConnection(plubot_id=plubot_id)
                    db.session.add(connection)
                connection.status = status
                connection.whatsapp_number = whatsapp_number
        except SQLAlchemyError:
            logger.exception("Error de base de datos al actualizar el estado de conexión.")
            db.session.rollback()
        else:
            db.session.commit()

    def disconnect_plubot(self, plubot_id: str) -> tuple[dict[str, Any], int]:
        """Desconecta un Plubot de WhatsApp."""
        try:
            self._make_request("post", "users/logout")
        except requests.exceptions.RequestException:
            logger.exception(
                "La llamada a la API de desconexión falló, "
                "se procederá a eliminar el registro local de todos modos."
            )

        self._update_connection_record(plubot_id, STATUS_DISCONNECTED)
        return {"status": "success", "message": "Plubot desconectado."}, 200

    def handle_incoming_message(self, data: dict[str, Any]) -> None:
        """Gestiona un mensaje entrante desde el webhook de WhatsApp."""
        is_valid_message = (
            data.get("event") == "messages.upsert"
            and data.get("data", {}).get("message", {}).get("conversation")
        )
        if not is_valid_message:
            return

        msg_data = data.get("data", {})
        sender_id = msg_data.get("key", {}).get("remoteJid")
        message_body = msg_data.get("message", {}).get("conversation")

        if not all((sender_id, message_body)):
            return

        connection = WhatsAppConnection.query.filter_by(
            status=STATUS_CONNECTED
        ).first()
        if not connection:
            logger.warning(
                "Mensaje de %s recibido, pero no hay ningún Plubot conectado.", sender_id
            )
            return

        thread = Thread(
            target=self.process_flow,
            args=(self.app, connection.plubot_id, sender_id, message_body),
        )
        thread.start()

    @staticmethod
    def process_flow(
        app: Flask, plubot_id: str, user_id: str, message: str
    ) -> None:
        """Procesa el flujo en un hilo separado con contexto de aplicación."""
        with app.app_context():
            flow_executor.trigger_flow(plubot_id, user_id, message)

    def send_whatsapp_message(
        self, plubot_id: str, to_number: str, message_text: str
    ) -> None:
        """Envía un mensaje de texto a través de WhatsApp."""
        connection = WhatsAppConnection.query.filter_by(
            plubot_id=plubot_id, status=STATUS_CONNECTED
        ).first()
        if not connection:
            logger.error(
                "Intento de enviar mensaje desde un plubot no conectado: %s", plubot_id
            )
            return

        payload = {"to": to_number, "body": message_text}
        try:
            self._make_request("post", "messages/text", json=payload)
        except requests.exceptions.RequestException:
            logger.exception("Error al enviar mensaje vía API de WhatsApp.")
        else:
            logger.info(
                "Mensaje enviado a %s para el plubot %s", to_number, plubot_id
            )
