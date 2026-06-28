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
            "Clasifica el mensaje del usuario en UNA de estas categorías:\n\n"
            "- query: consulta o modificacion sobre datos del hotel en la base de datos. "
            "Incluye: consultar disponibilidad, reservas, habitaciones, clientes, "
            "agregar/crear/registrar nuevos datos (habitaciones, reservas, clientes), "
            "modificar o actualizar datos existentes, eliminar registros, "
            "cambiar estados, check-in, check-out, ver historiales, datos operativos.\n\n"
            "- knowledge: pregunta sobre políticas, horarios, servicios, reglas del hotel, "
            "información general que no requiere acceder a la base de datos.\n\n"
            "- payment: solicitud de pago, link de pago, estado de pago, "
            "generar cobro, consultar transacciones, mercadopago, yape, plin.\n\n"
            "- general: saludo, ayuda, conversación casual, presentación, "
            "pregunta quién eres, qué puedes hacer.\n\n"
            "Regla: Si el usuario menciona 'agregar', 'crear', 'nueva habitacion', "
            "'nuevo cliente', 'modificar', 'cambiar', 'eliminar' -> siempre es 'query'.\n\n"
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