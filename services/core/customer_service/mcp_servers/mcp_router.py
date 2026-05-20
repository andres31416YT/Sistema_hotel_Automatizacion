"""
MCP Server McpRouter (servicio al cliente)
Enruta mensajes entre agentes y orquesta el flujo en el lado huesped.
Expone herramientas MCP de base de datos (lectura y escritura) sin
hardcodear estructura de DB en los prompts.
"""

from .mcp_datetime  import McpDateTime, get_current_datetime  # noqa: E402
from .mcp_database import McpDatabase  # noqa: E402


import asyncpg, os, json, re, logging as _log

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
            _logger.warning("[McpRouter:execute_sql] error: %s", exc)
            return {"ok": False, "error": str(exc), "columns": [], "rows": [], "count": 0}
        finally:
            await conn.close()
    except Exception as exc:
        return {"ok": False, "error": f"No se pudo conectar a DB: {exc}", "columns": [], "rows": [], "count": 0}


def execute_sql(query: str, params: list | None = None) -> dict:
    """
    Herramienta MCP para EJECUTAR consultas SQL de LECTURA sobre la BD del hotel.
    BLOQUEA DML (INSERT/UPDATE/DELETE) y DDL (DROP/ALTER/CREATE/etc).

    Uso:
      execute_sql(query="SELECT * FROM rooms ORDER BY room_number LIMIT 10")

    Devuelve: {ok, columns, rows, count}
    """
    import re
    q = (query or "").strip()
    # Bloquear escritura
    if re.match(r'^(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE)\b',
                q, re.IGNORECASE):
        return {"ok": False, "error": "Solo se permiten consultas de lectura (SELECT / SHOW / WITH).",
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


async def _ejecutar_dml(query: str, params: list | None = None, cmd: str = "") -> dict:
    """Ejecuta INSERT/UPDATE/DELETE y devuelve resultado."""
    try:
        conn = await asyncpg.connect(_DSN_HOTEL, timeout=15)
        try:
            if cmd == "INSERT":
                if "returning" not in query.lower():
                    query = f"{query.rstrip(';')} RETURNING *"
                row = await conn.fetchrow(query, *(params or []))
                last_id = row[0] if row else None
                return {
                    "success": True,
                    "message":  f"Registro insertado correctamente. ID: {last_id}",
                    "rows_affected": 1,
                    "last_insert_id": last_id,
                    "error": None,
                }
            elif cmd:
                status = await conn.execute(query, *(params or []))
                m = re.match(r'\w+\s+(\d+)', status or '')
                affected = int(m.group(1)) if m else 0
                return {
                    "success": True,
                    "message":  f"Operación {cmd.lower()} ejecutada. Filas afectadas: {affected}",
                    "rows_affected": affected,
                    "last_insert_id": None,
                    "error": None,
                }
        except Exception as exc:
            _logger.warning("[McpRouter:execute_dml] error: %s", exc)
            return {"success": False, "error": str(exc), "rows_affected": 0, "last_insert_id": None}
        finally:
            await conn.close()
    except Exception as exc:
        return {"success": False, "error": f"No se pudo conectar a DB: {exc}", "rows_affected": 0, "last_insert_id": None}


def execute_dml(query: str, params: list | None = None) -> dict:
    """
    Herramienta MCP para EJECUTAR operaciones de ESCRITURA (INSERT, UPDATE, DELETE)
    sobre la base de datos del hotel.
    BLOQUEA DDL (DROP/ALTER/CREATE/TRUNCATE/GRANT/REVOKE).

    Uso INSERT:
      execute_dml(
        query="INSERT INTO clients (name, whatsapp_number, doc_identidad, id_tipo_documento)
               VALUES ($1, $2, $3, $4)",
        params=["Juan Perez", "51977972106", "74125896", 1]
      )

    Uso UPDATE:
      execute_dml(
        query="UPDATE reservations SET id_estado=$1 WHERE id=$2",
        params=[2, 5]
      )

    Uso DELETE:
      execute_dml(
        query="DELETE FROM reservations WHERE id=$1",
        params=[3]
      )

    Devuelve: {success, message, rows_affected, last_insert_id, error}
    """
    import re
    q = (query or "").strip()
    cmd = (q.split()[0].upper() if q.split() else "")

    # Bloquear operaciones DDL
    if cmd in ("DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"):
        return {"success": False, "error": f"Operación DDL '{cmd}' no permitida.", "rows_affected": 0}

    # Solo permitir DML y lectura
    if cmd not in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        return {"success": False, "error": f"Solo se permiten SELECT/INSERT/UPDATE/DELETE. Recibido: '{cmd}'", "rows_affected": 0}

    import asyncio as _asyncio
    loop = _asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_ejecutar_dml(q, params, cmd))
    finally:
        loop.close()


# ── Catálogo de herramientas MCP ────────────────────────────────────────────

MCP_TOOLS = [
    {
        "name":        "get_db_schema",
        "servicio":    "mcp_database",
        "description": (
            "Devuelve la estructura COMPLETA de la base de datos del hotel "
            "(tablas, columnas, tipos y relaciones). "
            "USARLA SIEMPRE antes de armar cualquier consulta para confirmar "
            "nombres y tipos de columnas."
        ),
        "args": {},
    },
    {
        "name":        "get_schema_summary",
        "servicio":    "mcp_database",
        "description": (
            "Devuelve un resumen legible del esquema apto para contexto de LLM. "
            "Mas ligero que get_db_schema."
        ),
        "args": {"fmt": "'text' o 'json' (opcional)"},
    },
    {
        "name":        "describe_table",
        "servicio":    "mcp_database",
        "description": (
            "Devuelve la estructura detallada de una tabla específica: "
            "columnas, tipos, constraints y claves foráneas. "
            "Útil para consultar una sola tabla sin traer todo el esquema."
        ),
        "args": {"table": "nombre de la tabla (ej: clients, reservations, rooms)"},
    },
    {
        "name":        "validate_column",
        "servicio":    "mcp_database",
        "description": (
            "Verifica que una columna exista en una tabla del esquema. "
            "Util despues de leer el esquema para confirmar nombres."
        ),
        "args": {"table": "nombre de la tabla", "column": "nombre de la columna"},
    },
    {
        "name":        "execute_sql",
        "servicio":    "mcp_database",
        "description": (
            "EJECUTA consultas SQL de LECTURA sobre la base de datos del hotel "
            "(SELECT / SHOW / WITH). "
            "USALA para consultar habitaciones, reservas, clientes, tipos, etc. "
            "Siempre usa get_db_schema o describe_table ANTES para confirmar "
            "los nombres de columnas y tablas."
        ),
        "args": {"query": "consulta SQL de lectura", "params": "lista de parámetros posicionales (opcional)"},
    },
    {
        "name":        "execute_dml",
        "servicio":    "mcp_database",
        "description": (
            "EJECUTA operaciones de ESCRITURA (INSERT / UPDATE / DELETE) sobre "
            "la base de datos del hotel. "
            "BLOQUEA DDL (DROP / ALTER / CREATE / TRUNCATE). "
            "USALA para registrar clientes, modificar reservas o actualizar habitaciones. "
            "Siempre usa get_db_schema o describe_table ANTES para confirmar "
            "nombres de columnas y valores de catálogos."
        ),
        "args": {"query": "consulta SQL de escritura", "params": "lista de parámetros posicionales (opcional)"},
    },
    {
        "name":        "get_current_datetime",
        "servicio":    "datetime",
        "description": (
            "Fecha y hora actual en Peru (UTC-5). "
            "USAR CADA VEZ que el usuario pregunte por la fecha o la hora."
        ),
        "args": {"format": "'iso', 'pretty', 'date', 'time', 'datetime'"},
    },
    {
        "name":        "get_current_date",
        "servicio":    "datetime",
        "description": "Fecha actual en Peru (YYYY-MM-DD).",
        "args": {},
    },
    {
        "name":        "get_current_time",
        "servicio":    "datetime",
        "description": "Hora actual en Peru (HH:MM:SS, UTC-5).",
        "args": {},
    },
    {
        "name":        "get_day_of_week",
        "servicio":    "datetime",
        "description": "Dia de la semana actual en espanol.",
        "args": {},
    },
    {
        "name":        "is_today_holiday",
        "servicio":    "datetime",
        "description": "Verifica si hoy es feriado.",
        "args": {"country": "'PE' por defecto"},
    },
]


class McpRouter:
    def __init__(self):
        self.datetime  = McpDateTime()
        self.database  = McpDatabase()

    # ------------------------------------------------------------------ #
    #  Acceso a herramientas                                                #
    # ------------------------------------------------------------------ #

    def list_tools(self):
        """Devuelve el catálogo de herramientas disponibles para el LLM."""
        return MCP_TOOLS

    def route_message(self, message, sender_id, intent, entities):
        return {
            "message":    message,
            "sender_id":  sender_id,
            "intent":     intent,
            "entities":   entities,
            "routed_to":  f"handler_for_{intent}",
        }

    def orchestrate_flow(self, flow_steps):
        results = []
        for step in flow_steps:
            result = {"step": step, "status": "processed"}
            results.append(result)
        return results
