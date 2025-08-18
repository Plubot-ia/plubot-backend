"""Modelo para la integración con WhatsApp Business API."""
from datetime import datetime

from extensions import db


class WhatsAppBusiness(db.Model):
    """Modelo para almacenar información de cuentas de WhatsApp Business."""

    __tablename__ = "whatsapp_business"

    id = db.Column(db.Integer, primary_key=True)
    # Fixed foreign key reference - must point to plubots table (plural)
    plubot_id = db.Column(db.Integer, db.ForeignKey("plubots.id"), nullable=False, unique=True)

    # Información de la cuenta de WhatsApp Business
    waba_id = db.Column(db.String(100), nullable=False)  # WhatsApp Business Account ID
    phone_number_id = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20))
    business_name = db.Column(db.String(200))

    # Tokens de acceso
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
    token_expires_at = db.Column(db.DateTime)

    # Estado
    is_active = db.Column(db.Boolean, default=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    messages = db.relationship("WhatsAppMessage", backref="whatsapp_account", lazy="dynamic")
    webhook_events = db.relationship(
        "WhatsAppWebhookEvent", backref="whatsapp_account", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<WhatsAppBusiness {self.phone_number} - {self.business_name}>"


class WhatsAppMessage(db.Model):
    """Modelo para almacenar mensajes de WhatsApp."""

    __tablename__ = "whatsapp_messages"

    id = db.Column(db.Integer, primary_key=True)
    whatsapp_business_id = db.Column(
        db.Integer, db.ForeignKey("whatsapp_business.id"), nullable=False
    )

    # Información del mensaje
    message_id = db.Column(db.String(200), unique=True)
    from_number = db.Column(db.String(20), nullable=False)
    to_number = db.Column(db.String(20), nullable=False)
    message_type = db.Column(db.String(50))  # text, image, audio, video, document, location
    content = db.Column(db.Text)
    media_url = db.Column(db.Text)

    # Dirección del mensaje
    is_inbound = db.Column(db.Boolean, default=True)  # True = recibido, False = enviado

    # Estado del mensaje
    status = db.Column(db.String(50))  # sent, delivered, read, failed
    error_message = db.Column(db.Text)

    # Metadata
    message_metadata = db.Column(db.JSON)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    delivered_at = db.Column(db.DateTime)
    read_at = db.Column(db.DateTime)

    def __repr__(self) -> str:
        direction = "IN" if self.is_inbound else "OUT"
        return f"<WhatsAppMessage {direction} {self.from_number} -> {self.to_number}>"


class WhatsAppWebhookEvent(db.Model):
    """Modelo para almacenar eventos del webhook de WhatsApp."""

    __tablename__ = "whatsapp_webhook_events"

    id = db.Column(db.Integer, primary_key=True)
    whatsapp_business_id = db.Column(
        db.Integer, db.ForeignKey("whatsapp_business.id"), nullable=False
    )

    # Información del evento
    event_type = db.Column(db.String(100), nullable=False)
    event_data = db.Column(db.JSON, nullable=False)

    # Estado del procesamiento
    processed = db.Column(db.Boolean, default=False)
    processed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        status = "Processed" if self.processed else "Pending"
        return f"<WhatsAppWebhookEvent {self.event_type} - {status}>"
