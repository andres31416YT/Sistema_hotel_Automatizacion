import os
import json
import logging
import asyncio
from datetime import datetime, timezone
import httpx
import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ── Variables de entorno ─────────────────────────────────────────────────────
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
MP_API_URL      = os.getenv("MP_API_URL", "https://api.mercadopago.com/v1")
MP_SANDBOX      = os.getenv("MP_SANDBOX", "true").lower() == "true"
SYSTEM_PAYMENT_URL = os.getenv("SYSTEM_PAYMENT_URL", "http://localhost:8003")

DB_HOST     = os.getenv("DB_PAYMENTS_HOST", "db")
DB_PORT     = int(os.getenv("DB_PAYMENTS_PORT", 5433))
DB_NAME     = os.getenv("DB_PAYMENTS_NAME", "payments_db")
DB_USER     = os.getenv("DB_PAYMENTS_USER", "payments_user")
DB_PASSWORD = os.getenv("DB_PAYMENTS_PASSWORD")

REDIS_HOST     = os.getenv("REDIS_HOST", "redis")
REDIS_PORT     = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

if not MP_ACCESS_TOKEN:
    logger.error("MP_ACCESS_TOKEN no configurado")

# ── Conexiones ───────────────────────────────────────────────────────────────
redis_client: aioredis.Redis = None
db_pool: asyncpg.Pool = None


async def get_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True,
        )
    return redis_client


async def get_db() -> asyncpg.Pool:
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            min_size=2,
            max_size=10,
        )
    return db_pool


# ── Logica principal ─────────────────────────────────────────────────────────

async def fetch_payment_from_mp(payment_id: str) -> dict:
    """Consulta el estado real del pago en MercadoPago."""
    url = f"{MP_API_URL}/payments/{payment_id}"
    headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=10.0)

    if response.status_code != 200:
        raise Exception(f"MercadoPago respondio {response.status_code}: {response.text}")

    return response.json()


async def save_transaction(payment_data: dict):
    """
    Guarda la transaccion en DB Transaccional PostgreSQL Payments.
    Tabla: transacciones
    """
    pool = await get_db()

    payment_id       = str(payment_data.get("id"))
    status           = payment_data.get("status")           # approved, pending, rejected
    status_detail    = payment_data.get("status_detail")
    amount           = payment_data.get("transaction_amount")
    currency         = payment_data.get("currency_id")
    external_ref     = payment_data.get("external_reference")  # reserva_id
    payer_email      = payment_data.get("payer", {}).get("email")
    payment_method   = payment_data.get("payment_method_id")
    mp_preference_id = payment_data.get("preference_id")
    date_approved    = payment_data.get("date_approved")
    fecha_registro   = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO transacciones (
                payment_id, status, status_detail, monto, moneda,
                external_reference, payer_email, payment_method,
                mp_preference_id, date_approved, fecha_registro
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            ON CONFLICT (payment_id) DO UPDATE
                SET status        = EXCLUDED.status,
                    status_detail = EXCLUDED.status_detail,
                    date_approved = EXCLUDED.date_approved
            """,
            payment_id, status, status_detail, amount, currency,
            external_ref, payer_email, payment_method,
            mp_preference_id, date_approved, fecha_registro,
        )

    logger.info(f"Transaccion guardada en DB Payments — payment_id: {payment_id} | status: {status}")
    return status, external_ref


async def update_payment_cache(numero_wa: str, status: str):
    """
    Actualiza la key payment:{numero_wa} en DB Cache Redis ShortMemory.
    Solo si existe la key (el huesped tiene un pago en curso).
    """
    r = await get_redis()
    key = f"payment:{numero_wa}"
    existing = await r.get(key)
    if existing:
        data = json.loads(existing)
        data["status"] = status
        ttl = int(os.getenv("REDIS_TTL_PAYMENT", 900))
        await r.setex(key, ttl, json.dumps(data))
        logger.info(f"Cache Redis actualizado — {key} | status: {status}")


async def notify_core(external_reference: str, status: str, payment_id: str):
    """
    Notifica al System Core que el pago fue procesado
    para que confirme la reserva y notifique al huesped.
    """
    url = f"{CORE_URL}/payment-confirmed"
    payload = {
        "external_reference": external_reference,
        "status": status,
        "payment_id": payment_id,
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
        logger.info(f"System Core notificado — status: {response.status_code}")
    except Exception as e:
        logger.error(f"No se pudo notificar al System Core: {e}")


async def process_notification(raw: str):
    """
    Procesa una notificacion de la cola Redis mp_payment_notifications.
    1. Parsea el payload
    2. Consulta el estado real en MercadoPago
    3. Guarda en DB Payments
    4. Actualiza cache Redis
    5. Notifica al System Core
    """
    try:
        data       = json.loads(raw)
        payload    = data.get("payload", {})
        topic      = payload.get("type")
        data_id    = payload.get("data", {}).get("id")

        if topic != "payment" or not data_id:
            logger.info(f"Notificacion ignorada — tipo: {topic}")
            return

        logger.info(f"Procesando pago — payment_id: {data_id}")

        # Consultar estado real en MercadoPago
        payment_data = await fetch_payment_from_mp(str(data_id))

        # Guardar en DB Transaccional PostgreSQL Payments
        status, external_ref = await save_transaction(payment_data)

        # Actualizar cache Redis si corresponde
        if external_ref:
            await update_payment_cache(external_ref, status)

        # Solo notificar al Core si el pago fue aprobado
        if status == "approved":
            await notify_core(external_ref, status, str(data_id))

    except Exception as e:
        logger.error(f"Error procesando notificacion: {e}")


# ── Worker: consume cola Redis ───────────────────────────────────────────────

async def worker():
    """
    Worker continuo que consume la cola mp_payment_notifications de Redis.
    Bloquea esperando nuevas notificaciones con BRPOP (eficiente, sin polling).
    """
    logger.info("Worker System Payment iniciado — escuchando mp_payment_notifications")
    r = await get_redis()

    while True:
        try:
            result = await r.brpop("mp_payment_notifications", timeout=5)
            if result:
                _, raw = result
                await process_notification(raw)
        except Exception as e:
            logger.error(f"Error en worker: {e}")
            await asyncio.sleep(2)


# ── FastAPI lifecycle ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    await get_redis()
    await get_db()
    asyncio.create_task(worker())
    logger.info("System Payment listo")


@app.on_event("shutdown")
async def shutdown():
    global db_pool, redis_client
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()


@app.get("/health")
async def health_check():
    checks = {}
    try:
        r = await get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["db_payments"] = "ok"
    except Exception:
        checks["db_payments"] = "error"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, **checks}
