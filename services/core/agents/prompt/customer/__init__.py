"""Customer service prompts loader."""
import os

_here = os.path.dirname(__file__)


def _load(filename: str) -> str:
    with open(os.path.join(_here, filename), encoding="utf-8") as f:
        return f.read().strip()


PROMPT_GUARD      = _load("guard.txt")
PROMPT_IDENTIFIER = _load("identifier.txt")
PROMPT_NEXUS      = _load("nexus.txt")
PROMPT_QUERY      = _load("query.txt")
PROMPT_KNOWLEDGE  = _load("knowledge.txt")
PROMPT_PAYMENT    = _load("payment.txt")
PROMPT_WRITER     = _load("writer.txt")
PROMPT_LLM_HUESPED = _load("llm_huesped.txt")

__all__ = [
    "PROMPT_GUARD",
    "PROMPT_IDENTIFIER",
    "PROMPT_NEXUS",
    "PROMPT_QUERY",
    "PROMPT_KNOWLEDGE",
    "PROMPT_PAYMENT",
    "PROMPT_WRITER",
    "PROMPT_LLM_HUESPED",
]