"""Core service: FastAPI + LangGraph WhatsApp orchestrator."""
import os
import re
import json
import hashlib
import hmac
import logging
import asyncio
from typing import Any

import httpx
from fastapi import FastAPI, Request, HTTPException

from lib.config import settings
from lib.redis_client import redis_client
from lib.security import is_admin, validate_sender, validate_message_content, sanitize_name, sanitize_llm_response
from agents.graph import build_customer_graph, build_admin_graph

# LangSmith tracing setup
if settings.langsmith_api_key:
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    if settings.langsmith_project:
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Hotel Core Service")

customer_graph = build_customer_graph()
admin_graph = build_admin_graph()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _normalize_chat_id(phone: str) -> str:
    digits = re.sub(r'\D', '', phone or '')
    if not digits:
        return phone
    return f"{digits}@c.us"


async def _warm_chat(session_id: str, phone: str, max_retries: int = 3) -> bool:
    """Pre-warm chat by fetching it first to resolve LID."""
    headers = {"X-API-Key": settings.openwa_api_key} if settings.openwa_api_key else {}
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                chat_id = _normalize_chat_id(phone)
                await client.get(
                    f"{settings.openwa_api_url}/api/sessions/{session_id}/chats/{chat_id}",
                    headers=headers
                )
            return True
        except Exception:
            await asyncio.sleep(1)
    return False

async def _send_wa_message(to: str, text: str) -> bool:
    chat_id = _normalize_chat_id(to)
    session_id = settings.openwa_session_uuid or settings.openwa_session_id
    
    # Pre-warm chat to resolve LID
    await _warm_chat(session_id, to)
    
    url = f"{settings.openwa_api_url}/api/sessions/{session_id}/messages/send-text"
    payload = {"chatId": chat_id, "text": text}
    headers = {"Content-Type": "application/json"}
    if settings.openwa_api_key:
        headers["X-API-Key"] = settings.openwa_api_key
    
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.error("send_wa failed: %s %s", resp.status_code, resp.text)
            return False
        return True


async def _setup_openwa() -> None:
    base = settings.openwa_api_url.rstrip('/')
    headers = {"Content-Type": "application/json"}
    if settings.openwa_api_key:
        headers["X-API-Key"] = settings.openwa_api_key

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(f"{base}/api/sessions", json={"name": settings.openwa_session_id}, headers=headers)
            if resp.status_code == 409:
                logger.info("[OPENWA] Session already exists: %s", settings.openwa_session_id)
            elif resp.status_code >= 400:
                logger.warning("[OPENWA] Session creation returned %s: %s", resp.status_code, resp.text[:200])
            else:
                logger.info("[OPENWA] Session ensured: %s", settings.openwa_session_id)
        except Exception as exc:
            logger.error("[OPENWA] Session setup failed: %s", exc)


def _verify_hmac_signature(raw_body: bytes, signature: str | None, secret: str | None) -> bool:
    if not secret:
        return True
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _normalize_openwa_event_to_meta(payload: dict[str, Any]) -> dict[str, Any]:
    event = payload.get("event", "")
    data = payload.get("data") or {}
    if event != "message.received" or not isinstance(data, dict):
        return payload

    sender = data.get("from", "")
    phone = re.sub(r'@.*', '', sender or '')
    pushname = data.get("pushname", "")
    name = pushname or phone
    body = data.get("body", " ") or " "

    return {
        "contacts": [
            {
                "profile": {"name": name},
                "wa_id": phone,
            }
        ],
        "messages": [
            {
                "from": phone,
                "text": {"body": body},
            }
        ],
    }


# ── OpenWA webhook endpoint ───────────────────────────────────────────────────

@app.post("/webhooks/openwa")
async def openwa_webhook(request: Request):
    raw = await request.body()

    try:
        payload = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    signature = request.headers.get("X-Hub-Signature-256") or request.headers.get("X-OpenWA-Signature")
    if not _verify_hmac_signature(raw, signature, settings.openwa_webhook_secret):
        logger.warning("[OPENWA WEBHOOK] Invalid or missing HMAC signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    normalized = _normalize_openwa_event_to_meta(payload)
    queued = json.dumps(normalized)

    async def _queue():
        try:
            await redis_client.push_whatsapp(queued)
            logger.info("[OPENWA WEBHOOK] Event queued: %s", payload.get("event"))
        except Exception as exc:
            logger.error("[OPENWA WEBHOOK] Failed to queue event: %s", exc)

    asyncio.create_task(_queue())

    # Guardar historial inmediatamente cuando llega el mensaje
    try:
        event_data = payload.get("data") or {}
        event_type = payload.get("event", "")
        if event_type == "message.received" and isinstance(event_data, dict):
            sender = event_data.get("from", "")
            phone = re.sub(r'@.*', '', sender or '')
            body = event_data.get("body", "") or ""
            if phone and body:
                await redis_client.save_inbound(phone, body)
                logger.info("[OPENWA WEBHOOK] Inbound message saved for %s", phone)
    except Exception as exc:
        logger.error("[OPENWA WEBHOOK] Failed to save inbound message: %s", exc)

    return {"status": "queued"}


# ── WhatsApp message parsing ──────────────────────────────────────────────────

def _parse_wa_message(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)

        contacts: list[dict] = []
        messages: list[dict] = []

        def extract_value(obj: Any):
            nonlocal contacts, messages
            if isinstance(obj, dict):
                if "contacts" in obj:
                    contacts = obj.get("contacts") or contacts
                if "messages" in obj:
                    messages = obj.get("messages") or messages
                for v in obj.values():
                    extract_value(v)
            elif isinstance(obj, list):
                for item in obj:
                    extract_value(item)

        extract_value(data)

        phone = (
            (messages[0].get("from") if messages else "")
            or data.get("phone")
            or data.get("from")
            or data.get("sender_id")
            or (contacts[0].get("wa_id") if contacts else "")
        )
        name = (
            (contacts[0].get("profile", {}).get("name") if contacts else "")
            or data.get("name")
            or data.get("profile", {}).get("name", "")
            or ""
        )
        text = (
            (messages[0].get("text", {}).get("body") if messages else "")
            or data.get("text")
            or data.get("body")
            or data.get("message", "")
            or ""
        )
        return {"phone": phone, "name": sanitize_name(name), "text": text}
    except Exception as exc:
        logger.warning("parse_wa failed: %s | raw=%s", exc, raw[:200])
        return {}


def _detect_payment_intent(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in [
        "pago", "pagar", "link de pago", "pay", "payment",
        "ya pague", "ya pagué", "pago realizado", "pago confirmado",
        "quiero pagar", "necesito pagar", "cómo pago", "como pago",
        "transferencia", "deposito", "depósito", "tarjeta",
        "mercado pago", "yape", "plin",
    ])


async def _generate_payment_link(phone: str, name: str) -> str | None:
    try:
        from lib.payments import payments_client
        result = payments_client.generate_payment_link(
            amount=150.0,
            reference=f"WA_{phone}",
            user_id=phone,
            description=f"Reserva Hotel - {name}",
        )
        link = result.get("link", "")
        if link:
            return (
                f"Bienvenido/a al hotel, {name}!\n\n"
                f"Para confirmar tu reserva necesito completar el pago de S/150.00.\n\n"
                f"Puedes pagar aqui:\n{link}\n\n"
                f"Una vez realizado el pago, te confirmare tu reserva automaticamente."
            )
    except Exception as exc:
        logger.error("payment link error for %s: %s", phone, exc)
    return None


# ── Worker principal ───────────────────────────────────────────────────────────

async def _worker_wa() -> None:
    logger.info("[WA WORKER] Iniciado")
    r = None
    processed = 0
    while True:
        try:
            if r is None:
                r = await redis_client.connect()
                logger.info("[WA WORKER] Redis conectado")
                processed = 0
            result = await r.brpop("whatsapp_in", timeout=5)
            if result is None:
                continue
            _, raw = result
            logger.info("[WA WORKER] Raw message from Redis: %s", raw[:200])
            msg = _parse_wa_message(raw)
            logger.info("[WA WORKER] Parsed message: %s", msg)
            if not msg or not msg.get("phone"):
                logger.warning("[WA WORKER] Mensaje sin telefono, ignorado")
                continue

            text = (msg.get("text") or "").strip()
            if not text:
                continue

            processed += 1
            logger.info("[WA WORKER] #%d De %s: %s", processed, msg["phone"], text[:80])

            phone = msg["phone"]
            name = msg.get("name", "Usuario")
            _admin = is_admin(phone)

            if not validate_sender(phone):
                logger.warning("[WA WORKER] Remitente no autorizado %s", phone)
                if phone.startswith("test_"):
                    continue
                continue
            if not validate_message_content(text, phone):
                logger.warning("[WA WORKER] Contenido bloqueado de %s", phone)
                await _send_wa_message(phone, "Lo siento, no puedo procesar ese mensaje.")
                continue

            history = await redis_client.get_history(phone)
            is_new = len(history) == 0

            # Ensure history key is a list (fix WRONGTYPE from previous runs)
            if not isinstance(history, list):
                from lib.redis_client import redis_client as rc
                await rc.connect()
                await rc._client.delete(f"chat_history:{phone}")
                history = []

            payment_note = None
            if not _admin and _detect_payment_intent(text):
                logger.info("[PAYMENT] Intencion de pago detectada en %s", phone)
                payment_note = await _generate_payment_link(phone, name)

            graph = admin_graph if _admin else customer_graph
            state = {
                "phone": phone,
                "name": name,
                "message": text,
                "history": history,
                "is_admin": _admin,
                "security_valid": True,
                "blocked_reason": None,
                "sender_info": {},
                "intent": "general",
                "agent_response": "",
                "final_message": "",
            }

            try:
                reply = await asyncio.wait_for(graph.ainvoke(state), timeout=60.0)
                final_msg = reply.get("final_message", "")
                logger.info("[WA WORKER] Graph result for %s: intent=%s, final_msg_len=%d", phone, reply.get("intent", "?"), len(final_msg))
            except asyncio.TimeoutError:
                logger.error("[WA WORKER] Timeout procesando %s", phone)
                final_msg = "La consulta tardo demasiado. Intenta de nuevo mas tarde."
            except Exception as exc:
                logger.error("[WA WORKER] Graph error for %s: %s", phone, exc, exc_info=True)
                final_msg = "Error procesando tu mensaje. Intenta mas tarde."

            if payment_note:
                final_msg = f"{payment_note}\n\n{final_msg}" if final_msg else payment_note

            final_msg = sanitize_llm_response(final_msg)

            logger.info("[WA WORKER] Reply a %s (%d chars): %s", phone, len(final_msg), final_msg)
            await _send_wa_message(phone, final_msg)
            await redis_client.save_turn(phone, text, final_msg)

        except Exception as exc:
            logger.error("[WA WORKER] Error critico: %s", exc, exc_info=True)
            if r:
                try:
                    await r.aclose()
                except Exception:
                    pass
                r = None
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("[WA WORKER] Cancelado")
            if r:
                try:
                    await r.aclose()
                except Exception:
                    pass
            break


# ── Lanzar worker al arrancar ──────────────────────────────────────────────────

@app.on_event("startup")
async def _launch_worker():
    get_admin_phones()
    asyncio.create_task(_warm_schema())
    asyncio.create_task(_worker_wa())
    logger.info("[STARTUP] Worker WA lanzado")


async def _warm_schema():
    from lib.db import load_hotel_schema
    schema_text = await load_hotel_schema()
    if schema_text:
        logger.info("[STARTUP] Schema warmed (%d chars)", len(schema_text))
    else:
        logger.warning("[STARTUP] Schema warm-up returned empty")


def get_admin_phones() -> list[str]:
    phones = settings.admin_phones_list
    logger.info("[STARTUP] Admin phones loaded: %s (count=%d)", phones, len(phones))
    return phones

