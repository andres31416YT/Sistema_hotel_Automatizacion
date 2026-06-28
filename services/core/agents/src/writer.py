"""Writer agent node: format the final response for WhatsApp."""
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from lib.ollama import get_llm
from lib.security import sanitize_llm_response

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
    name = state.get("name", "")

    if is_adm:
        final_message = agent_response
    else:
        display_name = name if name else "Usuario"
        greeting = f"Hola {display_name}, es un placer atenderte. "
        prompt_text = _load_prompt(is_admin=False)
        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                f"{prompt_text}\n\n"
                "REGLAS DE RESPUESTA:\n"
                "- NUNCA repitas fechas, horas, zonas horarias ni ningun dato de contexto temporal en tu respuesta.\n"
                "- NUNCA incluyas etiquetas XML/HTML como <environment_details>, <system>, <internal>, <meta> ni similares.\n"
                "- NUNCA menciones 'Working directory', 'Current time', 'Active file', 'zona horaria', 'UTC-5' ni ningun metadato del sistema.\n"
                "Tu respuesta debe ser SOLO el texto para el usuario, sin etiquetas ni informacion tecnica. "
                "No agregues despedidas formales como 'Atentamente' o '[Nombre del Hotel]'. "
                "No uses formato markdown con pipes (|). Usa listas con guiones simples."
            )),
            ("user", (
                f"Mensaje original: {message}\n"
                f"Respuesta del agente especializado: {agent_response}\n\n"
                "Redacta el cuerpo del mensaje despues del saludo. No repitas el saludo, solo el contenido."
            )),
        ])
        chain = prompt | get_llm(temperature=0.3) | StrOutputParser()
        body = await chain.ainvoke({})
        body = sanitize_llm_response(body)
        final_message = f"{greeting}{body}"

    final_message = sanitize_llm_response(final_message)
    logger.info("Writer agent final message (%d chars): %s", len(final_message), final_message[:200])
    return {"final_message": final_message}