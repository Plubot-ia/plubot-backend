from . import db
import datetime

class WhatsappConnection(db.Model):
    __tablename__ = 'whatsapp_connections'

    id = db.Column(db.Integer, primary_key=True)
    plubot_id = db.Column(db.Integer, db.ForeignKey('plubots.id'), nullable=False, unique=True)
    session_id = db.Column(db.String(255), nullable=True) # ID from the external provider
    status = db.Column(db.String(50), nullable=False, default='disconnected') # e.g., pending, connected, disconnected, error
    whatsapp_number = db.Column(db.String(50), nullable=True)
    qr_code_url = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    plubot = db.relationship('Plubot', back_populates='whatsapp_connection')

    def to_dict(self):
        return {
            'id': self.id,
            'plubot_id': self.plubot_id,
            'session_id': self.session_id,
            'status': self.status,
            'whatsapp_number': self.whatsapp_number,
            'qr_code_url': self.qr_code_url
        }
