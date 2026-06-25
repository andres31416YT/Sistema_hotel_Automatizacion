"""Writer agent node: format the final response for WhatsApp."""
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from lib.ollama import get_llm
from lib.datetime import get_current_datetime_block

logger = logging.getLogger(__name__)


def _load_prompt(is_admin: bool) -> str:
    if is_admin:
        try:
            from agents.prompt.admin import PROMPT_WRITER
            return PROMPT_WRITER
        except Exception:
            pass
    else:
        try:
            from agents.prompt.customer import PROMPT_WRITER
            return PROMPT_WRITER
        except Exception:
            pass
    return "Eres el WriterAgent del hotel."


async def writer_node(state: dict) -> dict:
    message = state.get("message", "")
    agent_response = state.get("agent_response", "")
    is_adm = state.get("is_admin", False)
    phone = state.get("phone", "")
    name = state.get("name", "Usuario")

    prompt_text = _load_prompt(is_adm)
    greeting = "" if is_adm else f"Hola, {name}. "

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            f"{get_current_datetime_block()}\n\n"
            f"{prompt_text}\n"
            f"Saludo: {greeting}"
        )),
        ("user", (
            f"Mensaje original: {message}\n"
            f"Respuesta del agente especializado: {agent_response}\n\n"
            "Redacta la respuesta final para WhatsApp."
        )),
    ])

    chain = prompt | get_llm(temperature=0.3) | StrOutputParser()
    final_message = await chain.ainvoke({})
    logger.info("Writer agent final message (%d chars)", len(final_message))
    return {"final_message": final_message}