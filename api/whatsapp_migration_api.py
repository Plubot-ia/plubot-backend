"""WhatsApp Migration API - Handles migration from Puppeteer to WhatsApp Business API"""
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import os
import json
import logging
import re
from flask import Blueprint, request, jsonify
from redis import Redis
import hashlib
import hmac
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Blueprint for WhatsApp migration routes
whatsapp_migration_bp = Blueprint('whatsapp_migration', __name__, url_prefix='/api/whatsapp')

# Redis client for caching and queue management
redis_client = Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    password=os.getenv('REDIS_PASSWORD'),
    decode_responses=True
)

# Thread pool for async operations
executor = ThreadPoolExecutor(max_workers=10)

class RegistrationStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class WhatsAppProvider(Enum):
    META = "meta"
    TWILIO = "twilio"
    DIALOG360 = "360dialog"

# Provider configurations
PROVIDER_CONFIGS = {
    WhatsAppProvider.META: {
        "name": "Meta (WhatsApp Business API)",
        "base_url": "https://graph.facebook.com/v18.0",
        "docs_url": "https://developers.facebook.com/docs/whatsapp",
        "features": ["Official API", "Verified Business", "Template Messages", "Media Support"],
        "pricing": "Pay per conversation",
        "support_level": "Enterprise"
    },
    WhatsAppProvider.TWILIO: {
        "name": "Twilio WhatsApp",
        "base_url": "https://api.twilio.com",
        "docs_url": "https://www.twilio.com/docs/whatsapp",
        "features": ["Easy Integration", "Global Reach", "Sandbox Testing", "Programmable API"],
        "pricing": "Pay per message",
        "support_level": "Developer-friendly"
    },
    WhatsAppProvider.DIALOG360: {
        "name": "360dialog",
        "base_url": "https://waba.360dialog.io",
        "docs_url": "https://docs.360dialog.com",
        "features": ["Direct API Access", "Competitive Pricing", "EU Hosting", "Multi-agent Support"],
        "pricing": "Flexible pricing plans",
        "support_level": "Professional"
    }
}

def validate_phone_number(phone: str) -> bool:
    """Validate phone number format"""
    # Remove any non-digit characters
    phone_digits = re.sub(r'\D', '', phone)
    # Check if it's a valid length (between 7 and 15 digits)
    return 7 <= len(phone_digits) <= 15

def validate_migration_data(data: Dict[str, Any]) -> tuple[bool, str]:
    """Validate migration request data"""
    required_fields = ['businessName', 'countryCode', 'phoneNumber', 'businessType', 'provider']
    
    for field in required_fields:
        if field not in data or not data[field]:
            return False, f"Missing required field: {field}"
    
    if not validate_phone_number(data['phoneNumber']):
        return False, "Invalid phone number format"
    
    if data['provider'] not in [p.value for p in WhatsAppProvider]:
        return False, "Invalid provider selected"
    
    return True, "Valid"

@whatsapp_migration_bp.route('/providers', methods=['GET'])
def get_providers():
    """Get list of available WhatsApp Business API providers"""
    try:
        providers = []
        for provider in WhatsAppProvider:
            config = PROVIDER_CONFIGS[provider]
            providers.append({
                "id": provider.value,
                "name": config["name"],
                "features": config["features"],
                "pricing": config["pricing"],
                "supportLevel": config["support_level"],
                "docsUrl": config["docs_url"]
            })
        
        return jsonify({
            "success": True,
            "providers": providers
        }), 200
    except Exception as e:
        logger.error(f"Error fetching providers: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to fetch providers"
        }), 500

@whatsapp_migration_bp.route('/migrate', methods=['POST'])
def initiate_migration():
    """Initiate WhatsApp Business API migration"""
    try:
        data = request.json
        
        # Validate input data
        is_valid, message = validate_migration_data(data)
        if not is_valid:
            return jsonify({
                "success": False,
                "error": message
            }), 400
        
        # Generate migration ID
        migration_id = f"mig_{datetime.now().strftime('%Y%m%d%H%M%S')}_{data['phoneNumber'][-4:]}"
        
        # Store migration request in Redis
        migration_data = {
            "id": migration_id,
            "businessName": data['businessName'],
            "countryCode": data['countryCode'],
            "phoneNumber": data['phoneNumber'],
            "businessType": data['businessType'],
            "estimatedMessages": data.get('estimatedMessages', 'Not specified'),
            "provider": data['provider'],
            "status": RegistrationStatus.PENDING.value,
            "createdAt": datetime.now().isoformat(),
            "userId": data.get('userId', 'anonymous')
        }
        
        # Store in Redis with 30-day TTL
        redis_key = f"migration:{migration_id}"
        redis_client.setex(
            redis_key,
            timedelta(days=30),
            json.dumps(migration_data)
        )
        
        # Add to migration queue
        redis_client.lpush("migration_queue", migration_id)
        
        # Trigger async processing
        executor.submit(process_migration_async, migration_id)
        
        return jsonify({
            "success": True,
            "migrationId": migration_id,
            "message": "Migration request submitted successfully",
            "nextSteps": get_next_steps(data['provider'])
        }), 200
        
    except Exception as e:
        logger.error(f"Error initiating migration: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to initiate migration"
        }), 500

@whatsapp_migration_bp.route('/migration/<migration_id>/status', methods=['GET'])
def get_migration_status(migration_id: str):
    """Get status of a migration request"""
    try:
        redis_key = f"migration:{migration_id}"
        migration_data = redis_client.get(redis_key)
        
        if not migration_data:
            return jsonify({
                "success": False,
                "error": "Migration request not found"
            }), 404
        
        data = json.loads(migration_data)
        
        return jsonify({
            "success": True,
            "migration": data
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching migration status: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to fetch migration status"
        }), 500

@whatsapp_migration_bp.route('/webhook/meta', methods=['POST'])
def meta_webhook():
    """Handle Meta WhatsApp webhooks"""
    try:
        # Verify webhook signature
        signature = request.headers.get('X-Hub-Signature-256', '')
        if not verify_webhook_signature(request.data, signature, 'meta'):
            return 'Unauthorized', 401
        
        data = request.json
        # Process webhook data
        process_meta_webhook(data)
        
        return 'OK', 200
    except Exception as e:
        logger.error(f"Error processing Meta webhook: {str(e)}")
        return 'Error', 500

@whatsapp_migration_bp.route('/webhook/twilio', methods=['POST'])
def twilio_webhook():
    """Handle Twilio WhatsApp webhooks"""
    try:
        # Verify Twilio signature
        signature = request.headers.get('X-Twilio-Signature', '')
        if not verify_twilio_signature(request.url, request.form, signature):
            return 'Unauthorized', 401
        
        # Process webhook data
        process_twilio_webhook(request.form)
        
        return 'OK', 200
    except Exception as e:
        logger.error(f"Error processing Twilio webhook: {str(e)}")
        return 'Error', 500

def get_next_steps(provider: str) -> List[str]:
    """Get next steps for migration based on provider"""
    steps_map = {
        "meta": [
            "We'll send you an email with registration instructions",
            "Complete Meta Business verification (1-3 business days)",
            "Set up your WhatsApp Business profile",
            "Configure message templates",
            "Start sending messages via the official API"
        ],
        "twilio": [
            "Check your email for Twilio account setup",
            "Verify your phone number with Twilio",
            "Request WhatsApp approval (usually within 24 hours)",
            "Configure your messaging templates",
            "Begin using Twilio's WhatsApp API"
        ],
        "360dialog": [
            "Receive 360dialog onboarding email",
            "Complete KYC verification",
            "Get your API key",
            "Set up webhooks and templates",
            "Start messaging through 360dialog"
        ]
    }
    return steps_map.get(provider, [])

def process_migration_async(migration_id: str):
    """Process migration request asynchronously"""
    try:
        # Update status to in_progress
        redis_key = f"migration:{migration_id}"
        migration_data = json.loads(redis_client.get(redis_key))
        migration_data['status'] = RegistrationStatus.IN_PROGRESS.value
        redis_client.setex(redis_key, timedelta(days=30), json.dumps(migration_data))
        
        # Send notification emails, create accounts, etc.
        # This would integrate with actual provider APIs
        provider = migration_data['provider']
        
        if provider == 'meta':
            # Initiate Meta Business verification
            logger.info(f"Initiating Meta Business verification for {migration_id}")
            # TODO: Integrate with Meta Business API
        elif provider == 'twilio':
            # Create Twilio subaccount
            logger.info(f"Creating Twilio subaccount for {migration_id}")
            # TODO: Integrate with Twilio API
        elif provider == '360dialog':
            # Register with 360dialog
            logger.info(f"Registering with 360dialog for {migration_id}")
            # TODO: Integrate with 360dialog API
        
        # For demo purposes, mark as completed after a delay
        # In production, this would be triggered by actual provider callbacks
        import time
        time.sleep(5)  # Simulate processing time
        
        # Update status to completed
        migration_data['status'] = RegistrationStatus.COMPLETED.value
        migration_data['completedAt'] = datetime.now().isoformat()
        redis_client.setex(redis_key, timedelta(days=30), json.dumps(migration_data))
        
        logger.info(f"Migration {migration_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error processing migration {migration_id}: {str(e)}")
        # Update status to failed
        try:
            redis_key = f"migration:{migration_id}"
            migration_data = json.loads(redis_client.get(redis_key))
            migration_data['status'] = RegistrationStatus.FAILED.value
            migration_data['error'] = str(e)
            redis_client.setex(redis_key, timedelta(days=30), json.dumps(migration_data))
        except:
            pass

def verify_webhook_signature(payload: bytes, signature: str, provider: str) -> bool:
    """Verify webhook signature"""
    if provider == 'meta':
        secret = os.getenv('META_WEBHOOK_SECRET', '')
        if not secret:
            logger.warning("META_WEBHOOK_SECRET not configured")
            return True  # Allow in development
        expected_signature = 'sha256=' + hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    return True

def verify_twilio_signature(url: str, params: dict, signature: str) -> bool:
    """Verify Twilio webhook signature"""
    # In production, implement Twilio signature verification
    # using twilio.request_validator.RequestValidator
    auth_token = os.getenv('TWILIO_AUTH_TOKEN', '')
    if not auth_token:
        logger.warning("TWILIO_AUTH_TOKEN not configured")
        return True  # Allow in development
    
    # TODO: Implement actual Twilio signature verification
    return True

def process_meta_webhook(data: dict):
    """Process Meta webhook data"""
    # Handle different webhook events
    logger.info(f"Processing Meta webhook: {json.dumps(data)[:200]}")
    
    # Extract event type and process accordingly
    if 'entry' in data:
        for entry in data['entry']:
            if 'changes' in entry:
                for change in entry['changes']:
                    # Process different change types
                    if change.get('field') == 'messages':
                        # Handle incoming messages
                        logger.info("Received WhatsApp message via Meta webhook")
                    elif change.get('field') == 'message_template_status_update':
                        # Handle template status updates
                        logger.info("Received template status update")

def process_twilio_webhook(data: dict):
    """Process Twilio webhook data"""
    # Handle different webhook events
    logger.info(f"Processing Twilio webhook: {dict(data)}")
    
    # Extract message data
    if 'Body' in data:
        # Handle incoming message
        logger.info(f"Received WhatsApp message via Twilio: {data.get('Body')[:100]}")
    if 'MessageStatus' in data:
        # Handle message status update
        logger.info(f"Message status update: {data.get('MessageStatus')}")
