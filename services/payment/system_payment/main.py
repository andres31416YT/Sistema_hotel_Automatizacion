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
MP_PUBLIC_KEY = os.getenv('MP_PUBLIC_KEY')  # Not used in server-side operations, but kept for completeness
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
    # Additional fields as needed

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
    Record a payment in the local database (Redis for now, but in a real system this would be a proper DB).
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

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}