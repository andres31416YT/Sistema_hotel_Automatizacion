"""
Prompts centralizados del sistema de agentes del hotel.

Cada agente tiene su prompt en un archivo .txt independiente en la carpeta
correspondiente a su servicio (customer_service / admin_service).

Uso:
    from core.prompts.customer_service.agents import PROMPT_LLM_HUESPED
    from core.prompts.admin_service.agents       import PROMPT_LLM_ADMIN
"""

import importlib.resources as _res
import os as _os

# ── Definiciones de rol de cada agente ───────────────────────────────────────

PROMPT_GUARD = (
    "Valida cada mensaje entrante del huesped: detecta spam, fraude y contenido "
    "malicioso. Bloquea remitentes peligrosos. Los administradores tienen "
    "inmunidad."
)

PROMPT_IDENTIFIER = (
    "Identifica al remitente del mensaje y obtiene su contexto (huesped, empleado, "
    "admin). Extrae informacion relevante del remitente para personalizar la atencion."
)

PROMPT_KNOWLEDGE = (
    "Consulta la base de conocimiento del hotel para proporcionar informacion "
    "precisa sobre servicios, politicas, horarios y preguntas frecuentes usando "
    "busqueda semantica RAG."
)

PROMPT_QUERY = (
    "Ejecuta consultas a la base de datos para obtener informacion en tiempo real "
    "sobre disponibilidad de habitaciones, reservas y estados de pago."
)

PROMPT_PAYMENT = (
    "Gestiona el flujo de pagos de reservas: genera links de MercadoPago para el "
    "huesped, consulta el estado del pago y registra la transaccion en db_payments."
)

PROMPT_WRITER = (
    "Recibe el texto de respuesta del agente adecuado, lo formatea para WhatsApp "
    "(limite 4096 caracteres, tono calido y profesional) y lo envia al huesped."
)

PROMPT_NEXUS = (
    "Eres el orquestador principal del sistema. Recibes mensajes de huespedes por "
    "WhatsApp, los validas, identificas al remitente, determinas la intencion y "
    "delegas la tarea al agente especializado correspondiente. "
    "Intenciones reconocidas: disponibilidad, pago, informacion general."
)

# ── LLM prompts cargados desde archivo .txt ───────────────────────────────────

def _load_prompt(filename: str) -> str:
    _here = _os.path.dirname(__file__)
    full = _os.path.join(_here, filename)
    with open(full, encoding="utf-8") as f:
        return f.read().strip()


PROMPT_LLM_HUESPED = _load_prompt("llm_huesped.txt")
