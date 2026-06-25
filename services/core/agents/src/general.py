"""General response node for non-categorized intents."""
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from lib.ollama import get_llm
from lib.datetime import get_current_datetime_block

logger = logging.getLogger(__name__)


async def general_node(state: dict) -> dict:
    message = state.get("message", "")
    name = state.get("name", "Usuario")
    is_admin = state.get("is_admin", False)

    greeting = "" if is_admin else f"Hola, {name}. "
    tone = "directo" if is_admin else "amable"

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            f"{get_current_datetime_block()}\n\n"
            f"Eres el asistente virtual del hotel. Tono: {tone}.\n"
            "Si el usuario pregunta sobre disponibilidad, invítalo a consultar 'disponibilidad'.\n"
            "Si pregunta sobre pagos, invítalo a consultar 'pago'.\n"
            "Si pregunta sobre información general, usa tus conocimientos.\n"
            "No inventes reservas ni datos específicos."
        )),
        ("user", f"{greeting}Mensaje: {message}"),
    ])

    chain = prompt | get_llm(temperature=0.4) | StrOutputParser()
    response = await chain.ainvoke({})
    logger.info("General node response (%d chars)", len(response))
    return {"agent_response": response}