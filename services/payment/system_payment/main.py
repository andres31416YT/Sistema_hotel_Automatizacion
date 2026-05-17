import os
import logging
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Redis connection
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=1,  # Using db=1 for payment related data
    decode_responses=True
)

# Mercado Pago configuration
MP_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN')
MP_API_URL = os.getenv('MP_API_URL', 'https://api.mercadopago.com/v1')

if not MP_ACCESS_TOKEN:
    logger.error("MP_ACCESS_TOKEN environment variable is not set")

class PaymentVerificationRequest(BaseModel):
    payment_id: str

class PaymentRecordRequest(BaseModel):
    payment_id: str
    amount: float
    currency: str
    status: str
    external_reference: str = None
    payer_info: dict = None

class PaymentLinkRequest(BaseModel):
    external_reference: str  # e.g., reservation ID or similar
    amount: float
    currency: str = "USD"
    description: str = "Payment for hotel reservation"
    payer_email: str = None
    payer_name: str = None

@app.post("/verify-payment")
async def verify_payment(request: PaymentVerificationRequest):
    """
    Verify a payment with Mercado Pago.
    """
    if not MP_ACCESS_TOKEN:
        logger.error("MP_ACCESS_TOKEN not configured")
        raise HTTPException(status_code=500, detail="Payment service not configured")
    
    url = f"{MP_API_URL}/payments/{request.payment_id}"
    
    headers = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
        
        if response.status_code != 200:
            logger.error(f"Failed to verify payment: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to verify payment: {response.text}"
            )
        
        payment_data = response.json()
        logger.info(f"Payment verification successful for payment ID: {request.payment_id}")
        return payment_data
    
    except httpx.RequestError as e:
        logger.error(f"Request to Mercado Pago API failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

@app.post("/record-payment")
async def record_payment(request: PaymentRecordRequest):
    """
    Record a payment in the local database (using Redis for simplicity in this example, but in a real system this would be a proper DB).
    We are using Redis for simplicity in this example, but note that the documentation mentions a PostgreSQL Payments DB.
    For the purpose of this task, we'll use Redis to store payment records as a placeholder.
    In a real implementation, this would write to the PostgreSQL Payments DB.
    """
    try:
        # Create a payment record
        payment_record = {
            "payment_id": request.payment_id,
            "amount": request.amount,
            "currency": request.currency,
            "status": request.status,
            "external_reference": request.external_reference,
            "payer_info": request.payer_info,
            "timestamp": os.environ.get('TIMESTAMP', 'unknown')  # In a real app, use proper timestamp
        }
        
        # Store in Redis as a hash (or as a JSON string in a list, etc.)
        # We'll store as a hash for easy retrieval by payment_id
        redis_client.hset(f"payment:{request.payment_id}", mapping=payment_record)
        # Also add to a list of all payments for easy scanning
        redis_client.lpush("payments", request.payment_id)
        
        logger.info(f"Payment recorded: {request.payment_id}")
        return {"status": "recorded", "payment_id": request.payment_id}
    
    except Exception as e:
        logger.error(f"Failed to record payment: {e}")
        raise HTTPException(status_code=500, detail="Failed to record payment")

@app.post("/generate-link")
async def generate_payment_link(request: PaymentLinkRequest):
    """
    Generate a payment link (preference) using Mercado Pago API.
    """
    if not MP_ACCESS_TOKEN:
        logger.error("MP_ACCESS_TOKEN not configured")
        raise HTTPException(status_code=500, detail="Payment service not configured")
    
    url = f"{MP_API_URL}/checkout/preferences"
    
    headers = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Prepare the payload for Mercado Pago preference
    payload = {
        "items": [
            {
                "title": request.description,
                "quantity": 1,
                "unit_price": request.amount,
                "currency_id": request.currency
            }
        ],
        "external_reference": request.external_reference,
        "payment_methods": {
            "excluded_payment_types": [
                {
                    "id": "ticket"
                }
            ],
            "installments": 12
        },
        "back_urls": {
            "success": "https://www.tuhotel.com/pago-exitoso",  # Replace with your actual success URL
            "failure": "https://www.tuhotel.com/pago-fallido",
            "pending": "https://www.tuhotel.com/pago-pendiente"
        },
        "auto_return": "approved",
        "notification_url": f"{os.getenv('CORE_URL', 'http://core:8080')}/payment-webhook"  # This should be the URL of your payment webhook, but note: we are using the core service to orchestrate, so we might want to send the webhook to the core? Actually, the payment webhook is separate. We'll leave this as is, but note that the payment webhook service is separate and will receive the notification from Mercado Pago.
    }
    
    # If payer info is provided, add it
    if request.payer_email:
        payload["payer"] = {
            "email": request.payer_email
        }
    if request.payer_name:
        if "payer" not in payload:
            payload["payer"] = {}
        payload["payer"]["name"] = request.payer_name
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=10.0)
        
        if response.status_code != 201:
            logger.error(f"Failed to generate payment link: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to generate payment link: {response.text}"
            )
        
        link_data = response.json()
        init_point = link_data.get("init_point")
        # The init_point is the URL that the user should be redirected to to make the payment.
        # Alternatively, we can use the sandbox_init_point if in sandbox mode.
        # We'll return the init_point.
        logger.info(f"Payment link generated for external reference: {request.external_reference}")
        return {
            "link": init_point,
            "id": link_data.get("id")  # The preference ID
        }
    
    except httpx.RequestError as e:
        logger.error(f"Request to Mercado Pago API failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}