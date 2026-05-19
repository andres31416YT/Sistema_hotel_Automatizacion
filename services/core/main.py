"""
System Core — Entry point FastAPI servidor HTTP para orquestar el Hotel.
Expone endpoints publicos y recibe notificaciones de pagos desde system_payment.
"""

import os
import json
import asyncio
import sys
import re
import logging
import httpx
import redis
import redis.asyncio as aioredis
import asyncpg
from collections import deque
from datetime import datetime, timezone
from typing import Any
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

# ── MCP Servers ────────────────────────────────────────────────────────────────
from customer_service.mcp_servers.mcp_payments import McpPayments  # noqa: E402

sys.stdout.reconfigure(line_buffering=True)

logger = logging.getLogger("core")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.DEBUG)



app = FastAPI(title="System Core — Hotel Automatizacion")

# ── Config ────────────────────────────────────────────────────────────────────
CORE_PORT     = int(os.getenv("SYSTEM_CORE_PORT", 8080))
SYSTEM_PAYMENT_URL        = os.getenv("SYSTEM_PAYMENT_URL",        "http://payment-system:8003")
SYSTEM_WHATSAPP_SENDER_URL = os.getenv("SYSTEM_WHATSAPP_SENDER_URL", "http://whatsapp-sender:8001")
OLLAMA_API_URL            = os.getenv("OLLAMA_API_URL",            "http://ollama:11434")
OLLAMA_MODEL              = os.getenv("OLLAMA_MODEL",              "qwen2.5:3b-instruct")
CONTEXT_WINDOW_SIZE       = int(os.getenv("CONTEXT_WINDOW_SIZE",  80))   # mensajes de historial por usuario
RESERVATION_AMOUNT        = float(os.getenv("RESERVATION_AMOUNT", "150.0"))  # monto default para pago de reserva
RESERVATION_DESCRIPTION   = os.getenv("RESERVATION_DESCRIPTION", "Reserva de habitacion")  # descripcion del pago

DB_HOTEL = {
    "host":     os.getenv("DB_HOTEL_HOST"),
    "port":     int(os.getenv("DB_HOTEL_PORT", 5432)),
    "user":     os.getenv("DB_HOTEL_USER"),
    "password": os.getenv("DB_HOTEL_PASSWORD"),
    "database": os.getenv("DB_HOTEL_NAME"),
}

if not all([DB_HOTEL["host"], DB_HOTEL["user"], DB_HOTEL["password"], DB_HOTEL["database"]]):
    raise RuntimeError("Faltan variables de entorno de DB_HOTEL. "
                        "Verificar DB_HOTEL_HOST, DB_HOTEL_USER, DB_HOTEL_PASSWORD, DB_HOTEL_NAME en el .env")

DB_PAYMENTS = {
    "host":     os.getenv("DB_PAYMENTS_HOST"),
    "port":     int(os.getenv("DB_PAYMENTS_PORT", 5432)),
    "user":     os.getenv("DB_PAYMENTS_USER"),
    "password": os.getenv("DB_PAYMENTS_PASSWORD"),
    "database": os.getenv("DB_PAYMENTS_NAME"),
}

if not all([DB_PAYMENTS["host"], DB_PAYMENTS["user"], DB_PAYMENTS["password"], DB_PAYMENTS["database"]]):
    raise RuntimeError("Faltan variables de entorno de DB_PAYMENTS. "
                        "Verificar DB_PAYMENTS_HOST, DB_PAYMENTS_USER, DB_PAYMENTS_PASSWORD, DB_PAYMENTS_NAME en el .env")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

# ── Autenticacion ──────────────────────────────────────────────────────────────
from core_auth_settings import is_admin, get_admin_phones  # noqa: E402

# ── Almacenamiento en memoria ───────────────────────────────────────────────────
_reservas: dict = {}
_reservas_lock = asyncio.Lock()

# Memoria de corto plazo: historial de conversación por número de teléfono
# Cada entrada es una lista de dicts {role, content}
_chat_history: dict[str, deque] = {}
_chat_history_lock = asyncio.Lock()


def _format_history(history: list[dict]) -> str:
    """Formatea el historial como string para incluirlo en el prompt del LLM."""
    if not history:
        return ""
    lines = ["[Historial de conversacion anterior]"]
    for msg in history:
        role = "Huesped" if msg["role"] == "user" else "Asistente"
        lines.append(f"{role}: {msg['content']}")
    lines.append("[Fin del historial]")
    return "\n".join(lines)


async def _get_history(phone: str, redis_client: aioredis.Redis) -> list[dict]:
    """Obtiene el historial de conversación de Redis (persistente) + memoria en caliente."""
    async with _chat_history_lock:
        if phone in _chat_history:
            return list(_chat_history[phone])

    # Fallback a Redis
    try:
        raw = await asyncio.wait_for(redis_client.get(f"chat_history:{phone}"), timeout=5.0)
        if raw:
            data = json.loads(raw)
            # Recalentar buffer en memoria
            async with _chat_history_lock:
                _chat_history[phone] = deque(data, maxlen=CONTEXT_WINDOW_SIZE * 2)
            return data
    except Exception:
        pass
    return []


async def _save_turn(phone: str, user_msg: str, assistant_reply: str, redis_client: aioredis.Redis) -> None:
    """Guarda el turno completo en Redis y actualiza el buffer en memoria."""
    async with _chat_history_lock:
        if phone not in _chat_history:
            _chat_history[phone] = deque(maxlen=CONTEXT_WINDOW_SIZE * 2)
        _chat_history[phone].append({"role": "user",      "content": user_msg})
        _chat_history[phone].append({"role": "assistant", "content": assistant_reply})

    try:
        history = list(_chat_history[phone])
        await redis_client.set(
            f"chat_history:{phone}",
            json.dumps(history),
            ex=int(os.getenv("REDIS_TTL_CHAT", 1800)),
        )
    except Exception:
        pass


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

    # Ollama AI
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_API_URL}/api/tags")
            checks["ollama"] = "ok" if resp.status_code == 200 else "degraded"
    except Exception:
        checks["ollama"] = "error"

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

    # Actualizar cache de preferencia de pago (clave: payment_preference:{external_reference})
    # Nota: payment_preference guarda amount, currency, preference_id, status, created_at.
    # El numero de telefono del huesped esta en otra clave (payment:{id} o perfil de usuario).
    try:
        r_cache = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                                 password=REDIS_PASSWORD, decode_responses=True,
                                 socket_connect_timeout=3)

        pref_key = f"payment_preference:{external_reference}"
        exists = await r_cache.exists(pref_key)
        logger.info(f"[CORE] Redis update — key={pref_key} exists={exists} → {status}")
        if exists:
            await r_cache.hset(pref_key, "status", status)
            if status == "approved":
                await r_cache.hset(pref_key, "date_approved",
                                   datetime.now(timezone.utc).isoformat())
                logger.info(f"[CORE] Redis date_approved actualizado en {pref_key}")
            ttl = await r_cache.ttl(pref_key)
            if ttl == -1:
                await r_cache.expire(pref_key, int(os.getenv("REDIS_TTL_PAYMENT", 900)))
        await r_cache.close()
    except Exception as e:
        logger.warning(f"[CORE] Redis cache fallo: {e}")

    # Guardar estado del pago (protegido contra condiciones de carrera concurrentes)
    async with _reservas_lock:
        if external_reference not in _reservas:
            _reservas[external_reference] = {}

        _reservas[external_reference]["payment_status"] = status
        _reservas[external_reference]["payment_id"] = payment_id
        _reservas[external_reference]["estado"] = "confirmada" if status == "approved" else "pendiente"
        estado_final = _reservas[external_reference]["estado"]

    if status == "approved":
        # TODO: cuando el core tenga el modelo de BD de reservas, actualizarlo aqui.
        logger.info(f"[CORE] Reserva {external_reference} CONFIRMADA por pago {payment_id}")

        # Actualizar cache de preferencia de pago (si existe la clave)
    try:
        r_cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                              password=REDIS_PASSWORD, decode_responses=True)
        cache_key = f"payment_preference:{external_reference}"
        if await r_cache.exists(cache_key):
            await r_cache.hset(cache_key, "status", status)
            ttl = await r_cache.ttl(cache_key)
            if ttl == -1:
                await r_cache.expire(cache_key, int(os.getenv("REDIS_TTL_PAYMENT", 900)))
        r_cache.close()
    except Exception:
        pass  # No bloquear el flujo si Redis no esta disponible

    # Enviar mensaje de confirmacion por WhatsApp
        await _enviar_confirmacion_whatsapp(external_reference, payment_id)

    return {
        "status": "processed",
        "external_reference": external_reference,
        "estado": estado_final,
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


# ── Worker WhatsApp — consume cola whatsapp_in ────────────────────────────────
# Cada mensaje entrante por WhatsApp se encola en 'whatsapp_in'.
# Este worker lo consume con BRPOP, valida seguridad y responde.

def _normalize_phone(raw: str) -> str:
    """Elimina espacios y guiones del numero de telefono."""
    return re.sub(r"[^\d]", "", raw)


def _parse_wa_message(raw) -> dict:
    """Extrae phone, name, text de un evento de webhook de WhatsApp."""
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        raw = (raw or "").strip()
        if not raw:
            logger.warning("[WA WORKER] Mensaje vacio — ignorado")
            return {}
        payload = json.loads(raw)
        entry   = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value   = changes.get("value", {})
        logger.debug(f"[WA PARSER] value keys: {list(value.keys())}")
        # Filtrar eventos de estado sin mensaje
        if "statuses" in value and not value.get("messages"):
            logger.debug("[WA PARSER] Es evento de estado, ignorado")
            return {}
        contact = value.get("contacts", [{}])[0]
        msg_e   = value.get("messages", [{}])[0]
        wa_id   = contact.get("wa_id", "")
        from_f  = msg_e.get("from", "")
        phone   = _normalize_phone(wa_id or from_f)
        name    = (contact.get("profile", {}) or {}).get("name") or "Usuario"
        text    = ((msg_e.get("text") or {}).get("body") or "").strip()
        logger.debug(f"[WA PARSER] wa_id={wa_id!r} from={from_f!r} phone={phone!r} text={text!r}")
        if not phone or not text:
            logger.warning(f"[WA PARSER] Falta phone o text — phone={phone!r} text={text!r}")
            return {}
        return {"phone": phone, "name": name, "text": text, "msg_id": msg_e.get("id", "")}
    except Exception as e:
        logger.warning(f"[WA PARSER] Error: {e}")
        return {}


async def _send_wa_message(to: str, text: str) -> None:
    """Envía un mensaje de texto al huésped por WhatsApp Sender."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SYSTEM_WHATSAPP_SENDER_URL}/send-message",
                json={"to": to, "type": "text", "text": {"body": text}},
            )
        if resp.status_code == 200:
            logger.info(f"[WA WORKER] Enviado a {to}")
        else:
            logger.error(
                f"[WA WORKER] Error enviando a {to}: {resp.status_code} {resp.text[:200]}"
            )
    except Exception as e:
        logger.error(f"[WA WORKER] Exception enviando a {to}: {e}")


async def _build_reply(text: str, name: str, history: list[dict] | None = None) -> str:
    """
    Genera una respuesta usando Ollama (LLM local) via /v1/chat/completions.
    Incluye el historial de conversación del usuario para mantener el contexto.
    Si Ollama no esta disponible, cae a reglas predefinidas.
    """
    from prompts.customer_service.agents import PROMPT_LLM_HUESPED  # noqa

    # ── Contexto de fecha/hora actual ───────────────────────────────────────────
    from customer_service.mcp_servers.mcp_datetime import get_current_datetime, get_day_of_week  # noqa
    _dt_info  = get_current_datetime(format="pretty")
    _dt_date  = get_current_datetime(format="date")
    _dt_day   = get_day_of_week()
    _date_block = (
        f"FECHA Y HORA ACTUAL (zona horaria Peru, UTC-5):\n"
        f"  Ahora es: {_dt_info['result']}\n"
        f"  Hoy es:   {_dt_day['result']}, {_dt_date['result']}\n"
        f"Usa esta informacion para calcular fechas, vencimientos, dias de la semana "
        f"y horarios. Siempre que el huesped pregunte por la fecha, hora o dia de hoy, "
        f"usa los valores de arriba (no inventes ni uses valores hardcodeados).\n"
    )

    # ── Construir mensajes en formato OpenAI ────────────────────────────────────
    _system_prompt = f"{PROMPT_LLM_HUESPED}\n\n{_date_block}"
    messages: list[dict] = [{"role": "system", "content": _system_prompt}]
    if history:
        messages.extend(history[-(CONTEXT_WINDOW_SIZE * 2):])  # últimos N turnos
    messages.append({"role": "user", "content": text})

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{OLLAMA_API_URL}/v1/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                },
            )
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                reply = (choices[0].get("message", {}).get("content") or "").strip()
                if reply:
                    return reply
        else:
            logger.warning(f"[LLM] Ollama /v1/chat/completions status={resp.status_code}")
    except Exception as e:
        logger.warning(f"[LLM] Ollama fallo ({e}), usando fallback")

    # ── Fallback a reglas predefinidas ───────────────────────────────────────────
    t = text.lower().strip()
    if any(w in t for w in ["hola", "buenas", "buenos dias", "buenos dias", "buenos dias", "buenos dias"]):
        return (
            f"Hola {name}! Bienvenido al hotel. "
            "Escribe 'disponibilidad', 'pago' o 'info' para continuar."
        )
    if any(w in t for w in ["disponibilidad", "habitacion", "habitaciones", "disponible"]):
        return (
            "Para verificar disponibilidad necesito:\n"
            "1. Fecha de check-in\n"
            "2. Tipo de habitacion (simple, doble, suite)\n"
            "3. Numero de huespedes\n\n"
            "Ejemplo: '25 de mayo, doble, 2 personas'"
        )
    if any(w in t for w in ["pago", "pagar", "link", "transferencia"]):
        return (
            "Para generar tu link de pago necesito:\n"
            "1. Monto en soles\n"
            "2. Numero de reserva o DNI\n\n"
            "Ejemplo: 'Pagar 150 soles, reserva 456'"
        )
    if any(w in t for w in ["info", "informacion", "detalles", "horario", "desayuno", "wifi"]):
        return (
            "Informacion del hotel:\n"
            "Check-in: 3:00 PM | Check-out: 11:00 AM\n"
            "Desayuno: 7:00 AM - 10:00 AM\n"
            "WiFi: gratuito en todas las areas\n"
            "Estacionamiento: incluido"
        )
    if "admin" in t:
        return "Un administrador te contactara en breve."

    return (
        f"Gracias por tu mensaje, {name}! "
        "Escribe 'disponibilidad', 'pago' o 'info' para comenzar."
    )


async def _build_reply_admin(text: str, name: str, history: list[dict] | None = None, is_adm: bool = False) -> str:
    """
    Genera una respuesta para administradores usando Ollama via /v1/chat/completions.
    Prompt con contexto de admin: acceso completo, puede ver todo.
    Incluye historial de conversación para mantener el contexto.
    Consultas de datos conocidas se ejecutan directamente sin Ollama.
    """
    from prompts.admin_service.agents import PROMPT_LLM_ADMIN  # noqa

    async def _exec_sql(query: str) -> dict:
        """Ejecuta SQL de lectura contra la DB del hotel."""
        try:
            dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(**DB_HOTEL)
            conn = await asyncpg.connect(dsn, timeout=15)
            rows = await conn.fetch(query)
            cols = list(rows[0].keys()) if rows else []
            return {"ok": True, "columns": cols, "rows": [dict(r) for r in rows], "count": len(rows)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            await conn.close()

    # ── Respuesta directa por defecto: ejecutar schema o datos sin Ollama ─────
    logger.info("[ADMIN] _build_reply_admin INICIO: text=%r", text[:80])

    # Paso 1: consultas directas conocidas (ver reservas, habitaciones, etc.)
    direct = _ejecutar_consulta_admin(text)
    if direct is not None:
        logger.info("[ADMIN] Consulta directa ejecutada (%d chars)", len(direct))
        return direct

    # Paso 2: si el admin pide estructura/ver tablas/schema, ejecutar
    # consulta contra information_schema sin depender de Ollama
    t = text.lower().strip()
    if any(k in t for k in [
        "estructura", "esquema", "schema", "tablas", "tabla",
        "ver toda", "todas las", "todos los", "mostrar toda",
        "base de datos", "columnas", "campos",
    ]):
        logger.info("[ADMIN] Consulta de estructura detectada — ejecutando info_schema")
        try:
            result = await _exec_sql(
                "SELECT table_name, column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "ORDER BY table_name, ordinal_position"
            )
            if not result.get("ok"):
                return f"[ERROR] {result.get('error')}"
            rows = result["rows"]
            from collections import defaultdict
            tables = defaultdict(list)
            for row in rows:
                tables[row["table_name"]].append(f"{row['column_name']} ({row['data_type']})")
            lines = [f"Base de datos — {len(tables)} tabla(s):\n"]
            for table in sorted(tables):
                cols = tables[table]
                lines.append(f"  {table} ({len(cols)} columnas):")
                for c in cols:
                    lines.append(f"    - {c}")
                lines.append("")
            return "\n".join(lines)
        except Exception as exc:
            logger.warning("[ADMIN] Error info_schema: %s", exc)
            return f"Error obteniendo esquema: {exc}"

    logger.info("[ADMIN] No es consulta de estructura ni datos directos, pasando a Ollama.")

    # ── Contexto de fecha/hora actual ───────────────────────────────────────────
    from customer_service.mcp_servers.mcp_datetime import get_current_datetime, get_day_of_week  # noqa
    _dt_info  = get_current_datetime(format="pretty")
    _dt_date  = get_current_datetime(format="date")
    _dt_day   = get_day_of_week()
    _date_block = (
        f"FECHA Y HORA ACTUAL (zona horaria Peru, UTC-5):\n"
        f"  Ahora es: {_dt_info['result']}\n"
        f"  Hoy es:   {_dt_day['result']}, {_dt_date['result']}\n"
        f"Usa esta informacion para calcular vencimientos, cierres de dia y "
        f"operaciones con fechas. Nunca inventes fechas ni uses valores hardcodeados.\n"
    )

    # ── Construir mensajes en formato OpenAI ────────────────────────────────────
    # Para el admin se usa SOLO el prompt de sistema + la consulta actual.
    # El historial de admin se omite intencionalmente para que Ollama 3B no se cuelgue.
    _system_prompt = f"{PROMPT_LLM_ADMIN}\n\n{_date_block}"
    messages: list[dict] = [{"role": "system", "content": _system_prompt}]
    if not is_adm and history:
        messages.extend(history[-(CONTEXT_WINDOW_SIZE * 2):])  # clientes: historial completo
    messages.append({"role": "user", "content": text})
    logger.debug("[ADMIN] Mensajes enviados a Ollama: %d (is_adm=%s, hist_len=%d)",
                  len(messages), is_adm, len(history))

    _tools = [
        {
            "type": "function",
            "function": {
                "name": "execute_sql",
                "description": (
                    "Ejecuta una consulta SQL de LECTURA (SELECT/SHOW/WITH) sobre la base de datos "
                    "del hotel. Usala cuando el administrador pida ver, listar o consultar datos "
                    "(reservas, habitaciones, pagos, huespedes, transacciones). "
                    "BLOQUEA INSERT/UPDATE/DELETE/DROP. "
                    "Devuelve columnas + filas como lista de diccionarios."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Consulta SQL de lectura"},
                        "params": {"type": "array", "items": {"type": "string"}, "description": "Parametros opcionales para la consulta"},
                    },
                    "required": ["query"],
                },
            },
        },
    ]

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{OLLAMA_API_URL}/v1/chat/completions",
                json={
                    "model":  OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "tools":  _tools,
                },
            )
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        fn_name = fn.get("name", "")
                        if fn_name == "execute_sql":
                            try:
                                args = json.loads(fn.get("arguments", "{}"))
                                q = args.get("query", "")
                                p = args.get("params")
                                logger.info("[LLM-ADMIN] Ejecutando SQL: %s", q[:120])
                                result = execute_sql(q, p)
                                if result.get("ok"):
                                    rows = result.get("rows", [])
                                    cols = result.get("columns", [])
                                    cnt  = result.get("count", 0)
                                    if cnt == 0:
                                        return "La consulta se ejecuto correctamente pero no hay resultados para mostrar."
                                    lines = [f"**{cnt} resultado(s) encontrado(s):**\n",
                                             "| " + " | ".join(str(c) for c in cols) + " |",
                                             "|" + "|".join("---" for _ in cols) + "|"]
                                    for row in rows[:50]:
                                        lines.append("| " + " | ".join(str(row.get(c,"")) for c in cols) + " |")
                                    if cnt > 50:
                                        lines.append(f"\n(Se muestran los primeros 50 de {cnt} registros. "
                                                      "Pide 'ver todos' para ampliar.)")
                                    return "\n".join(lines)
                                else:
                                    return f"Error en la consulta SQL: {result.get('error')}"
                            except Exception as _exc:
                                logger.warning("[LLM-ADMIN] Error ejecutando SQL: %s", _exc)
                                return f"Error ejecutando la consulta: {_exc}"
                reply = (msg.get("content") or "").strip()
                if reply:
                    return reply
    except Exception as e:
        logger.warning(f"[LLM-ADMIN] Ollama fallo ({e})")

    return f"Recibi tu consulta, {name}. Estoy procesando la solicitud administrativa."


# ── Ejecucion directa de consultas para admin (sin Ollama) ─────────────────────
# Reglas de consulta directa: palabras clave que gatillan ejecucion inmediata
# de SQL sobre la DB de hotel, sin pasar por Ollama.

_CONSULTA_RESERVAS = (
    "ver todas las reservas", "mostrar todas las reservas", "listar todas las reservas",
    "ver reservas", "mostrar reservas", "listar reservas",
    "todas las reservas", "reservas activas",
)
_CONSULTA_HABITACIONES = (
    "ver todas las habitaciones", "mostrar todas las habitaciones",
    "listar todas las habitaciones", "ver habitaciones",
    "habitaciones disponibles", "habitaciones libres",
)
_CONSULTA_CLIENTES = (
    "ver todos los clientes", "mostrar clientes", "listar clientes",
    "todos los huespedes", "ver huespedes",
)
_CONSULTA_PAGOS = (
    "ver pagos", "ver transacciones", "transacciones de pago",
    "pagos recibidos", "listar pagos",
)
_CONSULTA_CHECKINS = (
    "ver checkins", "ver check-ins", "listar checkins",
    "ver check-outs", "listar check-outs",
)


def _ejecutar_consulta_admin(text: str) -> str | None:
    """
    Si el texto del admin coincide con una consulta conocida, ejecuta SQL y
    devuelve el resultado formateado.
    Devuelve None si la consulta no es reconocida (pasa a Ollama).
    """
    import asyncio as _asyncio

    t = text.lower().strip()
    logger.debug("[ADMIN-QUERY] Texto recibido: %r", t)

    _MAP = [
        (_CONSULTA_RESERVAS,   "SELECT r.id, r.check_in_date, r.check_out_date, r.total_amount, "
                                "e.codigo AS estado, c.name AS cliente, ro.room_number "
                                "FROM reservations r "
                                "JOIN estado_reserva e ON r.id_estado = e.id "
                                "LEFT JOIN clients c ON r.client_id = c.id "
                                "LEFT JOIN rooms ro ON r.room_id = ro.id "
                                "ORDER BY r.created_at DESC LIMIT 50"),
        (_CONSULTA_HABITACIONES, "SELECT ro.room_number, th.nombre AS tipo, "
                                  "eh.nombre AS estado, ro.created_at "
                                  "FROM rooms ro "
                                  "JOIN tipo_habitacion th ON ro.id_tipo_hab = th.id "
                                  "JOIN estado_habitacion eh ON ro.id_estado_hab = eh.id "
                                  "ORDER BY ro.room_number"),
        (_CONSULTA_CLIENTES,    "SELECT c.id, c.name, c.doc_identidad, "
                                "td.nombre AS tipo_doc, c.whatsapp_number, c.created_at "
                                "FROM clients c "
                                "LEFT JOIN tipo_documento td ON c.id_tipo_documento = td.id "
                                "ORDER BY c.created_at DESC LIMIT 50"),
        (_CONSULTA_PAGOS,       "SELECT t.id, t.payment_id, t.amount, t.status, "
                                "t.payer_name, t.date_created "
                                "FROM transacciones t "
                                "ORDER BY t.created_at DESC LIMIT 50"),
        (_CONSULTA_CHECKINS,    "SELECT ci.id, ci.reservation_id, ro.room_number, "
                                "ci.actual_check_in, ci.actual_check_out, ci.created_at "
                                "FROM checkins ci "
                                "JOIN reservations r ON ci.reservation_id = r.id "
                                "JOIN rooms ro ON r.room_id = ro.id "
                                "ORDER BY ci.created_at DESC LIMIT 50"),
    ]

    async def _run_query(sql: str) -> dict:
        dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(**DB_HOTEL)
        conn = await asyncpg.connect(dsn, timeout=15)
        try:
            rows = await conn.fetch(sql)
            cols = list(rows[0].keys()) if rows else []
            return {"columns": cols, "rows": [dict(r) for r in rows], "count": len(rows)}
        except Exception as exc:
            return {"error": str(exc)}
        finally:
            await conn.close()

    for keywords, sql in _MAP:
        if any(k in t for k in keywords):
            logger.info("[ADMIN-QUERY] Consulta detectada: %r", keywords[0])
            try:
                loop = _asyncio.new_event_loop()
                result = loop.run_until_complete(_run_query(sql))
                loop.close()
                if "error" in result:
                    return f"[ERROR] {result['error']}"
                return json.dumps(result, ensure_ascii=False, default=str)
            except Exception as exc:
                logger.warning("[ADMIN-QUERY] Error SQL: %s", exc)
                return f"[ERROR] {exc}"

    logger.debug("[ADMIN-QUERY] No se detecto ninguna consulta conocida en: %r", t)
    return None


async def _generate_payment_link(phone: str, name: str, text: str) -> str | None:
    """
    Genera un link de pago MercadoPago para un cliente nuevo que desea reservar.
    Devuelve el texto del link listo para enviar, o None si falla.
    """
    try:
        external_ref = f"WA_{phone}"
        description = f"{RESERVATION_DESCRIPTION} — {name} ({phone})"
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: McpPayments().generate_payment_link(
                amount=RESERVATION_AMOUNT,
                reference=external_ref,
                user_id=phone,
            ),
        )
        link = result.get("link", "")
        preference_id = result.get("preference_id", "")
        if link:
            logger.info(f"[PAYMENT] Link generado para {phone} — pref={preference_id}")
            return (
                f"Bienvenido/a al hotel, {name}! 😊\n\n"
                f"Para confirmar tu reserva necesito completar el pago de S/{RESERVATION_AMOUNT:.2f}.\n\n"
                f"Puedes pagar aqui:\n{link}\n\n"
                f"Una vez realizado el pago, te confirmare tu reserva automaticamente."
            )
    except Exception as e:
        logger.warning(f"[PAYMENT] No se pudo generar link para {phone}: {e}")
    return None


async def _worker_wa() -> None:
    """Worker principal que consume la cola 'whatsapp_in' via BRPOP."""
    logger.info("[WA WORKER] Iniciado — escuchando cola whatsapp_in")
    r = None
    processed = 0
    while True:
        try:
            if r is None:
                r = aioredis.Redis(
                host=REDIS_HOST, port=REDIS_PORT,
                password=REDIS_PASSWORD, decode_responses=True,
            )
            logger.info("[WA WORKER] Redis conectado")
            processed = 0
            while True:
                try:
                    logger.debug("[WA WORKER] Esperando mensaje en cola whatsapp_in...")
                    result = await r.brpop("whatsapp_in", timeout=5)
                    logger.debug(f"[WA WORKER] brpop resultado: {result}")
                    if result is None:
                        continue
                    _, raw = result
                    msg = _parse_wa_message(raw)
                    logger.debug(f"[WA PARSER] resultado: phone={msg.get('phone')!r}  text={msg.get('text')!r}  keys={list(msg.keys())}")
                    if not msg or not msg.get("phone"):
                        logger.warning(f"[WA WORKER] Mensaje sin telefono (raw[:120]={raw[:120]!r}) — ignorado")
                        continue

                    text = (msg.get("text") or "").strip()

                    # ── Filtro: mensajes vacíos no se procesan ──────────────────────────────
                    if not text:
                        continue

                    processed += 1
                    logger.info(
                        f"[WA WORKER] #{processed} De {msg['phone']} ({msg.get('name','?')}): "
                        f"{text[:80]!r}"
                    )

                    # ── Regla 1: seguridad pasa siempre (admins no se bloquean) ───────────
                    is_adm = is_admin(msg["phone"])
                    logger.info(f"[WA WORKER] is_adm={is_adm} para {msg['phone']}")

                    # ── Regla 2: validacion de seguridad (admins inmunes) ─────────────────
                    from customer_service.mcp_servers.mcp_security import McpSecurity
                    sec = McpSecurity()
                    if not is_adm and not sec.validate_sender(msg["phone"]):
                        logger.warning(f"[WA WORKER] Remitente no autorizado {msg['phone']}")
                        continue
                    if not is_adm and not sec.validate_message_content(text, msg["phone"]):
                        logger.warning(f"[WA WORKER] Contenido bloqueado de {msg['phone']}")
                        try:
                            await _send_wa_message(
                                msg["phone"],
                                "Lo siento, no puedo procesar ese mensaje. "
                                "Contacta al administrador si crees que es un error.",
                            )
                        except Exception:
                            pass
                        continue

                    # ── Regla 3: recuperar historial y responder con LLM ──────────────────
                    history: list[dict] = []
                    try:
                        # Ahorrar latencia para admin: solo traer los ultimos turnos
                        hist_key = f"chat_history:{msg['phone']}"
                        if is_adm:
                            try:
                                raw_hist = await asyncio.wait_for(
                                    r.lrange(hist_key, -20, -1), timeout=5.0
                                )
                                if raw_hist:
                                    import json as _json
                                    history = [_json.loads(m) for m in reversed(raw_hist) if m]
                                logger.debug(
                                    f"[HISTORY] Telefono={msg['phone']} (admin) — {len(history)} turnos recuperados"
                                )
                            except asyncio.TimeoutError:
                                logger.warning(f"[HISTORY] Timeout lrange para {msg['phone']}, continuando sin historial")
                        else:
                            history = await asyncio.wait_for(
                                _get_history(msg["phone"], r), timeout=5.0
                            )
                            logger.debug(
                                f"[HISTORY] Telefono={msg['phone']} — {len(history)} mensajes en contexto"
                            )
                    except Exception as e:
                        logger.warning(f"[HISTORY] No se pudo recuperar historial: {e}")

                    # ── Regla 4: detectar intencion de pago y generar link de pago ────────────
                    # Se aplica tanto a usuarios nuevos (primer saludo + reserva)
                    # como a usuarios existentes que solicitan pagar o confirmar una reserva.
                    _payment_note: str | None = None
                    is_new_user = not history
                    if not is_adm and _detect_payment_intent(text):
                        logger.info(
                            f"[PAYMENT] Intencion de pago detectada en {msg['phone']} "
                            f"(nuevo={is_new_user}) — intentando generar link"
                        )
                        _payment_note = await _generate_payment_link(
                            msg["phone"], msg.get("name", "Usuario"), text
                        )

                    try:
                        # Limitar el historial para admin: usar solo los ultimos 10 turnos (20 msgs)
                        # para evitar que Ollama 3B se cuelgue con contextos muy largos.
                        _admin_history   = history[-20:] if is_adm else history
                        _admin_hist_size = len(_admin_history)
                        logger.info("[WA WORKER] _build_reply_admin(is_adm=%s, hist=%d msgs, text=%r)",
                                   is_adm, _admin_hist_size, text[:60])

                        async def _do_build() -> str:
                            return (
                                await _build_reply_admin(text, msg.get("name", "Admin"), _admin_history, is_adm)
                                if is_adm else
                                await _build_reply(text, msg.get("name", "Usuario"), _admin_history)
                            )

                        try:
                            reply = await asyncio.wait_for(_do_build(), timeout=30.0)
                        except asyncio.TimeoutError:
                            logger.error("[WA WORKER] Timeout 30s procesando mensaje de %s: %r",
                                       msg['phone'], text[:80])
                            reply = ("La consulta tardo demasiado. "
                                     "Intenta de nuevo mas tarde.")
                    except Exception as e:
                        logger.error(f"[WA WORKER] LLM fallo: {e}")
                        reply = "Gracias por tu mensaje. En este momento el asistente no esta disponible."

                    # ── Log de respuesta antes de enviar ────────────────────────────────
                    logger.info(f"[WA WORKER] Reply ({len(reply)} chars): {reply[:200]!r}")

                    # ── Adjuntar link de pago si se genero ────────────────────────────────
                    if _payment_note:
                        reply = f"{_payment_note}\n\n{reply}"

                    try:
                        await _send_wa_message(msg["phone"], reply)
                    except Exception as e:
                        logger.error(f"[WA WORKER] No se pudo enviar respuesta a {msg['phone']}: {e}")

                    # ── Guardar turno en Redis para proximo mensaje ────────────────────────
                    try:
                        await _save_turn(msg["phone"], text, reply, r)
                    except Exception as e:
                        logger.warning(f"[HISTORY] No se pudo guardar turno: {e}")

                except Exception as e:
                    logger.error(f"[WA WORKER] Error procesando mensaje: {e}", exc_info=True)
                    await asyncio.sleep(1)
            # ── Fin del while True interno ──────────────────────────────────────────

        except Exception as e:
            logger.error(f"[WA WORKER] Error critico: {e}", exc_info=True)
            logger.info("[WA WORKER] Reiniciando en 5s...")
            try:
                await r.close()
            except Exception:
                pass
            r = None
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("[WA WORKER] Cancelado — saliendo limpiamente")
            break


# ── Info ──────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"service": "core", "status": "running", "port": CORE_PORT}


class LLMTestRequest(BaseModel):
    message: str
    name: str = "Usuario"


@app.post("/", response_model=dict)
async def test_llm(body: LLMTestRequest):
    """Prueba el LLM: envia un mensaje y devuelve la respuesta generada."""
    # Recuperar historial y pasarlo al LLM
    try:
        r_test = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                                password=REDIS_PASSWORD, decode_responses=True)
        history = await _get_history("test_llm", r_test)
        reply = await _build_reply(body.message, body.name, history)
        await _save_turn("test_llm", body.message, reply, r_test)
        await r_test.close()
    except Exception:
        try:
            r_fb = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                                  password=REDIS_PASSWORD, decode_responses=True)
            fb_history = await _get_history("test_llm", r_fb)
            await r_fb.close()
        except Exception:
            fb_history = []
        reply = await _build_reply(body.message, body.name, fb_history)
    return {"reply": reply}


# ── Lanzar worker de WhatsApp al arrancar ───────────────────────────────────────
# Se ejecuta DESPUÉS de que uvicorn termine de levantar la app,
# para no interferir con el event-loop de FastAPI durante el startup.
@app.on_event("startup")
async def _launch_worker():
    get_admin_phones()            # precarga de admins
    asyncio.create_task(_worker_wa())
    logger.info("[STARTUP] Worker WA lanzado")
