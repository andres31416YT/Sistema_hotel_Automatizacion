"""
MCP Server McpRouter (servicio administrativo)
Enruta mensajes entre agentes y orquesta el flujo en el lado admin.
Expone herramientas MCP sin hardcodear estructura de DB.
"""

from herramientas.datetime_utils import get_current_datetime, get_day_of_week, HerramientasFecha  # noqa: E402
from customer_service.mcp_servers.mcp_database import McpDatabase  # noqa: E402  (reusa)


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
            _logger.warning("[McpDatabase:execute_sql] error: %s", exc)
            return {"ok": False, "error": str(exc), "columns": [], "rows": [], "count": 0}
        finally:
            await conn.close()
    except Exception as exc:
        return {"ok": False, "error": f"No se pudo conectar a DB: {exc}", "columns": [], "rows": [], "count": 0}


def execute_sql(query: str, params: list | None = None) -> dict:
    """
    Herramienta MCP para que el administrador EJECUTE consultas SQL de LECTURA
    sobre la base de datos del hotel. Bloquea DML (INSERT/UPDATE/DELETE/DROP).
    Uso: execute_sql(query="SELECT * FROM reservations ORDER BY created_at DESC LIMIT 50")
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


def execute_dml(query: str, params: list | None = None) -> dict:
    """
    Herramienta MCP para que el administrador EJECUTE operaciones de ESCRITURA
    (INSERT, UPDATE, DELETE) sobre la base de datos del hotel.
    BLOQUEA DDL (DROP/ALTER/CREATE/TRUNCATE/GRANT/REVOKE).

    Uso:
      INSERT ejemplo:
        execute_dml(
          query="INSERT INTO clients (name, whatsapp_number, doc_identidad, id_tipo_documento)
          VALUES ($1, $2, $3, $4)",
          params=["Adriana Chavez", "51910841734", "74784023", 1]
        )

      UPDATE ejemplo:
        execute_dml(
          query="UPDATE rooms SET id_estado_hab=$1 WHERE id=$2",
          params=[2, 5]
        )

      DELETE ejemplo:
        execute_dml(
          query="DELETE FROM clients WHERE id=$1",
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


async def _ejecutar_dml(query: str, params: list | None = None, cmd: str = "") -> dict:
    """Ejecuta INSERT/UPDATE/DELETE y devuelve resultado."""
    try:
        conn = await asyncpg.connect(_DSN_HOTEL, timeout=15)
        try:
            if cmd == "INSERT":
                # Agregar RETURNING * automaticamente para obtener el ID insertado
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
                # UPDATE o DELETE: contar filas afectadas
                status = await conn.execute(query, *(params or []))
                # status viene como "UPDATE 3" o "DELETE 2"
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

# ── DB Payments (transacciones) ────────────────────────────────────────────────────
_DB_PAYMENTS = {
    "host":     os.getenv("DB_PAYMENTS_HOST"),
    "port":     int(os.getenv("DB_PAYMENTS_PORT", 5433)),
    "user":     os.getenv("DB_PAYMENTS_USER"),
    "password": os.getenv("DB_PAYMENTS_PASSWORD"),
    "database": os.getenv("DB_PAYMENTS_NAME"),
}
_DSN_PAYMENTS = "postgresql://{user}:{password}@{host}:{port}/{database}".format(**_DB_PAYMENTS)


async def _ejecutar_sql_payments(query: str, params: list | None = None) -> dict:
    """Ejecuta una consulta SQL de lectura sobre DB de pagos."""
    try:
        conn = await asyncpg.connect(_DSN_PAYMENTS, timeout=15)
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
            _logger.warning("[McpRouter:sql_payments] error: %s", exc)
            return {"ok": False, "error": str(exc), "columns": [], "rows": [], "count": 0}
        finally:
            await conn.close()
    except Exception as exc:
        return {"ok": False, "error": f"No se pudo conectar a DB de pagos: {exc}", "columns": [], "rows": [], "count": 0}


def execute_sql_payments(query: str, params: list | None = None) -> dict:
    """
    Ejecuta consultas SQL de LECTURA sobre la base de datos de pagos (transacciones).
    Uso: execute_sql_payments(query="SELECT * FROM transacciones ORDER BY created_at DESC LIMIT 50")
    Devuelve: {ok, columns, rows, count}
    """
    import re
    q = (query or "").strip()
    # Solo SELECT sobre transacciones/payment_links
    if not q.upper().startswith(("SELECT", "SHOW", "WITH", "EXPLAIN")):
        return {"ok": False, "error": "Solo se permiten consultas de lectura.", "columns": [], "rows": [], "count": 0}
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_ejecutar_sql_payments(q, params))
    finally:
        loop.close()
