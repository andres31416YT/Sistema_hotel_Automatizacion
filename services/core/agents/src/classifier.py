"""Classifier: use an LLM to determine the user's intent."""
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from lib.ollama import get_llm
from lib.config import settings

logger = logging.getLogger(__name__)

VALID_INTENTS = {"query", "knowledge", "payment", "general"}

_GENERAL_PATTERNS = [
    "quien soy", "quién soy", "como te llamas", "cómo te llamas",
    "que puedes hacer", "qué puedes hacer", "que haces", "qué haces",
    "hola", "buenas", "buen dia", "buen día", "buenos dias", "buenos días",
    "buenas tardes", "buenas noches", "saludos", "hey", "hi",
    "como estas", "cómo estás", "como va", "qué tal", "que tal",
]

_QUERY_PATTERNS = [
    "ver todos los", "mostrar todos los", "lista de", "listar",
    "todos los huespedes", "todos los clientes", "todas las habitaciones",
    "todas las reservas", "todos los pagos", "dame todos",
    "muestrame todos", "muéstrame todos", "consultar todos",
]

_PAYMENT_PATTERNS = [
    "pago", "pagar", "link de pago", "pay", "payment",
    "ya pague", "ya pagué", "pago realizado", "pago confirmado",
    "quiero pagar", "necesito pagar", "cómo pago", "como pago",
    "transferencia", "deposito", "depósito", "tarjeta",
    "mercado pago", "yape", "plin",
]


def _rule_based_classify(message: str) -> str | None:
    lower = message.strip().lower()
    for p in _QUERY_PATTERNS:
        if p in lower:
            return "query"
    for p in _PAYMENT_PATTERNS:
        if p in lower:
            return "payment"
    for p in _GENERAL_PATTERNS:
        if p in lower:
            return "general"
    return None


async def classify_intent(state: dict) -> dict:
    message = state.get("message", "")
    history = state.get("history", [])
    is_admin = state.get("is_admin", False)

    rule_intent = _rule_based_classify(message)
    if rule_intent:
        logger.info("Rule-based classification: '%s' -> %s", message[:40], rule_intent)
        return {"intent": rule_intent}

    context = ""
    if history:
        recent = [f"{m.get('role', '?')}: {m.get('content', '')[:80]}" for m in history[-4:]]
        context = "\n".join(recent)

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "Eres un clasificador de intenciones para un asistente de hotel.\n"
            "Clasifica el mensaje del usuario en UNA de estas categorías:\n\n"
            "- query: el usuario pide consultar o modificar DATOS ESPECIFICOS del hotel en la base de datos. "
            "Incluye: disponibilidad, reservas, habitaciones, clientes, pagos, agregar/crear/registrar datos, "
            "modificar, eliminar, check-in, check-out, ver historiales, datos operativos concretos.\n\n"
            "- knowledge: pregunta sobre POLITICAS, horarios, servicios, reglas del hotel, "
            "informacion general que no requiere acceder a la base de datos.\n\n"
            "- payment: solicitud de pago, link de pago, estado de pago, generar cobro, "
            "consultar transacciones, mercadopago, yape, plin.\n\n"
            "- general: saludo, ayuda, presentacion, pregunta sobre si mismo (quien soy, como te llamas), "
            "conversacion casual, pregunta que NO pide datos concretos de la base de datos.\n\n"
            "Reglas:\n"
            "- Si el usuario pregunta 'quien soy', 'como te llamas', 'que puedes hacer' -> general.\n"
            "- Si el usuario solo dice 'Hola', 'Buen dia', 'Buenas' -> general.\n"
            "- Si el usuario menciona 'agregar', 'crear', 'nueva habitacion', 'nuevo cliente', "
            "'modificar', 'cambiar', 'eliminar' -> query.\n"
            "- Si pide 'muestrame', 'dame', 'lista de' + datos concretos -> query.\n\n"
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

    logger.info("LLM classification: '%s' -> %s", message[:40], intent)
    return {"intent": intent}