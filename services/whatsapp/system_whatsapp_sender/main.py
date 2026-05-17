import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# WhatsApp Business API configuration
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
WHATSAPP_API_URL = os.getenv('WHATSAPP_API_URL', 'https://graph.facebook.com/v18.0')

if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
    logger.error("WhatsApp credentials not properly configured")

class MessageRequest(BaseModel):
    to: str  # Recipient phone number in international format without +
    type: str  # Message type (text, template, etc.)
    # For text messages
    text: dict = None
    # For template messages
    template: dict = None

@app.post("/send-message")
async def send_whatsapp_message(request: MessageRequest):
    """
    Send a message via WhatsApp Business API.
    """
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        logger.error("WhatsApp credentials not configured")
        raise HTTPException(status_code=500, detail="WhatsApp service not configured")
    
    url = f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Prepare the payload based on message type
    payload = {
        "messaging_product": "whatsapp",
        "to": request.to,
        "type": request.type
    }
    
    if request.type == "text" and request.text:
        payload["text"] = request.text
    elif request.type == "template" and request.template:
        payload["template"] = request.template
    else:
        raise HTTPException(status_code=400, detail="Invalid message type or missing content")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=10.0)
        
        if response.status_code != 200:
            logger.error(f"Failed to send WhatsApp message: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to send message: {response.text}"
            )
        
        result = response.json()
        logger.info(f"WhatsApp message sent successfully: {result}")
        return {"status": "sent", "message_id": result.get("messages", [{}])[0].get("id")}
    
    except httpx.RequestError as e:
        logger.error(f"Request to WhatsApp API failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}