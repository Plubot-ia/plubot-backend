import json
import os

from cryptography.fernet import Fernet
from flask import Blueprint, Response, current_app, jsonify, request
from google.oauth2 import service_account
from googleapiclient.discovery import build

from models import db
from models.user import User

integrations_bp = Blueprint("integrations", __name__)

# Clave de encriptación desde variable de entorno
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    msg = "ENCRYPTION_KEY no está configurada en las variables de entorno"
    raise ValueError(msg)
fernet = Fernet(ENCRYPTION_KEY.encode())

@integrations_bp.route("/google/sheets/connect", methods=["POST"])
def connect_google_sheets() -> Response:
    user_id = request.json.get("user_id")
    credentials_json = request.json.get("credentials")

    try:
        # Validar el formato de las credenciales
        required_fields = ["client_email", "private_key"]
        if not isinstance(credentials_json, dict) or not all(
            field in credentials_json for field in required_fields
        ):
            error_msg = (
                "Formato de credenciales inválido. "
                "Debe incluir client_email y private_key"
            )
            return jsonify({"error": error_msg}), 400

        # Guardar credenciales en la base de datos asociadas al usuario
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # Encriptar las credenciales
        encrypted_credentials = fernet.encrypt(json.dumps(credentials_json).encode()).decode()
        user.google_sheets_credentials = encrypted_credentials
        db.session.commit()

        return jsonify({"success": True, "message": "Conexión con Google Sheets establecida"})
    except Exception:
        current_app.logger.exception("Error en connect_google_sheets")
        return jsonify({"error": "Error interno del servidor"}), 500

@integrations_bp.route("/google/sheets/data", methods=["POST"])
def get_sheets_data() -> Response:
    user_id = request.json.get("user_id")
    spreadsheet_id = request.json.get("spreadsheet_id")
    range_name = request.json.get("range", "A1:Z1000")  # Rango predeterminado amplio

    try:
        user = User.query.get(user_id)
        if not user or not user.google_sheets_credentials:
            return jsonify({"error": "Credenciales no encontradas"}), 404

        # Desencriptar las credenciales
        decrypted_credentials = fernet.decrypt(user.google_sheets_credentials.encode()).decode()
        credentials_info = json.loads(decrypted_credentials)

        # Crear credenciales desde el JSON guardado
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )

        # Construir el servicio
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()

        # Obtener los datos
        result = sheet.values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()

        values = result.get("values", [])

        if not values:
            return jsonify({"data": [], "message": "No se encontraron datos"})

        # Convertir a formato más útil para frontend
        headers = values[0]
        rows = values[1:]
        formatted_data = []

        for row in rows:
            row_data = {}
            for i, cell in enumerate(row):
                if i < len(headers):
                    row_data[headers[i]] = cell
            formatted_data.append(row_data)

        return jsonify({
            "success": True,
            "data": formatted_data,
            "headers": headers,
            "raw_data": values
        })

    except Exception:
        current_app.logger.exception("Error en get_sheets_data")
        return jsonify({"error": "Error interno del servidor"}), 500
