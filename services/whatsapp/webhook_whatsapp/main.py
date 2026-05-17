import os
import hmac
import hashlib
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import Response
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
    password=os.getenv('REDIS_PASSWORD'),
    db=0,
    decode_responses=True  # To get strings instead of bytes
)

# WhatsApp app secret for signature verification
WHATSAPP_APP_SECRET = os.getenv('WHATSAPP_APP_SECRET')
if not WHATSAPP_APP_SECRET:
    logger.error("WHATSAPP_APP_SECRET environment variable is not set")
    # In a real app, we might want to fail fast, but for now we'll let it fail when used

WA_VERIFY_TOKEN = os.getenv('WA_VERIFY_TOKEN', '')
if not WA_VERIFY_TOKEN:
    logger.warning("WA_VERIFY_TOKEN no configurado — la verificacion de Meta fallara")


@app.get("/webhook")
async def whatsapp_webhook_verify(request: Request):
    """
    Meta llama a GET /webhook con hub.mode, hub.verify_token, hub.challenge
    para verificar que el endpoint existe y el token coincide.
    Devuelve hub.challenge en texto plano con 200 OK.
    """
    hub_mode   = request.query_params.get("hub.mode", "")
    hub_token  = request.query_params.get("hub.verify_token", "")
    hub_challenge = request.query_params.get("hub.challenge", "")

    logger.info(f"[WA WEBHOOK] Verificacion recibida — mode={hub_mode} token={hub_token}")

    if hub_mode == "subscribe" and hub_token == WA_VERIFY_TOKEN:
        logger.info(f"[WA WEBHOOK] Verificacion exitosa — challenge: {hub_challenge}")
        return Response(content=hub_challenge, status_code=200, media_type="text/plain")

    logger.warning(f"[WA WEBHOOK] Verificacion fallida — token no coincide o modo invalido")
    raise HTTPException(status_code=403, detail="Verification failed")


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
    
    # Log truncated without PII
    logger.info(f"Received webhook payload ({len(body)} bytes) — signature_ok={bool(x_hub_signature_256)}")
    
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