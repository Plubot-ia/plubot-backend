import os
import requests
import logging
from flask import current_app
from threading import Thread

from models import db, WhatsappConnection, Plubot
from services import flow_executor

class WhatsAppService:
    def __init__(self):
        self.api_url = current_app.config.get('WHATSAPP_API_URL')
        self.api_key = current_app.config.get('WHATSAPP_API_KEY')

    def _get_headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

    def initiate_connection(self, plubot_id):
        if not self.api_url or not self.api_key:
            return {'status': 'error', 'message': 'La integración con WhatsApp no está configurada.'}, 500

        try:
            # This endpoint returns a base64 encoded QR image
            response = requests.get(f"{self.api_url}/users/login", headers=self._get_headers())
            response.raise_for_status()
            data = response.json()
            qr_base64 = data.get("qr")
            if not qr_base64:
                raise ValueError("No QR code in API response")
            
            # The frontend will render this data URL
            qr_code_url = f"data:image/png;base64,{qr_base64}"
            return {"qrCodeUrl": qr_code_url}, 200
        except requests.exceptions.RequestException as e:
            logging.error(f"Error initiating WhatsApp connection: {e}")
            return {'status': 'error', 'message': 'No se pudo comunicar con el proveedor de WhatsApp.'}, 502
        except ValueError as e:
            logging.error(f"Error processing QR code response: {e}")
            return {'status': 'error', 'message': 'Respuesta inesperada del proveedor de WhatsApp.'}, 502

    def get_connection_status(self, plubot_id):
        connection = WhatsappConnection.query.filter_by(plubot_id=plubot_id).first()

        try:
            # We use the profile endpoint to check if we are logged in
            response = requests.get(f"{self.api_url}/users/profile", headers=self._get_headers())
            response.raise_for_status()
            data = response.json()

            # If we get user data, it means we are connected
            if data.get("id") or data.get("pushname"):
                status = "connected"
                whatsapp_number = data.get("id", {}).get("user")
                
                if not connection:
                    # If another plubot was connected, disconnect it first to avoid conflicts
                    existing_connection = WhatsappConnection.query.filter_by(status='connected').first()
                    if existing_connection:
                        db.session.delete(existing_connection)

                    connection = WhatsappConnection(plubot_id=plubot_id)
                    db.session.add(connection)
                
                connection.status = status
                connection.whatsapp_number = whatsapp_number
                db.session.commit()
                
                return {"status": status, "whatsappNumber": whatsapp_number}, 200
            else:
                # If response is valid but no user data, we are likely disconnected
                if connection:
                    db.session.delete(connection)
                    db.session.commit()
                return {"status": "disconnected"}, 200

        except requests.exceptions.RequestException as e:
            # If API call fails (e.g. 404 if not logged in), treat as disconnected
            if e.response and e.response.status_code in [404, 401]:
                if connection:
                    db.session.delete(connection)
                    db.session.commit()
                return {"status": "disconnected"}, 200
            
            logging.error(f"Error checking whatsapp status for {plubot_id}: {e}")
            # On other errors, return last known status
            if connection:
                return {"status": connection.status, "whatsappNumber": connection.whatsapp_number}, 200
            return {"status": "disconnected"}, 200

    def disconnect_plubot(self, plubot_id):
        try:
            # Logout from the WhatsApp session via API
            response = requests.post(
                f"{self.api_url}/users/logout",
                headers=self._get_headers()
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"API call to disconnect failed, but proceeding to delete local record. Error: {e}")
        
        # Delete the connection from our database
        connection = WhatsappConnection.query.filter_by(plubot_id=plubot_id).first()
        if connection:
            db.session.delete(connection)
            db.session.commit()
            
        return {"status": "success", "message": "Plubot desconectado de WhatsApp." }, 200

    def handle_incoming_message(self, data):
        # This webhook handler assumes a single active WhatsApp connection for the entire application,
        # identified by the API Key in the environment variables.
        if data.get('event') == 'messages.upsert' and data.get('data', {}).get('message', {}).get('conversation'):
            msg_data = data['data']
            sender_id = msg_data.get('key', {}).get('remoteJid')
            message_body = msg_data.get('message', {}).get('conversation')

            if not all([sender_id, message_body]):
                return

            # Find the currently active plubot connection
            connection = WhatsappConnection.query.filter_by(status='connected').first()
            if not connection:
                logging.warning(f"Mensaje de {sender_id} recibido, pero no hay ningún Plubot conectado.")
                return

            # Process the flow in a separate thread to not block the webhook response
            thread = Thread(target=self.process_flow, args=(connection.plubot_id, sender_id, message_body))
            thread.start()

    def process_flow(self, plubot_id, user_id, message):
        with current_app.app_context():
            # The trigger_flow function now handles the entire logic of the conversation
            flow_executor.trigger_flow(plubot_id, user_id, message)

    def send_whatsapp_message(self, plubot_id, to_number, message_text):
        connection = WhatsappConnection.query.filter_by(plubot_id=plubot_id, status='connected').first()
        if not connection:
            logging.error(f"Intento de enviar mensaje desde un plubot no conectado: {plubot_id}")
            return

        # The 'to_number' received from the webhook is the 'remoteJid' which is in the correct format
        payload = {
            "to": to_number,
            "body": message_text
        }
        try:
            response = requests.post(f"{self.api_url}/messages/text", json=payload, headers=self._get_headers())
            response.raise_for_status()
            logging.info(f"Mensaje enviado a {to_number} para el plubot {plubot_id}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error al enviar mensaje vía API de WhatsApp: {e}")
