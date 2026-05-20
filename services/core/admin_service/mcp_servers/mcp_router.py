"""
MCP Server McpRouter (servicio administrativo)
Enruta mensajes entre agentes y orquesta el flujo en el lado admin.
Expone herramientas MCP sin hardcodear estructura de DB.
"""

from herramientas.datetime_utils import get_current_datetime, get_day_of_week, HerramientasFecha  # noqa: E402
from customer_service.mcp_servers.mcp_database import McpDatabase  # noqa: E402  (reusa)


import asyncpg, os, json, logging as _log

_logger = _log.getLogger(__name__)

_DB_HOTEL = {
    "host":     os.getenv("DB_HOTEL_HOST"),
    "port":     int(os.getenv("DB_HOTEL_PORT", 5432)),
    "user":     os.getenv("DB_HOTEL_USER"),
    "password": os.getenv("DB_HOTEL_PASSWORD"),
    "database": os.getenv("DB_HOTEL_NAME"),
}
_DSN_HOTEL = "postgresql://{user}:{password}@{host}:{port}/{database}".format(**_DB_HOTEL)


async def _ejecutar_sql(query: str, params: list | None = None) -> dict:
    """Ejecuta una consulta SQL de lectura y devuelve filas + columnas."""
    try:
        conn = await asyncpg.connect(_DSN_HOTEL, timeout=15)
        try:
            rows = await conn.fetch(query, *(params or []))
            if rows:
                cols = list(rows[0].keys())
                data = [dict(r) for r in rows]
            else:
                cols = []
                data = []
            return {"ok": True, "columns": cols, "rows": data, "count": len(data)}
        except Exception as exc:
            _logger.warning("[McpDatabase:execute_sql] error: %s", exc)
            return {"ok": False, "error": str(exc), "columns": [], "rows": [], "count": 0}
        finally:
            await conn.close()
    except Exception as exc:
        return {"ok": False, "error": f"No se pudo conectar a DB: {exc}", "columns": [], "rows": [], "count": 0}


def execute_sql(query: str, params: list | None = None) -> dict:
    """
    Herramienta MCP para que el administrador ejecute consultas SQL de LECTURA
    sobre la base de datos del hotel. Bloquea DML (INSERT/UPDATE/DELETE/DROP).
    Uso: execute_sql(query="SELECT * FROM reservations LIMIT 50", params=None)
    Devuelve: {ok, columns, rows, count}
    """
    import re
    q = (query or "").strip()
    # Bloquear operaciones de escritura
    if re.match(r'^(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE)\b',
                q, re.IGNORECASE):
        return {"ok": False, "error": "Solo se permiten consultas de lectura (SELECT / SHOW).",
                "columns": [], "rows": [], "count": 0}
    if not q.upper().startswith(("SELECT", "SHOW", "WITH", "EXPLAIN")):
        return {"ok": False, "error": "Solo se permiten consultas de lectura (SELECT / SHOW / WITH).",
                "columns": [], "rows": [], "count": 0}
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_ejecutar_sql(q, params))
    finally:
        loop.close()


MCP_TOOLS = [
    {
        "name":        "execute_sql",
        "servicio":    "database",
        "description": (
            "EJECUTA una consulta SQL de LECTURA (SELECT) sobre la base de datos del hotel. "
            "Devuelve columnas + filas en formato JSON. "
            "BLOQUEA INSERT/UPDATE/DELETE/DROP. "
            "Ejemplo: execute_sql(query='SELECT * FROM reservations ORDER BY created_at DESC LIMIT 50')"
        ),
        "args": {"query": "SELECT ... (consulta SQL de lectura)", "params": "lista opcional de valores"},
    },
    {
        "name":        "get_db_schema",
        "servicio":    "mcp_database",
        "description": (
            "Devuelve la estructura COMPLETA de la base de datos del hotel "
            "(tablas, columnas, tipos y relaciones). "
            "USARLA SIEMPRE antes de armar cualquier consulta para confirmar nombres."
        ),
        "args": {},
    },
    {
        "name":        "get_current_datetime",
        "servicio":    "datetime",
        "description": "Fecha y hora actual en Peru (UTC-5). USA CADA VEZ que se requiera calcular fechas.",
        "args": {"format": "'iso', 'pretty', 'date', 'time', 'datetime'"},
    },
    {
        "name":        "get_current_date",
        "servicio":    "datetime",
        "description": "Fecha actual en Peru (YYYY-MM-DD).",
        "args": {},
    },
    {
        "name":        "get_day_of_week",
        "servicio":    "datetime",
        "description": "Dia de la semana actual en espanol.",
        "args": {},
    },
]


class McpRouter:
    def __init__(self):
        self.datetime  = HerramientasFecha()
        self.database  = McpDatabase()

    def list_tools(self):
        return MCP_TOOLS

    def route_message(self, message, sender_id, intent, entities):
        return {
            "message":   message,
            "sender_id": sender_id,
            "intent":    intent,
            "entities":  entities,
            "routed_to": f"handler_for_{intent}",
        }

    def orchestrate_flow(self, flow_steps):
        return [{"step": s, "status": "processed"} for s in flow_steps]
