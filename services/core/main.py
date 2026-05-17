"""
System Core — Entry point FastAPI servidor HTTP para orquestar el Hotel.
Expone endpoints publicos y recibe notificaciones de pagos desde system_payment.
"""

import os
import json
import logging
import httpx
import redis
import asyncpg
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="System Core — Hotel Automatizacion")

# ── Config ────────────────────────────────────────────────────────────────────
CORE_PORT     = int(os.getenv("SYSTEM_CORE_PORT", 8080))
SYSTEM_PAYMENT_URL = os.getenv("SYSTEM_PAYMENT_URL", "http://payment-system:8003")
SYSTEM_WHATSAPP_SENDER_URL = os.getenv("SYSTEM_WHATSAPP_SENDER_URL", "http://whatsapp-sender:8001")

DB_HOTEL = {
    "host":     os.getenv("DB_HOTEL_HOST", "db_hotel"),
    "port":     int(os.getenv("DB_HOTEL_PORT", 5432)),
    "user":     os.getenv("DB_HOTEL_USER", "hotel_user"),
    "password": os.getenv("DB_HOTEL_PASSWORD", "hotel_password"),
    "database": os.getenv("DB_HOTEL_NAME", "hotel_db"),
}
DB_PAYMENTS = {
    "host":     os.getenv("DB_PAYMENTS_HOST", "db_payments"),
    "port":     int(os.getenv("DB_PAYMENTS_PORT", 5432)),
    "user":     os.getenv("DB_PAYMENTS_USER", "payments_user"),
    "password": os.getenv("DB_PAYMENTS_PASSWORD", "payments_password"),
    "database": os.getenv("DB_PAYMENTS_NAME", "payments_db"),
}
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

# ── Autenticacion ──────────────────────────────────────────────────────────────
from core_auth_settings import is_admin  # noqa: E402


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    checks = {}

    # Redis
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD,
                         socket_connect_timeout=3, decode_responses=True)
        r.ping()
        checks["redis"] = "ok"
        r.close()
    except Exception:
        checks["redis"] = "error"

    # DB Hotel
    try:
        pool = await asyncpg.create_pool(**DB_HOTEL, timeout=3, min_size=1, max_size=2)
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        await pool.close()
        checks["db_hotel"] = "ok"
    except Exception:
        checks["db_HOTEL"] = "error"

    # DB Payments
    try:
        pool = await asyncpg.create_pool(**DB_PAYMENTS, timeout=3, min_size=1, max_size=2)
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        await pool.close()
        checks["db_payments"] = "ok"
    except Exception:
        checks["db_payments"] = "error"

    # System Payment
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{SYSTEM_PAYMENT_URL}/health")
            checks["system_payment"] = "ok" if resp.status_code == 200 else "degraded"
    except Exception:
        checks["system_payment"] = "error"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, **checks}


# ── Autenticacion de administradores ────────────────────────────────────────────

class AdminCheckRequest(BaseModel):
    phone: str


@app.post("/admin/check", response_model=dict)
async def admin_check(body: AdminCheckRequest):
    """
    Verifica si un numero de WhatsApp pertenece a un administrador.
    Administradores pueden agregarse/removerse via ADMIN_PHONES en el .env del core.
    """
    result = is_admin(body.phone)
    return {"phone": body.phone, "is_admin": result}


# ── Endpoint llamado por system_payment cuando un pago se confirma ─────────────

@app.post("/payment-confirmed")
async def payment_confirmed(request: Request):
    """
    Recibe la notificacion de pago aprobado desde system_payment.
    Confirma la reserva correspondiente y dispara la notificacion por WhatsApp
    por el huesped.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalido")

    external_reference = body.get("external_reference")
    status = body.get("status")
    payment_id = body.get("payment_id")

    logger.info(f"[CORE] payment-confirmed recibido — ref={external_reference} status={status}")

    if not external_reference:
        raise HTTPException(status_code=400, detail="external_reference es obligatorio")

    # Guardar estado del pago
    if external_reference not in _reservas:
        _reservas[external_reference] = {}

    _reservas[external_reference]["payment_status"] = status
    _reservas[external_reference]["payment_id"] = payment_id
    _reservas[external_reference]["estado"] = "confirmada" if status == "approved" else "pendiente"

    if status == "approved":
        # TODO: cuando el core tenga el modelo de BD de reservas, actualizarlo aqui.
        logger.info(f"[CORE] Reserva {external_reference} CONFIRMADA por pago {payment_id}")

        # Enviar mensaje de confirmacion por WhatsApp
        await _enviar_confirmacion_whatsapp(external_reference, payment_id)

    return {
        "status": "processed",
        "external_reference": external_reference,
        "estado": _reservas[external_reference]["estado"],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _enviar_confirmacion_whatsapp(reserva_id: str, payment_id: str):
    """
    Llama al System WhatsApp Sender para enviar un mensaje de confirmacion
    al huesped. Usa el numero de telefono guardado en la clave payment:{reserva_id}
    del cache Redis.
    """
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                    password=REDIS_PASSWORD, decode_responses=True)
    try:
        key = f"payment:{reserva_id}"
        cached = r.get(key)
        if not cached:
            logger.warning(f"[CORE] No hay clave {key} en Redis — no se envia WhatsApp")
            return

        data = json.loads(cached)
        numero_wa = data.get("numero_wa")
        nombre    = data.get("nombre", "Estimado huesped")

        mensaje = (
            f"Estimado {nombre}, tu pago ha sido confirmado exitosamente. "
            f"Tu reserva {reserva_id} esta activa. "
            f"Te esperamos. "
        )
        payload = {"to": numero_wa, "type": "text",
                   "text": {"body": mensaje}}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SYSTEM_WHATSAPP_SENDER_URL}/send-message", json=payload
            )
        if resp.status_code == 200:
            logger.info(f"[CORE] WhatsApp enviado a {numero_wa} — reserva {reserva_id}")
        else:
            logger.error(f"[CORE] Error enviando WhatsApp: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"[CORE] Error en enviar_confirmacion_whatsapp: {e}")
    finally:
        r.close()


# ── Info ──────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"service": "core", "status": "running", "port": CORE_PORT}
