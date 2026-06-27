import os
import hmac
import hashlib
import json
import logging
from fastapi import FastAPI, Request, HTTPException
import redis.asyncio as aioredis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ── Redis ────────────────────────────────────────────────────────────────────
redis_client = aioredis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True,
)

MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET")
SYSTEM_PAYMENT_URL = os.getenv("SYSTEM_PAYMENT_URL", "http://localhost:8003")

if not MP_WEBHOOK_SECRET:
    raise RuntimeError("MP_WEBHOOK_SECRET no configurado — abortando inicio de servicio")


def _validate_mercadopago_signature(body: bytes, x_signature: str, x_request_id: str) -> bool:
    """
    MercadoPago envia la firma en el header x-signature con formato:
    ts=<timestamp>,v1=<hash>
    El mensaje a firmar es: id:<data.id>;request-id:<x-request-id>;ts:<ts>;
    Referencia: https://www.mercadopago.com.pe/developers/es/docs/your-integrations/notifications/webhooks
    """
    try:
        parts = dict(item.split("=", 1) for item in x_signature.split(","))
        ts = parts.get("ts")
        v1 = parts.get("v1")

        if not ts or not v1:
            return False

        payload = json.loads(body)
        data_id = payload.get("data", {}).get("id", "")

        signed_template = f"id:{data_id};request-id:{x_request_id};ts:{ts};"

        expected = hmac.new(
            MP_WEBHOOK_SECRET.encode("utf-8"),
            signed_template.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, v1)

    except Exception as e:
        logger.error(f"Error validando firma MercadoPago: {e}")
        return False


@app.post("/webhook")
async def mercadopago_webhook(request: Request):
    """
    Recibe notificaciones de MercadoPago.
    Valida la firma HMAC segun el protocolo oficial de MercadoPago.
    Encola la notificacion en Redis para que system_payment la procese.
    Responde 200 inmediatamente para que MercadoPago no reintente.
    """
    body = await request.body()

    x_signature = request.headers.get("x-signature", "")
    x_request_id = request.headers.get("x-request-id", "")

    # Validar firma si el secret esta configurado y no estamos en modo testing
    if MP_WEBHOOK_SECRET and os.getenv("MP_SKIP_SIGNATURE_VALIDATION") != "true":
        if not x_signature:
            logger.warning("Webhook recibido sin header x-signature")
            raise HTTPException(status_code=403, detail="Firma requerida")

        if not _validate_mercadopago_signature(body, x_signature, x_request_id):
            logger.warning("Firma invalida en webhook de MercadoPago")
            raise HTTPException(status_code=403, detail="Firma invalida")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(f"JSON invalido recibido: {e}")
        raise HTTPException(status_code=400, detail="JSON invalido")

    topic = payload.get("type", "unknown")
    data_id = payload.get("data", {}).get("id", "sin-id")
    logger.info(f"Notificacion MercadoPago recibida — tipo: {topic} | id: {data_id}")

    # Encolar en Redis para procesamiento asincrono por system_payment
    await redis_client.lpush(
        "mp_payment_notifications",
        json.dumps({"payload": payload, "x_request_id": x_request_id}),
    )
    logger.info(f"Notificacion encolada en Redis — mp_payment_notifications")

    # MercadoPago requiere 200 inmediato para no reintentar
    return {"status": "ok"}


@app.get("/health")
async def health_check():
    try:
        await redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "healthy", "redis": redis_ok}
