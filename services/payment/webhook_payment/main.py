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

# Redis connection
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=1,  # Using db=1 for payment related data as per documentation
    decode_responses=True
)

# Mercado Pago client secret for webhook validation
MP_CLIENT_SECRET = os.getenv('MP_CLIENT_SECRET')
if not MP_CLIENT_SECRET:
    logger.error("MP_CLIENT_SECRET environment variable is not set")

@app.post("/webhook")
async def mercadopago_webhook(
    request: Request,
    x_signature: str = Header(None, alias="x-signature")
):
    """
    Handle incoming Mercado Pago webhook.
    Validates the signature, extracts the notification, and enqueues it for processing.
    """
    # Get the raw body
    body = await request.body()
    
    # Log the received body (be cautious with PII in production)
    logger.info(f"Received Mercado Pago webhook body: {body}")
    
    # Verify the signature if we have a client secret
    if MP_CLIENT_SECRET and x_signature:
        # Calculate expected signature
        expected_signature = hmac.new(
            MP_CLIENT_SECRET.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        if not hmac.compare_digest(expected_signature, x_signature):
            logger.warning("Invalid Mercado Pago signature received")
            raise HTTPException(status_code=403, detail="Invalid signature")
    elif not MP_CLIENT_SECRET:
        logger.error("MP_CLIENT_SECRET not set")
        raise HTTPException(status_code=500, detail="Server configuration error")
    else:
        logger.warning("No x-signature header provided")
    
    # Parse the JSON payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON received: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Log the payload (be cautious with PII)
    logger.info(f"Parsed Mercado Pago payload: {json.dumps(payload, indent=2)[:200]}...")
    
    # Extract important info for logging
    if 'data' in payload and 'id' in payload['data']:
        payment_id = payload['data']['id']
        logger.info(f"Processing payment notification for payment ID: {payment_id}")
    
    # Enqueue the raw payload to Redis for further processing
    redis_client.lpush('payment_notifications', body.decode('utf-8'))
    logger.info("Payment notification enqueued to Redis list 'payment_notifications'")
    
    # Return 200 OK to Mercado Pago to acknowledge receipt
    return {"status": "ok"}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}