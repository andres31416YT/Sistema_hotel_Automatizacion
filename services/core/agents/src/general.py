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
    sender_info = state.get("sender_info", {})

    role = "administrador del hotel" if is_admin else "huésped"
    tone = "directo y profesional" if is_admin else "amable y cordial"
    greeting = "" if is_admin else f"Hola, {name}. "

    db_name = sender_info.get("name", name)
    client_id = sender_info.get("client_id")
    is_existing = sender_info.get("is_existing_client", False)
    is_new_user = sender_info.get("is_new_user", False)

    context_lines = []
    if is_admin:
        context_lines.append("El usuario es administrador del sistema.")
    else:
        context_lines.append(f"El usuario es un huesped llamado {db_name}.")
        if is_new_user:
            context_lines.append("Es un usuario nuevo, recien registrado.")
        elif is_existing and client_id:
            context_lines.append(f"Es un huesped existente registrado en el sistema (ID: {client_id}).")
        else:
            context_lines.append("No se encontro registro previo en la base de datos.")

    context_block = "\n".join(context_lines)

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            f"{get_current_datetime_block()}\n\n"
            f"Eres el asistente virtual del hotel.\n"
            f"CONTEXTO DEL USUARIO:\n{context_block}\n\n"
            f"Tono: {tone}.\n"
            "Si el usuario pregunta sobre disponibilidad, invitalo a consultar 'disponibilidad'.\n"
            "Si pregunta sobre pagos, invitalo a consultar 'pago'.\n"
            "Si pregunta sobre informacion general, usa tus conocimientos.\n"
            "No inventes reservas ni datos especificos."
        )),
        ("user", f"{greeting}Mensaje: {message}"),
    ])

    chain = prompt | get_llm(temperature=0.4) | StrOutputParser()
    response = await chain.ainvoke({})
    logger.info("General node response (%d chars)", len(response))
    return {"agent_response": response}