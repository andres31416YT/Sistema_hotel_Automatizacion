"""Query agent node: execute database queries using LangChain tools."""
import logging
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from lib.ollama import get_llm
from lib.db import fetch_all, execute_dml, get_hotel_schema, schema_to_text, HOTEL_SCHEMA_TEXT, HOTEL_SCHEMA_LOADED, load_hotel_schema
from lib.datetime import get_current_datetime_block

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


CATALOG_TABLES: set[str] = set()


def _detect_catalog_tables() -> set[str]:
    if not _hotel_schema_text:
        return set()
    tables: set[str] = set()
    current_table = ""
    for line in _hotel_schema_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Tabla: "):
            current_table = stripped.split(": ", 1)[1].strip().lower()
        if "  codigo:" in stripped and current_table:
            tables.add(current_table)
    return tables


def _should_exclude_id(query: str) -> bool:
    global CATALOG_TABLES
    if not CATALOG_TABLES:
        CATALOG_TABLES = _detect_catalog_tables()
    q = query.strip().upper()
    for tbl in CATALOG_TABLES:
        if f"FROM {tbl}" in q or f"FROM {tbl.upper()}" in q:
            return True
    return False


@tool
async def execute_sql(query: str) -> str:
    """Execute a read-only SQL query against the hotel database (SELECT, SHOW, WITH)."""
    try:
        rows = await fetch_all(query)
        if not rows:
            return "La consulta se ejecutó correctamente pero no hay resultados."
        cols = [c for c in rows[0].keys() if c != "id"] if _should_exclude_id(query) else list(rows[0].keys())
        if not cols:
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

    schema_block = f"\n\nESQUEMA DE BASE DE DATOS:\n{_hotel_schema_text}" if _hotel_schema_text else ""

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            f"{get_current_datetime_block()}\n\n"
            f"{prompt_text}"
            f"{schema_block}\n\n"
            "IMPORTANTE: Usa SOLO los nombres de tabla y columna que aparecen en el esquema anterior. "
            "Si el usuario usa lenguaje natural (ej: 'habitaciones', 'reservas', 'huespedes'), "
            "busca la tabla equivalente en el esquema (rooms, reservations, clients). "
            "No inventes nombres de tablas."
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

        final_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "IMPORTANTE: Los resultados de las herramientas son la UNICA fuente de informacion valida. "
                "Tu respuesta debe basarse EXCLUSIVAMENTE en esos resultados. "
                "NUNCA inventes datos, nunca uses conocimiento general, nunca describas entidades que no aparezcan en los resultados. "
                "NUNCA muestres IDs numericos al administrador. Solo muestra nombres, codigos y descripciones. "
                "Si hay filas, presenta ESAS filas tal cual vinieron (sin la columna id si aplica). "
                "Si no hay resultados, di 'No se encontraron registros'. "
                "No muestres SQL ni detalles tecnicos al usuario."
                f"{tables_context}"
            )),
            ("user", f"Resultados de la consulta:\n{chr(10).join(t['result'] for t in tool_results)}\n\nResponde al usuario con estos datos."),
        ])
        final_chain = final_prompt | get_llm(temperature=0.1) | StrOutputParser()
        final_response = await final_chain.ainvoke({})
    else:
        final_response = getattr(response, "content", "") or "No pude procesar esa consulta."

    logger.info("Query agent response (%d chars)", len(final_response))
    return {"agent_response": final_response}