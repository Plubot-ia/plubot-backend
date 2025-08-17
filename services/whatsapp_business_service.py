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
        # Usar la página de callback del frontend
        self.redirect_uri = "https://plubot.com/whatsapp-callback.html"
    
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
            
            logger.info(f"Intercambiando código por token para Plubot {plubot_id}")
            logger.info(f"URL: {token_url}")
            logger.info(f"Client ID: {self.app_id[:10]}...")
            logger.info(f"Redirect URI: {self.redirect_uri}")
            
            response = requests.get(token_url, params=params)
            
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response text: {response.text[:500]}")
            
            if response.status_code != 200:
                logger.error(f"Error obteniendo token: Status {response.status_code}, Response: {response.text}")
                return False
            
            # Facebook puede devolver el token en diferentes formatos
            try:
                token_data = response.json()
                access_token = token_data.get("access_token")
            except:
                # Si no es JSON, intentar parsear como query string
                from urllib.parse import parse_qs
                parsed = parse_qs(response.text)
                access_token = parsed.get('access_token', [None])[0]
            
            if not access_token:
                logger.error(f"No se pudo extraer access_token de la respuesta: {response.text}")
                return False
            
            logger.info(f"Token obtenido exitosamente para Plubot {plubot_id}")
            
            # Obtener información del negocio de WhatsApp
            waba_id = None
            phone_number_id = None
            phone_number = None
            business_name = "WhatsApp Business"
            
            try:
                # Primero intentar obtener los WhatsApp Business Accounts directamente
                waba_url = f"https://graph.facebook.com/v18.0/debug_token"
                debug_response = requests.get(waba_url, params={
                    "input_token": access_token,
                    "access_token": f"{self.app_id}|{self.app_secret}"
                })
                
                if debug_response.status_code == 200:
                    debug_data = debug_response.json()
                    logger.info(f"Token debug info: {debug_data}")
                
                # Obtener información del usuario/negocio
                me_url = f"https://graph.facebook.com/v18.0/me"
                me_response = requests.get(me_url, params={"access_token": access_token})
                
                if me_response.status_code == 200:
                    me_data = me_response.json()
                    logger.info(f"Información del usuario: {me_data}")
                    
                    # Intentar obtener WhatsApp Business Accounts directamente
                    waba_list_url = f"https://graph.facebook.com/v18.0/{me_data.get('id', 'me')}/owned_whatsapp_business_accounts"
                    waba_response = requests.get(waba_list_url, params={"access_token": access_token})
                    
                    if waba_response.status_code == 200:
                        waba_data = waba_response.json()
                        logger.info(f"WhatsApp Business Accounts: {waba_data}")
                        
                        if waba_data.get('data'):
                            first_waba = waba_data['data'][0]
                            waba_id = first_waba.get('id')
                            business_name = first_waba.get('name', 'WhatsApp Business')
                            
                            # Obtener números de teléfono
                            if waba_id:
                                phones_url = f"https://graph.facebook.com/v18.0/{waba_id}/phone_numbers"
                                phones_response = requests.get(phones_url, params={"access_token": access_token})
                                
                                if phones_response.status_code == 200:
                                    phones_data = phones_response.json()
                                    logger.info(f"Números obtenidos: {phones_data}")
                                    
                                    if phones_data.get('data'):
                                        first_phone = phones_data['data'][0]
                                        phone_number_id = first_phone.get('id')
                                        phone_number = first_phone.get('display_phone_number', first_phone.get('verified_name'))
                    
                    # Si no funcionó, intentar con accounts
                    if not waba_id:
                        accounts_url = f"https://graph.facebook.com/v18.0/me/accounts"
                        accounts_response = requests.get(accounts_url, params={
                            "access_token": access_token,
                            "fields": "whatsapp_business_account"
                        })
                    
                    if accounts_response.status_code == 200:
                        accounts_data = accounts_response.json()
                        logger.info(f"Cuentas obtenidas: {accounts_data}")
                        
                        # Buscar la primera cuenta con WhatsApp Business
                        for account in accounts_data.get('data', []):
                            if 'whatsapp_business_account' in account:
                                waba_data = account['whatsapp_business_account']
                                waba_id = waba_data.get('id')
                                business_name = waba_data.get('name', 'WhatsApp Business')
                                
                                # Obtener números de teléfono
                                if waba_id:
                                    phones_url = f"https://graph.facebook.com/v18.0/{waba_id}/phone_numbers"
                                    phones_response = requests.get(phones_url, params={"access_token": access_token})
                                    
                                    if phones_response.status_code == 200:
                                        phones_data = phones_response.json()
                                        logger.info(f"Números obtenidos: {phones_data}")
                                        
                                        if phones_data.get('data'):
                                            first_phone = phones_data['data'][0]
                                            phone_number_id = first_phone.get('id')
                                            phone_number = first_phone.get('display_phone_number', first_phone.get('verified_name'))
                                break
            except Exception as e:
                logger.warning(f"No se pudo obtener información completa de WhatsApp Business: {str(e)}")
            
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
                whatsapp.updated_at = datetime.utcnow()
                logger.info(f"Actualizando WhatsApp Business existente para Plubot {plubot_id}")
            else:
                # Usar SQL directo para evitar problemas de metadata
                from sqlalchemy import text
                from datetime import datetime
                
                sql = text("""
                    INSERT INTO whatsapp_business 
                    (plubot_id, access_token, waba_id, phone_number_id, phone_number, business_name, is_active, is_connected, connection_status, created_at, updated_at)
                    VALUES 
                    (:plubot_id, :access_token, :waba_id, :phone_number_id, :phone_number, :business_name, :is_active, :is_connected, :connection_status, :created_at, :updated_at)
                """)
                
                db.session.execute(sql, {
                    'plubot_id': plubot_id,
                    'access_token': access_token,
                    'waba_id': waba_id,
                    'phone_number_id': phone_number_id,
                    'phone_number': phone_number,
                    'business_name': business_name,
                    'is_active': True,
                    'is_connected': True,
                    'connection_status': 'connected',
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                })
                logger.info(f"Creando nuevo WhatsApp Business para Plubot {plubot_id} usando SQL directo")
            
            db.session.commit()
            logger.info(f"WhatsApp Business conectado exitosamente para Plubot {plubot_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error en exchange_token: {str(e)}", exc_info=True)
            db.session.rollback()
            return False
    
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
    
    def update_whatsapp_info(self, plubot_id: int) -> bool:
        """Intenta actualizar la información de WhatsApp Business desde el token"""
        try:
            whatsapp = db.session.query(WhatsAppBusiness).filter_by(plubot_id=plubot_id).first()
            if not whatsapp or not whatsapp.access_token:
                return False
            
            access_token = whatsapp.access_token
            
            # Intentar obtener información actualizada
            try:
                # Obtener WhatsApp Business Accounts
                waba_url = f"https://graph.facebook.com/v18.0/me"
                response = requests.get(waba_url, params={"access_token": access_token})
                
                if response.status_code == 200:
                    user_data = response.json()
                    user_id = user_data.get('id')
                    
                    # Intentar obtener WABA directamente
                    waba_list_url = f"https://graph.facebook.com/v18.0/{user_id}/owned_whatsapp_business_accounts"
                    waba_response = requests.get(waba_list_url, params={"access_token": access_token})
                    
                    if waba_response.status_code == 200:
                        waba_data = waba_response.json()
                        if waba_data.get('data'):
                            first_waba = waba_data['data'][0]
                            whatsapp.waba_id = first_waba.get('id')
                            whatsapp.business_name = first_waba.get('name', 'WhatsApp Business')
                            
                            # Obtener números
                            if whatsapp.waba_id:
                                phones_url = f"https://graph.facebook.com/v18.0/{whatsapp.waba_id}/phone_numbers"
                                phones_response = requests.get(phones_url, params={"access_token": access_token})
                                
                                if phones_response.status_code == 200:
                                    phones_data = phones_response.json()
                                    if phones_data.get('data'):
                                        first_phone = phones_data['data'][0]
                                        whatsapp.phone_number_id = first_phone.get('id')
                                        whatsapp.phone_number = first_phone.get('display_phone_number')
                                        whatsapp.updated_at = datetime.utcnow()
                                        db.session.commit()
                                        return True
            except Exception as e:
                logger.error(f"Error actualizando información de WhatsApp: {str(e)}")
            
            return False
        except Exception as e:
            logger.error(f"Error en update_whatsapp_info: {str(e)}")
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
            
            # Verificar que tenemos la configuración necesaria
            if not whatsapp.phone_number_id or whatsapp.phone_number_id == "pending_configuration":
                logger.error(f"WhatsApp no está completamente configurado para Plubot {plubot_id}")
                logger.error(f"phone_number_id: {whatsapp.phone_number_id}, waba_id: {whatsapp.waba_id}")
                # Intentar usar el token para obtener la información faltante
                if whatsapp.access_token:
                    self.update_whatsapp_info(plubot_id)
                    # Recargar la información
                    db.session.refresh(whatsapp)
                    if not whatsapp.phone_number_id or whatsapp.phone_number_id == "pending_configuration":
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
                
                # Guardar evento del webhook
                webhook_event = WhatsAppWebhookEvent(
                    whatsapp_business_id=whatsapp.id,
                    event_type="message",
                    event_data={"value": {}, "message": {}}
                )
                db.session.add(webhook_event)
                
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