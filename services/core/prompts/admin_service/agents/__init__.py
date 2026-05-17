"""
Prompts centralizados del sistema de agentes del hotel (servicio administrativo).

Cada agente tiene su prompt en un archivo .txt independiente.
Los prompts activos de LLM se cargan desde archivo para facilitar
su edicion sin tocar codigo.

Uso:
    from core.prompts.admin_service.agents import (
        PROMPT_GUARD,
        PROMPT_IDENTIFIER,
        PROMPT_KNOWLEDGE,
        PROMPT_QUERY,
        PROMPT_PAYMENT,
        PROMPT_WRITER,
        PROMPT_NEXUS,
        PROMPT_LLM_ADMIN,
    )
"""

import os as _os

# ── Definiciones de rol de cada agente ───────────────────────────────────────

PROMPT_GUARD = (
    "Valida cada mensaje entrante del huesped o admin: detecta spam, fraude y "
    "contenido malicioso. Bloquea remitentes peligrosos."
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
    "Gestiona el flujo de pagos de reservas: genera links de MercadoPago, consulta "
    "el estado del pago y registra la transaccion en db_payments."
)

PROMPT_WRITER = (
    "Recibe el texto de respuesta del agente adecuado, lo formatea para WhatsApp "
    "(limite 4096 caracteres, tono calido y profesional) y lo envia al huesped o "
    "administrador correspondiente."
)

PROMPT_NEXUS = (
    "Eres el orquestador principal del servicio administrativo. Coordinas todos los "
    "agentes y respondes consultas de administradores con acceso completo a toda "
    "la informacion del sistema."
)

# ── Carga de prompts activos de LLM desde archivo ────────────────────────────


def _load_prompt(filename: str) -> str:
    _here = _os.path.dirname(__file__)
    full = _os.path.join(_here, filename)
    with open(full, encoding="utf-8") as f:
        return f.read().strip()


PROMPT_LLM_ADMIN = _load_prompt("llm_admin.txt")
