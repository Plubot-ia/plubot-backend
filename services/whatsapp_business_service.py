"""Servicio para manejar la integración con WhatsApp Business API."""
from datetime import UTC, datetime
import json
import logging
from typing import Any

from extensions import db
from flask import Flask, current_app
import requests

from models.whatsapp_business import WhatsAppBusiness, WhatsAppMessage, WhatsAppWebhookEvent

logger = logging.getLogger(__name__)


class WhatsAppBusinessService:
    """Servicio para manejar operaciones con WhatsApp Business API."""

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, app: Flask | None = None) -> None:
        """Inicializa el servicio con la configuración de la aplicación."""
        self.app = app or current_app
        self.app_id = self.app.config.get("FACEBOOK_APP_ID")
        self.app_secret = self.app.config.get("FACEBOOK_APP_SECRET")
        self.webhook_verify_token = self.app.config.get("WHATSAPP_WEBHOOK_VERIFY_TOKEN")
        # Usar la página de callback del frontend
        self.redirect_uri = "https://plubot.com/whatsapp-callback.html"

    def get_oauth_url(self, plubot_id: int) -> str:
        """Genera la URL de OAuth para conectar WhatsApp Business."""
        import urllib.parse

        # URL base de Facebook OAuth
        base_url = "https://www.facebook.com/v18.0/dialog/oauth"

        # Parámetros de OAuth
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "state": str(plubot_id),
            "response_type": "code",
            "scope": "whatsapp_business_management,whatsapp_business_messaging,business_management"
        }

        # Construir URL con parámetros codificados
        oauth_url = f"{base_url}?{urllib.parse.urlencode(params)}"
        logger.info("OAuth URL generada para Plubot %s: %s", plubot_id, oauth_url)

        return oauth_url

    def _extract_token_from_response(self, response_text: str) -> str | None:
        """Extrae el token de la respuesta de Facebook."""
        try:
            token_data = json.loads(response_text)
            return token_data.get("access_token")
        except (ValueError, KeyError):
            # Si no es JSON, intentar parsear como query string
            from urllib.parse import parse_qs
            parsed = parse_qs(response_text)
            return parsed.get("access_token", [None])[0]

    def _get_waba_info(self, access_token: str) -> tuple[str | None, str | None, str | None, str]:
        """Obtiene información del WhatsApp Business Account."""
        waba_id = None
        phone_number_id = None
        phone_number = None
        business_name = "WhatsApp Business"

        try:
            # Obtener información del token
            debug_url = "https://graph.facebook.com/v18.0/debug_token"
            debug_params = {
                "input_token": access_token,
                "access_token": f"{self.app_id}|{self.app_secret}"
            }
            debug_response = requests.get(debug_url, params=debug_params, timeout=30)
            
            if debug_response.status_code == 200:
                debug_data = debug_response.json()
                if debug_data.get("data", {}).get("is_valid"):
                    # Obtener WABAs
                    user_id = debug_data["data"].get("user_id")
                    if user_id:
                        wabas_url = f"{self.BASE_URL}/{user_id}/owned_whatsapp_business_accounts"
                        wabas_response = requests.get(
                            wabas_url,
                            params={"access_token": access_token},
                            timeout=30
                        )
                        
                        if wabas_response.status_code == 200:
                            wabas_data = wabas_response.json()
                            if wabas_data.get("data"):
                                first_waba = wabas_data["data"][0]
                                waba_id = first_waba.get("id")
                                business_name = first_waba.get("name", "WhatsApp Business")
                                
                                # Obtener phone numbers
                                phones_url = f"{self.BASE_URL}/{waba_id}/phone_numbers"
                                phones_response = requests.get(
                                    phones_url,
                                    params={"access_token": access_token},
                                    timeout=30
                                )
                                
                                if phones_response.status_code == 200:
                                    phones_data = phones_response.json()
                                    if phones_data.get("data"):
                                        first_phone = phones_data["data"][0]
                                        phone_number_id = first_phone.get("id")
                                        phone_number = first_phone.get("display_phone_number")
        except (ValueError, KeyError, TypeError):
            logger.exception("Error obteniendo información de WABA")
            
        return waba_id, phone_number_id, phone_number, business_name

    def exchange_token(self, code: str, plubot_id: int) -> bool:
        """Intercambia el código de autorización por un token de acceso."""
        try:
            # Intercambiar código por token
            token_url = f"{self.BASE_URL}/oauth/access_token"
            params = {
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "redirect_uri": self.redirect_uri,
                "code": code
            }

            logger.info("Intercambiando código por token para Plubot %s", plubot_id)
            logger.info("URL: %s", token_url)
            logger.info("Client ID: %s...", self.app_id[:10])
            logger.info("Redirect URI: %s", self.redirect_uri)

            response = requests.post(token_url, params=params, timeout=30)

            logger.info("Response status: %s", response.status_code)
            logger.info("Response text: %s", response.text[:500])

            if response.status_code != 200:
                logger.error(
                    "Error enviando mensaje: Status %s, Response: %s",
                    response.status_code, response.text
                )
                return False

            # Extraer token de la respuesta
            access_token = self._extract_token_from_response(response.text)
            if not access_token:
                logger.error("No se pudo extraer access_token de la respuesta: %s", response.text)
                return False

            logger.info("Procesando webhook para Plubot %s", plubot_id)

            # Obtener información del negocio de WhatsApp
            waba_id, phone_number_id, phone_number, business_name = self._get_waba_info(access_token)
            
            # Si no se obtuvieron los datos, usar valores por defecto
            if not waba_id:
                waba_id = "pending_configuration"
            if not phone_number_id:
                phone_number_id = "pending_configuration"
            if not phone_number:
                phone_number = "pending_configuration"

            whatsapp = db.session.query(WhatsAppBusiness).filter_by(plubot_id=plubot_id).first()

            if whatsapp:
                # Actualizar cuenta existente
                whatsapp.access_token = access_token
                whatsapp.waba_id = waba_id
                whatsapp.phone_number_id = phone_number_id
                whatsapp.phone_number = phone_number
                whatsapp.business_name = business_name
                whatsapp.is_active = True
                whatsapp.updated_at = datetime.now(UTC)
                logger.info("Actualizando WhatsApp Business existente para Plubot %s", plubot_id)
            else:
                # Usar SQL directo para evitar problemas de metadata

                # Crear nuevo registro de WhatsApp Business

                whatsapp = WhatsAppBusiness(
                    plubot_id=plubot_id,
                    access_token=access_token,
                    waba_id=waba_id,
                    phone_number_id=phone_number_id,
                    phone_number=phone_number,
                    business_name=business_name,
                    is_active=True,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC)
                )
                db.session.add(whatsapp)

                logger.info("Creando nuevo WhatsApp Business para Plubot %s", plubot_id)

            db.session.commit()
            logger.info("WhatsApp Business conectado exitosamente para Plubot %s", plubot_id)

        except (ValueError, KeyError, TypeError):
            logger.exception("Error en exchange_token")
            db.session.rollback()
            return False
        else:
            return True

    def verify_token(self, access_token: str) -> bool:
        """Verifica si un token de acceso es válido."""
        try:
            debug_url = f"{self.BASE_URL}/debug_token"
            params = {
                "input_token": access_token,
                "access_token": f"{self.app_id}|{self.app_secret}"
            }

            response = requests.get(debug_url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json().get("data", {})
                if data.get("is_valid"):
                    logger.info("Token válido para WhatsApp Business")
                    return True
                else:
                    logger.warning("Token inválido para WhatsApp Business")
                    return False
            else:
                logger.error("Error verificando token: Status %s", response.status_code)
                return False

        except (ValueError, KeyError, TypeError):
            logger.exception("Error verificando token")
            return False

    def disconnect(self, plubot_id: int) -> bool:
        """Desconecta WhatsApp Business de un Plubot."""
        try:
            whatsapp = db.session.query(WhatsAppBusiness).filter_by(plubot_id=plubot_id).first()

            if not whatsapp:
                logger.warning("No se encontró cuenta de WhatsApp para Plubot %s", plubot_id)
                return False

            # Marcar como inactiva
            whatsapp.is_active = False
            whatsapp.updated_at = datetime.now(UTC)

            db.session.commit()
            logger.info("Información de WhatsApp Business actualizada para Plubot %s", plubot_id)

        except (ValueError, KeyError, TypeError):
            logger.exception("Error desconectando WhatsApp")
            db.session.rollback()
            return False
        else:
            return True

    def send_message(
        self, plubot_id: int, to: str, message: str, message_type: str = "text"
    ) -> str | None:
        """Envía un mensaje de WhatsApp."""
        try:
            whatsapp = db.session.query(WhatsAppBusiness).filter_by(
                plubot_id=plubot_id, is_active=True
            ).first()

            if not whatsapp:
                logger.warning(
                    "No se encontró cuenta activa de WhatsApp para Plubot %s", plubot_id
                )
                return None

            # Verificar que tenemos la configuración necesaria
            if not whatsapp.phone_number_id or whatsapp.phone_number_id == "pending_configuration":
                logger.error(
                    "WhatsApp no está completamente configurado para Plubot %s",
                    plubot_id
                )
                logger.error(
                    "phone_number_id: %s, waba_id: %s",
                    whatsapp.phone_number_id,
                    whatsapp.waba_id
                )
                # Intentar usar el token para obtener la información faltante
                if whatsapp.access_token:
                    self.update_whatsapp_info(plubot_id)
                    # Recargar la información
                    db.session.refresh(whatsapp)
                    if (
                        not whatsapp.phone_number_id
                        or whatsapp.phone_number_id == "pending_configuration"
                    ):
                        return None
                else:
                    return None

            # Construir el mensaje según el tipo
            if message_type == "text":
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": message}
                }
            else:
                # Aquí se pueden agregar otros tipos de mensajes
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": message_type,
                    message_type: message
                }

            # Enviar mensaje
            url = (
                f"https://graph.facebook.com/v18.0/"
                f"{whatsapp.phone_number_id}/messages"
            )
            headers = {
                "Authorization": f"Bearer {whatsapp.access_token}",
                "Content-Type": "application/json"
            }

            response = requests.post(
                url, headers=headers, json=payload, timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                message_id = result.get("messages", [{}])[0].get("id")
                logger.info("Mensaje enviado exitosamente. ID: %s", message_id)

                # Guardar mensaje en la base de datos
                wa_message = WhatsAppMessage(
                    whatsapp_business_id=whatsapp.id,
                    message_id=message_id,
                    from_number=whatsapp.phone_number,
                    to_number=to,
                    message_type=message_type,
                    content=(
                        message if message_type == "text" else json.dumps(message)
                    ),
                    is_inbound=False,
                    status="sent"
                )
                db.session.add(wa_message)

                # Guardar evento del webhook
                webhook_event = WhatsAppWebhookEvent(
                    whatsapp_business_id=whatsapp.id,
                    event_type="message",
                    event_data={"value": {}, "message": {}}
                )
                db.session.add(webhook_event)

                db.session.commit()
                logger.info("Mensaje enviado y guardado exitosamente")
                return message_id
            else:
                logger.error("Error enviando mensaje: %s", result)
                return None

        except (ValueError, KeyError, TypeError):
            logger.exception("Error enviando mensaje")
            db.session.rollback()
            return None

    def verify_webhook(self, mode: str, token: str, challenge: str) -> str | None:
        """Verifica el webhook de WhatsApp."""
        if mode == "subscribe" and token == self.webhook_verify_token:
            logger.info("Webhook verificado exitosamente")
            return challenge
        
        logger.warning("Verificación de webhook con token incorrecto: %s", token)
        return None

    def process_webhook(self, data: dict[str, Any]) -> None:
        """Procesa los eventos del webhook de WhatsApp."""
        try:
            entry = data.get("entry", [])

            for item in entry:
                changes = item.get("changes", [])

                for change in changes:
                    value = change.get("value", {})

                    # Procesar mensajes
                    messages = value.get("messages", [])
                    for message in messages:
                        self._process_message(value, message)

                    # Procesar estados de mensajes
                    statuses = value.get("statuses", [])
                    for status in statuses:
                        self._process_status(value, status)

        except Exception:
            logger.exception("Error procesando webhook")

    def _process_message(self, value: dict[str, Any], message: dict[str, Any]) -> None:
        """Procesa un mensaje recibido."""
        try:
            phone_number_id = value.get("metadata", {}).get("phone_number_id")

            # Buscar la cuenta de WhatsApp correspondiente
            whatsapp = WhatsAppBusiness.query.filter_by(
                phone_number_id=phone_number_id,
                is_active=True
            ).first()

            if not whatsapp:
                logger.warning("No se encontró cuenta para phone_number_id: %s", phone_number_id)
                return

            # Extraer información del mensaje
            from_number = message.get("from")
            message_id = message.get("id")
            message_type = message.get("type", "text")

            # Extraer contenido según el tipo
            content = None
            if message_type == "text":
                content = message.get("text", {}).get("body")
            elif message_type == "image":
                content = message.get("image", {}).get("id")
            # Agregar más tipos según sea necesario

            # Guardar mensaje en la base de datos
            wa_message = WhatsAppMessage(
                whatsapp_business_id=whatsapp.id,
                message_id=message_id,
                from_number=from_number,
                to_number=whatsapp.phone_number,
                message_type=message_type,
                content=content,
                is_inbound=True,
                status="received",
                message_metadata=message
            )
            db.session.add(wa_message)

            # Guardar evento del webhook
            webhook_event = WhatsAppWebhookEvent(
                whatsapp_business_id=whatsapp.id,
                event_type="message",
                event_data={"value": value, "message": message}
            )
            db.session.add(webhook_event)
            db.session.commit()

            # TODO: Procesar con el motor de flujos cuando esté disponible

        except (ValueError, KeyError, TypeError):
            logger.exception("Error procesando mensaje")
            db.session.rollback()

    def _process_status(self, _value: dict[str, Any], status: dict[str, Any]) -> None:
        """Procesa una actualización de estado de mensaje."""
        try:
            message_id = status.get("id")
            status_type = status.get("status")

            # Actualizar el estado del mensaje en la base de datos
            wa_message = WhatsAppMessage.query.filter_by(message_id=message_id).first()

            if wa_message:
                wa_message.status = status_type

                if status_type == "delivered":
                    wa_message.delivered_at = datetime.now(UTC)
                elif status_type == "read":
                    wa_message.read_at = datetime.now(UTC)

                db.session.commit()
                logger.info("Estado de mensaje actualizado: %s - %s", message_id, status_type)

        except (ValueError, KeyError, TypeError):
            logger.exception("Error procesando estado")
            db.session.rollback()
