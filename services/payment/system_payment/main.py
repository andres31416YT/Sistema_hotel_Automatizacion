import os
import json
import logging
import asyncio
from datetime import datetime, timezone
import httpx
import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ── Variables de entorno ─────────────────────────────────────────────────────
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
MP_API_URL      = os.getenv("MP_API_URL", "https://api.mercadopago.com")
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

CORE_URL       = os.getenv("CORE_URL")
if not CORE_URL:
    raise RuntimeError("CORE_URL no configurado — abortando inicio de servicio")

if not MP_ACCESS_TOKEN:
    raise RuntimeError("MP_ACCESS_TOKEN no configurado — abortando inicio de servicio")

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
        max_retries = 10
        for attempt in range(max_retries):
            try:
                db_pool = await asyncpg.create_pool(
                    host=DB_HOST,
                    port=DB_PORT,
                    database=DB_NAME,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    min_size=2,
                    max_size=10,
                )
                logger.info(f"DB connection established after {attempt+1} attempt(s)")
                return db_pool
            except Exception as e:
                logger.warning(f"DB connection attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
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
    fecha_registro   = datetime.utcnow()
    _dt_approved     = datetime.fromisoformat(date_approved.replace("Z", "+00:00")).replace(tzinfo=None) \
                       if date_approved else None

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO transacciones (
                payment_id, status, status_detail, amount, currency,
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
            mp_preference_id, _dt_approved, fecha_registro,
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
    2. Consulta el estado real en MercadoPago (con fallback a pending)
    3. Guarda en DB Payments
    4. Actualiza cache Redis
    5. Notifica al Core si fue aprobado
    """
    # ── 1. Parsear ──────────────────────────────────────────────────────────────
    try:
        data    = json.loads(raw)
        payload = data.get("payload", {})
        topic   = payload.get("type")
        data_id = payload.get("data", {}).get("id")
    except Exception as e:
        logger.error(f"JSON invalido en notificacion: {e}")
        return

    if topic != "payment" or not data_id:
        logger.info(f"Notificacion ignorada — tipo: {topic}")
        return

    logger.info(f"Procesando pago — payment_id: {data_id}")

    # ── 2. Consultar estado en MP (con fallback) ────────────────────────────────
    payment_data: dict = {}
    try:
        payment_data = await fetch_payment_from_mp(str(data_id))
    except Exception as e:
        logger.warning(
            f"No se pudo consultar MP para payment_id={data_id}: {e}. "
            "Guardando registro como 'pending' en DB."
        )
        payment_data = {
            "id": data_id,
            "status": "pending",
            "status_detail": "pendiente_de_confirmacion_mp",
            "transaction_amount": 0.0,
            "currency_id": "PEN",
            "external_reference": None,
            "payer": {},
        }

    # ── 3–5. Guardar, actualizar cache, notificar ───────────────────────────────
    try:
        status, external_ref = await save_transaction(payment_data)

        if external_ref:
            await update_payment_cache(external_ref, status)

        if status == "approved":
            await notify_core(external_ref, status, str(data_id))

    except Exception as e:
        logger.error(f"Error guardando notificacion payment_id={data_id}: {e}")


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


# ── Endpoints REST para consumo de MCP / Core ────────────────────────────────

class GenerateLinkRequest(BaseModel):
    external_reference: str
    amount: float
    currency: str = "PEN"
    description: str = ""
    payer_email: str = None
    payer_name: str = None


class PaymentStatusResponse(BaseModel):
    external_reference: str
    status: str
    payment_id: str = None
    amount: float = None
    currency: str = None
    date_approved: str = None


class PaymentConfirmedRequest(BaseModel):
    external_reference: str
    status: str
    payment_id: str = None


@app.post("/generate-link", response_model=dict)
async def generate_payment_link(request: GenerateLinkRequest):
    if not MP_ACCESS_TOKEN:
        logger.error("[MP ERROR] MP_ACCESS_TOKEN no configurado")
        raise HTTPException(status_code=500, detail="MP_ACCESS_TOKEN no configurado")

    url = f"{MP_API_URL}/checkout/preferences"
    headers = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    notification_url_env = os.getenv(
        "MERCADO_PAGO_NOTIFICATION_URL",
        os.getenv("WEBHOOK_PUBLIC_URL", ""),
    )

    payload = {
        "items": [
            {
                "title": request.description or f"Reserva {request.external_reference}",
                "quantity": 1,
                "unit_price": request.amount,
                "currency_id": request.currency,
            }
        ],
        "external_reference": request.external_reference,
        "auto_return": "approved",
        "back_urls": {
            "success": os.getenv("BACK_URL_SUCCESS", "https://www.tuhotel.com/pago-exitoso"),
            "failure": os.getenv("BACK_URL_FAILURE", "https://www.tuhotel.com/pago-fallido"),
            "pending": os.getenv("BACK_URL_PENDING", "https://www.tuhotel.com/pago-pendiente"),
        },
    }
    if notification_url_env:
        payload["notification_url"] = notification_url_env
    if request.payer_email:
        payload["payer"] = {"email": request.payer_email}
    if request.payer_name:
        payload.setdefault("payer", {})["name"] = request.payer_name

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload, timeout=15.0)

    if response.status_code not in (200, 201):
        logger.error(f"[MP ERROR] status={response.status_code} body={response.text[:500]}")
        raise HTTPException(
            status_code=response.status_code,
            detail=f"MercadoPago rechazo la preferencia: {response.text}",
        )

    data = response.json()
    init_point = data.get("init_point") or data.get("sandbox_init_point")
    preference_id = data.get("id")

    if not init_point:
        logger.error(f"[MP ERROR] status={response.status_code} body={response.text[:500]}")
        raise HTTPException(status_code=500, detail="MP no devolvio init_point")

    r = await get_redis()
    await r.hset(
        f"payment_preference:{request.external_reference}",
        mapping={
            "preference_id": preference_id,
            "amount": str(request.amount),
            "currency": request.currency,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    await r.expire(f"payment_preference:{request.external_reference}", int(os.getenv("REDIS_TTL_PAYMENT", 900)))

    logger.info(f"Link generado — ref={request.external_reference} preference={preference_id}")
    return {"link": init_point, "preference_id": preference_id, "external_reference": request.external_reference}


@app.get("/payment-status/{external_reference}", response_model=dict)
async def get_payment_status(external_reference: str):
    r = await get_redis()
    cached = await r.hgetall(f"payment_preference:{external_reference}")
    if cached:
        return {
            "external_reference": external_reference,
            "status": cached.get("status", "pending"),
            "preference_id": cached.get("preference_id"),
            "amount": float(cached.get("amount", 0)),
            "currency": cached.get("currency"),
            "date_approved": cached.get("date_approved"),
            "source": "redis",
        }

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT payment_id, status, monto, moneda, date_approved "
            "FROM transacciones WHERE external_reference = $1 ORDER BY fecha_registro DESC LIMIT 1",
            external_reference,
        )
    if row:
        return {
            "external_reference": external_reference,
            "status": row["status"],
            "payment_id": row["payment_id"],
            "amount": float(row["monto"]),
            "currency": row["moneda"],
            "date_approved": row["date_approved"].isoformat() if row["date_approved"] else None,
            "source": "db_payments",
        }
    raise HTTPException(status_code=404, detail="Pago no encontrado")


@app.post("/payment-confirmed", response_model=dict)
async def payment_confirmed(body: PaymentConfirmedRequest):
    """
    Endpoint llamado por el System Core.
    Actualiza el estado del pago en cache y registra si viene un pago aprobado.
    """
    logger.info(
        f"payment-confirmed recibido — ref={body.external_reference} status={body.status} payment_id={body.payment_id}"
    )

    r = await get_redis()

    # Actualizar cache de preferencia
    cache_key = f"payment_preference:{body.external_reference}"
    if await r.exists(cache_key):
        await r.hset(cache_key, "status", body.status)

    return {"status": "processed", "external_reference": body.external_reference}