"""
Servicio para manejar la integración con WhatsApp Business API
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from flask import Flask, current_app

from extensions import db
from models.whatsapp_business import WhatsAppBusiness, WhatsAppMessage, WhatsAppWebhookEvent
# from services.flow_service import FlowService  # TODO: Implementar cuando esté disponible

logger = logging.getLogger(__name__)


class WhatsAppBusinessService:
    """Servicio para manejar operaciones con WhatsApp Business API"""
    
    BASE_URL = "https://graph.facebook.com/v18.0"
    
    def __init__(self, app: Flask | None = None) -> None:
        """Inicializa el servicio con la configuración de la aplicación"""
        self.app = app or current_app
        self.app_id = self.app.config.get("FACEBOOK_APP_ID")
        self.app_secret = self.app.config.get("FACEBOOK_APP_SECRET")
        self.webhook_verify_token = self.app.config.get("WHATSAPP_WEBHOOK_VERIFY_TOKEN")
        self.redirect_uri = self.app.config.get("WHATSAPP_REDIRECT_URI")
    
    def get_oauth_url(self, plubot_id: int) -> str:
        """Genera la URL de OAuth para conectar WhatsApp Business"""
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
        logger.info(f"OAuth URL generada para Plubot {plubot_id}: {oauth_url}")
        
        return oauth_url
    
    def exchange_token(self, code: str, plubot_id: int) -> bool:
        """Intercambia el código de autorización por un token de acceso"""
        try:
            # Intercambiar código por token
            token_url = f"{self.BASE_URL}/oauth/access_token"
            params = {
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "redirect_uri": self.redirect_uri,
                "code": code
            }
            
            response = requests.get(token_url, params=params)
            if response.status_code != 200:
                logger.error(f"Error obteniendo token: {response.text}")
                return False
            
            token_data = response.json()
            access_token = token_data.get("access_token")
            
            # Obtener información de la cuenta de WhatsApp Business
            waba_info = self._get_waba_info(access_token)
            if not waba_info:
                return False
            
            # Guardar o actualizar la información en la base de datos
            whatsapp = db.session.query(WhatsAppBusiness).filter_by(plubot_id=plubot_id).first()
            
            if whatsapp:
                # Actualizar cuenta existente
                whatsapp.access_token = access_token
                whatsapp.waba_id = waba_info["id"]
                whatsapp.phone_number_id = waba_info["phone_number_id"]
                whatsapp.phone_number = waba_info.get("phone_number")
                whatsapp.business_name = waba_info.get("business_name")
                whatsapp.is_active = True
                whatsapp.updated_at = datetime.utcnow()
            else:
                # Crear nueva cuenta
                whatsapp = WhatsAppBusiness(
                    plubot_id=plubot_id,
                    access_token=access_token,
                    waba_id=waba_info["id"],
                    phone_number_id=waba_info["phone_number_id"],
                    phone_number=waba_info.get("phone_number"),
                    business_name=waba_info.get("business_name"),
                    is_active=True
                )
                db.session.add(whatsapp)
            
            db.session.commit()
            logger.info(f"WhatsApp Business conectado exitosamente para Plubot {plubot_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error en exchange_token: {str(e)}")
            db.session.rollback()
            return False
    
    def _get_waba_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Obtiene información de la cuenta de WhatsApp Business"""
        try:
            # Primero obtener el WABA ID
            debug_url = f"{self.BASE_URL}/debug_token"
            params = {
                "input_token": access_token,
                "access_token": f"{self.app_id}|{self.app_secret}"
            }
            
            response = requests.get(debug_url, params=params)
            if response.status_code != 200:
                logger.error(f"Error obteniendo información del token: {response.text}")
                return None
            
            # Aquí deberías obtener el WABA ID real desde la respuesta
            # Por ahora retornamos datos de ejemplo
            return {
                "id": "WABA_ID_PLACEHOLDER",
                "phone_number_id": "PHONE_ID_PLACEHOLDER",
                "phone_number": "+1234567890",
                "business_name": "Mi Negocio"
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo información WABA: {str(e)}")
            return None
    
    def verify_token(self, access_token: str) -> bool:
        """Verifica si un token de acceso es válido"""
        try:
            debug_url = f"{self.BASE_URL}/debug_token"
            params = {
                "input_token": access_token,
                "access_token": f"{self.app_id}|{self.app_secret}"
            }
            
            response = requests.get(debug_url, params=params)
            if response.status_code == 200:
                data = response.json().get("data", {})
                return data.get("is_valid", False)
            
            return False
            
        except Exception as e:
            logger.error(f"Error verificando token: {str(e)}")
            return False
    
    def disconnect(self, plubot_id: int) -> bool:
        """Desconecta WhatsApp Business de un Plubot"""
        try:
            whatsapp = db.session.query(WhatsAppBusiness).filter_by(plubot_id=plubot_id).first()
            
            if not whatsapp:
                logger.warning(f"No se encontró cuenta de WhatsApp para Plubot {plubot_id}")
                return False
            
            # Marcar como inactiva
            whatsapp.is_active = False
            whatsapp.updated_at = datetime.utcnow()
            
            db.session.commit()
            logger.info(f"WhatsApp Business desconectado para Plubot {plubot_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error desconectando WhatsApp: {str(e)}")
            db.session.rollback()
            return False
    
    def send_message(self, plubot_id: int, to: str, message: str, message_type: str = "text") -> Optional[str]:
        """Envía un mensaje de WhatsApp"""
        try:
            whatsapp = db.session.query(WhatsAppBusiness).filter_by(plubot_id=plubot_id, is_active=True).first()
            
            if not whatsapp:
                logger.error(f"No se encontró cuenta activa de WhatsApp para Plubot {plubot_id}")
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
            url = f"{self.BASE_URL}/{whatsapp.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {whatsapp.access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                message_id = result.get("messages", [{}])[0].get("id")
                
                # Guardar mensaje en la base de datos
                wa_message = WhatsAppMessage(
                    whatsapp_business_id=whatsapp.id,
                    message_id=message_id,
                    from_number=whatsapp.phone_number,
                    to_number=to,
                    message_type=message_type,
                    content=message if message_type == "text" else json.dumps(message),
                    is_inbound=False,
                    status="sent"
                )
                db.session.add(wa_message)
                db.session.commit()
                
                logger.info(f"Mensaje enviado exitosamente: {message_id}")
                return message_id
            else:
                logger.error(f"Error enviando mensaje: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error enviando mensaje de WhatsApp: {str(e)}")
            db.session.rollback()
            return None
    
    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """Verifica el webhook de WhatsApp"""
        if mode == "subscribe" and token == self.webhook_verify_token:
            logger.info("Webhook verificado exitosamente")
            return challenge
        
        logger.warning(f"Verificación de webhook fallida: mode={mode}, token={token}")
        return None
    
    def process_webhook(self, data: Dict[str, Any]) -> None:
        """Procesa los eventos del webhook de WhatsApp"""
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
                        
        except Exception as e:
            logger.error(f"Error procesando webhook: {str(e)}")
    
    def _process_message(self, value: Dict[str, Any], message: Dict[str, Any]) -> None:
        """Procesa un mensaje recibido"""
        try:
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            
            # Buscar la cuenta de WhatsApp correspondiente
            whatsapp = WhatsAppBusiness.query.filter_by(
                phone_number_id=phone_number_id,
                is_active=True
            ).first()
            
            if not whatsapp:
                logger.warning(f"No se encontró cuenta para phone_number_id: {phone_number_id}")
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
            # if content and message_type == "text":
            #     flow_service = FlowService()
            #     flow_service.process_whatsapp_message(
            #         plubot_id=whatsapp.plubot_id,
            #         from_number=from_number,
            #         message=content
            #     )
            
            logger.info(f"Mensaje procesado: {message_id} de {from_number}")
            
        except Exception as e:
            logger.error(f"Error procesando mensaje: {str(e)}")
            db.session.rollback()
    
    def _process_status(self, value: Dict[str, Any], status: Dict[str, Any]) -> None:
        """Procesa una actualización de estado de mensaje"""
        try:
            message_id = status.get("id")
            status_type = status.get("status")
            
            # Actualizar el estado del mensaje en la base de datos
            wa_message = WhatsAppMessage.query.filter_by(message_id=message_id).first()
            
            if wa_message:
                wa_message.status = status_type
                
                if status_type == "delivered":
                    wa_message.delivered_at = datetime.utcnow()
                elif status_type == "read":
                    wa_message.read_at = datetime.utcnow()
                
                db.session.commit()
                logger.info(f"Estado actualizado para mensaje {message_id}: {status_type}")
            
        except Exception as e:
            logger.error(f"Error procesando estado: {str(e)}")
            db.session.rollback()