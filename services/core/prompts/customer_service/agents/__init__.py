"""
Prompts de agentes del servicio al Cliente (customer_service).

Cada agente tiene su propio archivo .txt en esta carpeta.
Los prompts activos de LLM tambien viven aqui como .txt.
"""

import os as _os


def _load(filename: str) -> str:
    _here = _os.path.dirname(__file__)
    with open(_os.path.join(_here, filename), encoding="utf-8") as f:
        return f.read().strip()


# ── Prompts de LLM ────────────────────────────────────────────────────────

PROMPT_LLM_HUESPED = _load("llm_huesped.txt")


# ── Roles de agentes ─────────────────────────────────────────────────────

PROMPT_GUARD      = _load("guard.txt")
PROMPT_IDENTIFIER = _load("identifier.txt")
PROMPT_KNOWLEDGE  = _load("knowledge.txt")
PROMPT_QUERY      = _load("query.txt")
PROMPT_PAYMENT    = _load("payment.txt")
PROMPT_WRITER     = _load("writer.txt")
PROMPT_NEXUS      = _load("nexus.txt")
