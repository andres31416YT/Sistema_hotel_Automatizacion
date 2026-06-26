"""Knowledge agent node: search RAG for policies and procedures."""
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from lib.ollama import get_llm
from lib.datetime import get_current_datetime_block
from lib.rag import search

logger = logging.getLogger(__name__)


def _load_prompt(is_admin: bool) -> str:
    if is_admin:
        try:
            from agents.prompt.admin import PROMPT_KNOWLEDGE
            return PROMPT_KNOWLEDGE
        except Exception:
            pass
    else:
        try:
            from agents.prompt.customer import PROMPT_KNOWLEDGE
            return PROMPT_KNOWLEDGE
        except Exception:
            pass
    return "Eres un agente de conocimientos del hotel. Responde con base en la información recuperada."


async def knowledge_node(state: dict) -> dict:
    message = state.get("message", "")
    is_adm = state.get("is_admin", False)

    docs = await search(message, limit=3)
    context = "\n".join(f"- {d['content']}" for d in docs) if docs else "No se encontró información específica."

    prompt_text = _load_prompt(is_adm)
    tone = "directo, técnico" if is_adm else "cálido, amable"

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            f"{get_current_datetime_block()}\n\n"
            f"{prompt_text}\n"
            f"Responde con base en la información recuperada. Tono: {tone}. "
            f"Si la información no está en los documentos, indícalo claramente."
        )),
        ("user", f"Pregunta: {message}\n\nInformación disponible:\n{context}"),
    ])

    chain = prompt | get_llm(temperature=0.2) | StrOutputParser()
    response = await chain.ainvoke({})
    logger.info("Knowledge agent response (%d chars)", len(response))
    return {"agent_response": response}