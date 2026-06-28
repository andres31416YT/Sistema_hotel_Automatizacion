"""General response node for non-categorized intents."""
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from lib.ollama import get_llm
from lib.datetime import get_current_datetime_block

logger = logging.getLogger(__name__)


async def general_node(state: dict) -> dict:
    message = state.get("message", "")
    name = state.get("name", "")
    is_admin = state.get("is_admin", False)
    sender_info = state.get("sender_info", {})

    db_name = sender_info.get("name") or name
    client_id = sender_info.get("client_id")
    is_existing = sender_info.get("is_existing_client", False)
    is_new_user = sender_info.get("is_new_user", False)

    if is_admin:
        role_line = "El usuario es administrador del hotel."
    elif is_new_user:
        role_line = "El usuario es un huesped nuevo que acaba de registrarse por WhatsApp."
    elif is_existing and client_id:
        role_line = f"El usuario es un huesped registrado. Nombre: {db_name}. ID interno: {client_id}."
    else:
        role_line = f"El usuario escribio por WhatsApp. Nombre del perfil: {db_name}."

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            f"{get_current_datetime_block()}\n\n"
            "Eres el asistente virtual del hotel.\n"
            f"Contexto: {role_line}\n"
            "Comportate segun el rol del usuario:\n"
            "- Si es administrador: tono directo, profesional, sin saludos innecesarios.\n"
            "- Si es huesped: tono cordial, usa su nombre si lo tienes.\n"
            "- Si es nuevo: se amigable, invitalo a conocer el hotel.\n"
            "Si pregunta sobre disponibilidad, sugiere consultar 'disponibilidad'.\n"
            "Si pregunta sobre pagos, sugiere consultar 'pago'.\n"
            "Si pregunta sobre informacion general, responde segun tu conocimiento del hotel.\n"
            "No inventes reservas ni datos especificos."
        )),
        ("user", message),
    ])

    chain = prompt | get_llm(temperature=0.4) | StrOutputParser()
    response = await chain.ainvoke({})
    logger.info("General node response (%d chars)", len(response))
    return {"agent_response": response}
