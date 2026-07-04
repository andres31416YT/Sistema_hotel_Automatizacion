"""Query agent node: execute database queries using LangChain tools."""
import logging
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from lib.ollama import get_llm
from lib.db import fetch_all, execute_dml, HOTEL_SCHEMA_TEXT, HOTEL_SCHEMA_LOADED, load_hotel_schema
from lib.security import sanitize_llm_response

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
async def execute_sql(query: str) -> str:
    """Execute a read-only SQL query against the hotel database (SELECT, SHOW, WITH)."""
    try:
        rows = await fetch_all(query)
        if not rows:
            return "La consulta se ejecutó correctamente pero no hay resultados."
        exclude_id = True
        cols = [c for c in rows[0].keys() if not (exclude_id and c == "id")]
        if not cols:
            cols = list(rows[0].keys())
        lines = [f"{len(rows)} resultado(s):\n", " | ".join(cols), "|" + "|".join("---" for _ in cols)]
        for row in rows[:50]:
            lines.append(" | ".join(str(row.get(c, "")) for c in cols))
        result = "\n".join(lines)
        logger.info("[EXECUTE_SQL] query=%s | rows=%d | result_preview=%s", query[:80], len(rows), result[:200])
        return result
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

    lower_msg = message.lower()

    if any(k in lower_msg for k in ["habitacion", "cuarto", "room"]):
        try:
            rows = await fetch_all(
                "SELECT rooms.room_number AS numero, tipo_habitacion.nombre AS tipo, "
                "estado_habitacion.nombre AS estado "
                "FROM rooms "
                "JOIN tipo_habitacion ON rooms.id_tipo_hab = tipo_habitacion.id "
                "JOIN estado_habitacion ON rooms.id_estado_hab = estado_habitacion.id "
                "ORDER BY rooms.room_number"
            )
            cols = [c for c in rows[0].keys() if c != "id"] if rows else []
            lines = [f"{len(rows)} resultado(s):\n", " | ".join(cols), "|" + "|".join("---" for _ in cols)] if rows else []
            for row in rows[:50]:
                lines.append(" | ".join(str(row.get(c, "")) for c in cols))
            sql_result = "\n".join(lines) if lines else "No hay habitaciones registradas."
        except Exception as exc:
            sql_result = f"Error: {exc}"

        llm = get_llm(temperature=0.0)
        lc_messages = [
            SystemMessage(content="IMPORTANTE: Los resultados de la consulta son la UNICA fuente de informacion. No inventes datos. Usa listas con guiones, no tablas markdown."),
            HumanMessage(content=f"Resultados de la consulta:\n{sql_result}\n\nResponde al usuario con estos datos."),
        ]
        final_response = await llm.ainvoke(lc_messages)
        final_response = getattr(final_response, "content", str(final_response))
        logger.info("Query agent rule-based response (%d chars)", len(final_response))
        final_response = sanitize_llm_response(final_response)
        return {"agent_response": final_response}

    tools = [execute_sql, get_db_schema]
    if is_adm:
        tools.append(execute_dml_tool)

    llm = get_llm(temperature=0.0).bind_tools(tools)
    prompt_text = _load_prompt(is_adm)

    schema_block = f"\n\nESQUEMA DE BASE DE DATOS:\n{_hotel_schema_text}" if _hotel_schema_text else ""

    prompt_msgs = [
        ("system", (
            f"{prompt_text}"
            f"{schema_block}\n\n"
            "IMPORTANTE: Usa SOLO los nombres de tabla y columna del esquema. "
            "Si el usuario usa lenguaje natural (ej: 'habitaciones'), busca la tabla equivalente (rooms). "
            "No inventes nombres de tablas.\n\n"
            "REGLAS: NUNCA incluyas 'id' en SELECT sobre tablas de catalogo. "
            "NUNCA repitas fechas ni zonas horarias."
        )),
        ("user", message),
    ]

    llm_prompt = ChatPromptTemplate.from_messages(prompt_msgs)
    response = await (llm_prompt | llm).ainvoke({})
    tool_calls = getattr(response, "tool_calls", None) or []

    tool_results: list[dict] = []

    for tc in tool_calls:
        fn_name = tc.get("name", tc.get("function", {}).get("name", ""))
        args = tc.get("args", tc.get("function", {}).get("arguments", {}))
        logger.info("Tool call: %s args=%s", fn_name, args)
        try:
            if fn_name == "execute_sql":
                result = await execute_sql.ainvoke(args)
            elif fn_name == "execute_dml_tool":
                result = await execute_dml_tool.ainvoke(args)
            elif fn_name == "get_db_schema":
                result = await get_db_schema.ainvoke(args)
            else:
                result = f"Herramienta desconocida: {fn_name}"
        except Exception as exc:
            result = f"Error ejecutando {fn_name}: {exc}"
        tool_results.append({"tool": fn_name, "result": result})

    if tool_calls and tool_results:
        consulted_tables = []
        for tc in tool_calls:
            query = tc.get("args", {}).get("query", "")
            if query:
                words = query.strip().upper().split()
                if "FROM" in words:
                    idx = words.index("FROM")
                    if idx + 1 < len(words):
                        consulted_tables.append(words[idx + 1].rstrip(";").lower())

        tables_context = ""
        if consulted_tables:
            tables_context = f" Las tablas consultadas fueron: {', '.join(consulted_tables)}."

        lc_messages = [
            SystemMessage(content=f"{prompt_text}{schema_block}"),
            HumanMessage(content=message),
            AIMessage(content="", tool_calls=tool_calls),
        ]
        for tr in tool_results:
            lc_messages.append(ToolMessage(content=tr["result"], tool_call_id=tr["tool"]))
        lc_messages.append(SystemMessage(content=(
            "IMPORTANTE: Los resultados de las herramientas son la UNICA fuente de informacion valida. "
            "No inventes datos, no uses conocimiento general. "
            "No muestres SQL ni IDs numericos. Usa listas con guiones. "
            "NUNCA repitas fechas, horas ni zonas horarias."
            f"{tables_context}"
        )))
        final_response = await llm.ainvoke(lc_messages)
        final_response = getattr(final_response, "content", str(final_response))
    elif not tool_calls:
        final_response = "No pude procesar esa consulta. Por favor, intenta de nuevo."
    else:
        final_response = getattr(response, "content", "") or "No pude procesar esa consulta."

    logger.info("Query agent response (%d chars)", len(final_response))
    final_response = sanitize_llm_response(final_response)
    return {"agent_response": final_response}