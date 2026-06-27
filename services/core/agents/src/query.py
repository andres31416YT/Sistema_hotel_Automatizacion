"""Query agent node: execute database queries using LangChain tools."""
import logging
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from lib.ollama import get_llm
from lib.db import fetch_all, execute_dml, get_hotel_schema, schema_to_text
from lib.datetime import get_current_datetime_block

logger = logging.getLogger(__name__)

_hotel_schema_text = ""


async def _ensure_schema():
    global _hotel_schema_text
    if not _hotel_schema_text:
        try:
            schema = await get_hotel_schema()
            _hotel_schema_text = schema_to_text(schema)
        except Exception as exc:
            logger.warning("Failed to load schema: %s", exc)
            _hotel_schema_text = ""


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
async def execute_dml_tool(query: str) -> str:
    """Execute INSERT/UPDATE/DELETE (admin only). BLOQUEA DDL (DROP/ALTER/CREATE)."""
    try:
        result = await execute_dml(query)
        return f"Operación exitosa: {result['status']} en {result['count']} fila(s)."
    except Exception as exc:
        return f"Error ejecutando operación: {exc}"


@tool
async def get_db_schema() -> str:
    """Get the complete database schema with tables and columns."""
    await _ensure_schema()
    return _hotel_schema_text


def _load_prompt(is_admin: bool) -> str:
    if is_admin:
        try:
            from agents.prompt.admin import PROMPT_QUERY
            return PROMPT_QUERY
        except Exception:
            pass
    else:
        try:
            from agents.prompt.customer import PROMPT_QUERY
            return PROMPT_QUERY
        except Exception:
            pass
    return (
        "Eres un agente de consultas a base de datos del hotel.\n"
        "Usa las herramientas disponibles para responder preguntas operativas."
    )


async def query_node(state: dict) -> dict:
    await _ensure_schema()

    message = state.get("message", "")
    is_adm = state.get("is_admin", False)

    tools = [execute_sql, get_db_schema]
    if is_adm:
        tools.append(execute_dml_tool)

    llm = get_llm(temperature=0.0).bind_tools(tools)
    prompt_text = _load_prompt(is_adm)

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            f"{get_current_datetime_block()}\n\n"
            f"{prompt_text}"
        )),
        ("user", message),
    ])

    chain = prompt | llm
    response = await chain.ainvoke({})
    tool_calls = getattr(response, "tool_calls", None)
    tool_results: list[dict] = []

    if tool_calls:
        for tc in tool_calls:
            fn_name = tc["name"]
            args = tc.get("args", {})
            logger.info("Tool call: %s args=%s", fn_name, args)
            try:
                if fn_name == "execute_sql":
                    result = await execute_sql.ainvoke(args)
                elif fn_name == "execute_dml":
                    result = await execute_dml_tool.ainvoke(args)
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

    logger.info("Query agent response (%d chars)", len(final_response))
    return {"agent_response": final_response}