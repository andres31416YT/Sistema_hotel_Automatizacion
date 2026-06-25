"""Classifier: use an LLM to determine the user's intent."""
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from lib.ollama import get_llm
from lib.config import settings

logger = logging.getLogger(__name__)

VALID_INTENTS = {"query", "knowledge", "payment", "general"}


async def classify_intent(state: dict) -> dict:
    message = state.get("message", "")
    history = state.get("history", [])
    is_admin = state.get("is_admin", False)

    context = ""
    if history:
        recent = [f"{m.get('role', '?')}: {m.get('content', '')[:80]}" for m in history[-4:]]
        context = "\n".join(recent)

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "Eres un clasificador de intenciones para un asistente de hotel.\n"
            "Clasifica el mensaje del usuario en UNA de estas categorías:\n"
            "- query: consulta sobre disponibilidad, reservas, habitaciones, datos operativos\n"
            "- knowledge: pregunta sobre políticas, horarios, servicios, reglas del hotel\n"
            "- payment: solicitud de pago, link de pago, estado de pago\n"
            "- general: saludo, ayuda, otro\n\n"
            "Devuelve SOLO la categoría, sin explicaciones."
        )),
        ("user", f"Mensaje: {message}\nContexto reciente:\n{context}\n\nCategoría:"),
    ])

    llm = get_llm(temperature=0.0)
    chain = prompt | llm | StrOutputParser()

    try:
        raw = await chain.ainvoke({})
        intent = raw.strip().lower()
        if intent not in VALID_INTENTS:
            logger.warning("Unknown intent '%s', falling back to general", intent)
            intent = "general"
    except Exception as exc:
        logger.error("Intent classification failed: %s", exc)
        intent = "general"

    logger.info("Classified intent for %s: %s", state.get("phone"), intent)
    return {"intent": intent}