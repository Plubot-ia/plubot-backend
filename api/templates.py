from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from config.settings import get_session
from models.template import Template
import json
import logging

templates_bp = Blueprint('templates', __name__)
logger = logging.getLogger(__name__)

@templates_bp.route('', methods=['GET', 'OPTIONS'])
@jwt_required()
def get_templates():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200

    with get_session() as session:
        templates = session.query(Template).all()
        return jsonify({
            'templates': [
                {
                    'id': t.id,
                    'name': t.name,
                    'description': t.description,
                    'tone': t.tone,
                    'purpose': t.purpose,
                    'flows': json.loads(t.flows)
                } for t in templates
            ]
        })