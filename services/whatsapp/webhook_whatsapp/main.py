import os
import hmac
import hashlib
from fastapi import FastAPI, Request, Header, HTTPException
import redis
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Redis connection (assuming service name 'redis' in docker-compose)
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=0,
    decode_responses=True  # To get strings instead of bytes
)

# WhatsApp app secret for signature verification
WHATSAPP_APP_SECRET = os.getenv('WHATSAPP_APP_SECRET')
if not WHATSAPP_APP_SECRET:
    logger.error("WHATSAPP_APP_SECRET environment variable is not set")
    # In a real app, we might want to fail fast, but for now we'll let it fail when used

@app.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None)
):
    """
    Handle incoming WhatsApp webhook.
    Validates the signature, extracts the message, and enqueues it for processing.
    """
    # Get the raw body
    body = await request.body()
    
    # Log the received body (for debugging, be cautious with PII in production)
    logger.info(f"Received webhook body: {body}")
    
    # Verify the signature if we have a secret
    if WHATSAPP_APP_SECRET:
        # Calculate expected signature
        expected_signature = "sha256=" + hmac.new(
            WHATSAPP_APP_SECRET.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        if not hmac.compare_digest(expected_signature, x_hub_signature_256 or ''):
            logger.warning("Invalid signature received")
            raise HTTPException(status_code=403, detail="Invalid signature")
    else:
        logger.warning("WHATSAPP_APP_SECRET not set, skipping signature verification")
    
    # Parse the JSON payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON received: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Log the payload (be cautious with PII)
    logger.info(f"Parsed payload: {json.dumps(payload, indent=2)[:200]}...")  # Truncate for logs
    
    # Enqueue the raw payload (or processed data) to Redis for further processing
    # We enqueue the raw body as string to preserve all data
    redis_client.lpush('whatsapp_in', body.decode('utf-8'))
    logger.info("Message enqueued to Redis list 'whatsapp_in'")
    
    # Return 200 OK to WhatsApp to acknowledge receipt
    return {"status": "ok"}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}