"""Knowledge agent node: search RAG for policies and procedures and query DB."""
import logging
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from lib.ollama import get_llm
from lib.db import fetch_all, get_hotel_schema, schema_to_text, HOTEL_SCHEMA_TEXT, HOTEL_SCHEMA_LOADED, load_hotel_schema
from lib.datetime import get_current_datetime_block
from lib.rag import search

logger = logging.getLogger(__name__)

_hotel_schema_text = ""


async def _ensure_schema():
    global _hotel_schema_text
    if _hotel_schema_text:
        return
    if HOTEL_SCHEMA_LOADED and HOTEL_SCHEMA_TEXT:
        _hotel_schema_text = HOTEL_SCHEMA_TEXT
        return
    _hotel_schema_text = await load_hotel_schema() or ""


@tool
async def search_knowledge(query: str, limit: int = 3) -> str:
    """Search the RAG knowledge base by semantic similarity."""
    try:
        results = await search(query, limit=limit)
        if not results:
            return "No se encontró información en la base de conocimientos."
        lines = []
        for i, r in enumerate(results, 1):
            score = r.get("score", 0)
            content = r.get("content", "")
            lines.append(f"[{i}] (score={score:.2f})\n{content}")
        return "\n\n".join(lines)
    except Exception as exc:
        return f"Error buscando en base de conocimientos: {exc}"


@tool
async def execute_sql(query: str) -> str:
    """Execute a read-only SQL query against the hotel database (SELECT, SHOW, WITH)."""
    try:
        rows = await fetch_all(query)
        if not rows:
            return "La consulta se ejecutó correctamente pero no hay resultados."
        cols = list(rows[0].keys())
        lines = [f"{len(rows)} resultado(s):\n", " | ".join(cols), "|" + "|".join("---" for _ in cols)]
        for row in rows[:50]:
            lines.append(" | ".join(str(row.get(c, "")) for c in cols))
        return "\n".join(lines)
    except Exception as exc:
        return f"Error en consulta SQL: {exc}"


@tool
async def get_db_schema() -> str:
    """Get the complete database schema with tables and columns."""
    await _ensure_schema()
    return _hotel_schema_text


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
    await _ensure_schema()
    message = state.get("message", "")
    is_adm = state.get("is_admin", False)

    tools = [search_knowledge, get_db_schema, execute_sql]
    llm = get_llm(temperature=0.0).bind_tools(tools)
    prompt_text = _load_prompt(is_adm)
    tone = "directo, tecnico" if is_adm else "calido, amable"

    schema_block = f"\n\nESQUEMA DE BASE DE DATOS:\n{_hotel_schema_text}" if _hotel_schema_text else ""

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            f"{get_current_datetime_block()}\n\n"
            f"{prompt_text}\n"
            f"Responde con base en la informacion recuperada. Tono: {tone}. "
            f"Si la informacion no esta en los documentos, indicalo claramente."
            f"{schema_block}\n\n"
            "IMPORTANTE: Usa SOLO los nombres de tabla y columna que aparecen en el esquema anterior."
        )),
        ("user", f"Pregunta: {message}"),
    ])

    chain = prompt | llm
    response = await chain.ainvoke({})
    tool_calls = getattr(response, "tool_calls", None)
    tool_results: list[dict] = []

    if tool_calls:
        for tc in tool_calls:
            fn_name = tc["name"]
            args = tc.get("args", {})
            try:
                if fn_name == "search_knowledge":
                    result = await search_knowledge.ainvoke(args)
                elif fn_name == "execute_sql":
                    result = await execute_sql.ainvoke(args)
                elif fn_name == "get_db_schema":
                    result = await get_db_schema.ainvoke(args)
                else:
                    result = f"Herramienta desconocida: {fn_name}"
            except Exception as exc:
                result = f"Error ejecutando {fn_name}: {exc}"
            tool_results.append({"tool": fn_name, "result": result})

        messages = [
            {"role": "system", "content": prompt.format_messages()[0].content},
            {"role": "user", "content": message},
            {"role": "assistant", "content": "", "tool_calls": tool_calls},
        ]
        for tr in tool_results:
            messages.append({"role": "tool", "tool_call_id": tr["tool"], "content": tr["result"]})

        final_prompt = ChatPromptTemplate.from_messages([
            ("system", "Con los resultados de las herramientas anteriores, responde al usuario de forma clara y concisa. No muestres SQL ni detalles técnicos."),
            ("user", f"Resultados:\n{chr(10).join(t['result'] for t in tool_results)}"),
        ])
        final_chain = final_prompt | get_llm(temperature=0.1) | StrOutputParser()
        final_response = await final_chain.ainvoke({})
    else:
        final_response = getattr(response, "content", "") or "No pude procesar esa consulta."

    logger.info("Knowledge agent response (%d chars)", len(final_response))
    return {"agent_response": final_response}