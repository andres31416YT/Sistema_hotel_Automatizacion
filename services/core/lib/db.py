"""Database access layer using asyncpg."""
import asyncpg
import logging
from typing import Any
from lib.config import settings

logger = logging.getLogger(__name__)


async def get_hotel_connection() -> asyncpg.Connection:
    """Create a new connection to the hotel database."""
    return await asyncpg.connect(settings.hotel_dsn, timeout=15)


async def get_payments_connection() -> asyncpg.Connection:
    """Create a new connection to the payments database."""
    return await asyncpg.connect(settings.payments_dsn, timeout=15)


async def fetch_all(query: str, params: list | None = None, connection: str = "hotel") -> list[dict[str, Any]]:
    """
    Execute a SELECT query and return all rows as dicts.
    connection: "hotel" | "payments"
    """
    dsn = settings.hotel_dsn if connection == "hotel" else settings.payments_dsn
    conn = await asyncpg.connect(dsn, timeout=15)
    try:
        rows = await conn.fetch(query, *(params or []))
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def execute_dml(query: str, params: list | None = None, connection: str = "hotel") -> dict:
    """
    Execute INSERT/UPDATE/DELETE and return affected rows info.
    DDL statements (DROP/ALTER/CREATE/TRUNCATE) are explicitly blocked.
    connection: "hotel" | "payments"
    """
    normalized = query.strip().upper()
    if normalized.startswith(("DROP ", "ALTER ", "CREATE ", "TRUNCATE ", "GRANT ", "REVOKE ")):
        raise ValueError("DDL statements are not allowed: " + query[:60])

    dsn = settings.hotel_dsn if connection == "hotel" else settings.payments_dsn
    conn = await asyncpg.connect(dsn, timeout=15)
    try:
        result = await conn.execute(query, *(params or []))
        parts = result.split()
        return {"status": parts[0], "count": int(parts[1]) if len(parts) > 1 else 0}
    except Exception as exc:
        logger.error("DML error: %s", exc)
        raise
    finally:
        await conn.close()


async def get_hotel_schema() -> dict[str, Any]:
    """Read the live database schema from information_schema."""
    conn = await get_hotel_connection()
    try:
        tables: dict[str, dict] = {}
        columns = await conn.fetch("""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """)
        fks = await conn.fetch("""
            SELECT tc.table_name, kcu.column_name,
                   ccu.table_name AS foreign_table, ccu.column_name AS foreign_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
        """)

        for c in columns:
            tn = c["table_name"]
            tables.setdefault(tn, {"columns": [], "constraints": []})
            tables[tn]["columns"].append({
                "name": c["column_name"],
                "type": c["data_type"],
                "nullable": c["is_nullable"] == "YES",
                "default": c.get("column_default"),
            })

        for fk in fks:
            tn = fk["table_name"]
            tables.setdefault(tn, {"columns": [], "constraints": []})
            tables[tn]["constraints"].append({
                "column": fk["column_name"],
                "foreign_table": fk["foreign_table"],
                "foreign_column": fk["foreign_column"],
            })

        return tables
    finally:
        await conn.close()


def schema_to_text(schema: dict) -> str:
    """Convert schema dict to readable text for prompts."""
    lines = ["BASE DE DATOS DEL HOTEL:\n"]
    for tn in sorted(schema):
        lines.append(f"Tabla: {tn}")
        for col in schema[tn]["columns"]:
            null_str = "NULL" if col["nullable"] else "NOT NULL"
            lines.append(f"  {col['name']}: {col['type']} ({null_str})")
        for cons in schema[tn]["constraints"]:
            lines.append(f"  [FK] {cons['column']} -> {cons['foreign_table']}.{cons['foreign_column']}")
    return "\n".join(lines)