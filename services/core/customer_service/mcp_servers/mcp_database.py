"""
MCP Server McpDatabase — acceso cognitivo a la base de datos Hotel.
Lee el esquema desde information_schema de la BD en tiempo real.
Expone herramientas de lectura/escritura para que el LLM las use sin
hardcodear nombres de tablas ni columnas en el prompt.
"""

import json
import logging
import asyncpg
import os

logger = logging.getLogger(__name__)

_DB_HOTEL = {
    "host":     os.getenv("DB_HOTEL_HOST"),
    "port":     int(os.getenv("DB_HOTEL_PORT", 5432)),
    "user":     os.getenv("DB_HOTEL_USER"),
    "password": os.getenv("DB_HOTEL_PASSWORD"),
    "database": os.getenv("DB_HOTEL_NAME"),
}
_DSN_HOTEL = "postgresql://{user}:{password}@{host}:{port}/{database}".format(**_DB_HOTEL)


async def _fetch_schema() -> dict:
    """Lee el esquema completo desde information_schema de la BD."""
    try:
        conn = await asyncpg.connect(_DSN_HOTEL, timeout=15)
        try:
            rows = await conn.fetch("""
                SELECT table_name, column_name, data_type, is_nullable,
                       column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """)
            fk_rows = await conn.fetch("""
                SELECT tc.table_name, kcu.column_name,
                       ccu.table_name AS foreign_table,
                       ccu.column_name AS foreign_column
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
                ORDER BY tc.table_name, kcu.column_name
            """)
            tables: dict = {}
            for r in rows:
                tn = r["table_name"]
                col = {
                    "name":         r["column_name"],
                    "type":         r["data_type"],
                    "nullable":     r["is_nullable"] == "YES",
                    "default":      r.get("column_default"),
                }
                tables.setdefault(tn, {"columns": [], "constraints": []})
                tables[tn]["columns"].append(col)

            for fk in fk_rows:
                tn = fk["table_name"]
                tables.setdefault(tn, {"columns": [], "constraints": []})
                tables[tn]["constraints"].append({
                    "column":         fk["column_name"],
                    "foreign_table":  fk["foreign_table"],
                    "foreign_column": fk["foreign_column"],
                })

            return tables
        finally:
            await conn.close()
    except Exception as exc:
        logger.warning("[McpDatabase] Error leyendo information_schema: %s", exc)
        return {}


def _schema_to_summary(schema: dict) -> str:
    """Convierte dict de esquema a texto legible para prompts."""
    lines = ["ESTRUCTURA DE LA BASE DE DATOS DEL HOTEL (leida desde la BD en vivo):\n"]
    for tn in sorted(schema):
        lines.append(f"  Tabla: {tn}")
        for col in schema[tn]["columns"]:
            null_str = "NULL" if col["nullable"] else "NOT NULL"
            lines.append(f"    {col['name']}: {col['type']} ({null_str})")
        for cons in schema[tn]["constraints"]:
            lines.append(f"    [FK] {cons['column']} -> {cons['foreign_table']}.{cons['foreign_column']}")
    return "\n".join(lines)


# ── Cache ─────────────────────────────────────────────────────────────────────
_schema_cache: dict | None = None


def _load_schema() -> dict:
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        _schema_cache = loop.run_until_complete(_fetch_schema())
    finally:
        loop.close()
    return _schema_cache or {}


def get_db_schema() -> dict:
    """Devuelve el esquema completo de la BD como diccionario (leido desde la BD)."""
    return _load_schema()


def get_schema_short() -> str:
    """Resumen compacto del esquema — apto para insertar en prompts."""
    return _schema_to_summary(_load_schema())


# ── Clase MCP ─────────────────────────────────────────────────────────────────

class McpDatabase:
    """
    Servidor MCP de base de datos cognitiva del hotel.
    Todas las consultas de esquema se ejecutan contra la BD en vivo
    usando information_schema.
    """

    def __init__(self):
        self._schema = _load_schema()

    # ------------------------------------------------------------------
    # Consulta de esquema
    # ------------------------------------------------------------------

    def get_db_schema(self) -> dict:
        """Devuelve la estructura completa de la base de datos del hotel (leida desde la BD)."""
        return self._schema

    def get_schema_summary(self, fmt: str = "text") -> dict:
        """Devuelve un resumen legible del esquema (texto o JSON)."""
        if fmt == "json":
            return {"result": json.dumps(self._schema, indent=2, ensure_ascii=False)}
        return {"result": _schema_to_summary(self._schema)}

    def describe_table(self, table: str) -> dict:
        """
        Devuelve la estructura detallada de una tabla especifica:
        columnas, tipos, nullable y claves foraneas.
        Lee desde information_schema en la BD en vivo.
        Args:
            table: Nombre de la tabla (ej: 'clients', 'reservations', 'rooms').
        Returns:
            Dict con 'table', 'columns' y 'constraints', o mensaje de error.
        """
        t = (table or "").strip().lower()
        tbl = self._schema.get(t)
        if not tbl:
            available = sorted(self._schema.keys())
            return {"result": f"La tabla '{table}' no existe. Tablas disponibles: {available}"}
        return {"result": {"table": t, "columns": tbl["columns"], "constraints": tbl["constraints"]}}

    def validate_column(self, table: str, column: str) -> dict:
        """Verifica si una columna existe en una tabla del esquema de la BD."""
        t = (table or "").strip().lower()
        c = (column or "").strip().lower()
        tbl = self._schema.get(t)
        if not tbl:
            return {"result": f"La tabla '{table}' no existe en el esquema."}
        cols = {col["name"] for col in tbl["columns"]}
        return {"result": "OK" if c in cols else f"La columna '{column}' no existe en '{table}'. Columnas: {sorted(cols)}"}

    # ------------------------------------------------------------------
    # Lectura de datos (delega a execute_sql del mcp_router)
    # ------------------------------------------------------------------

    def execute_sql(self, query: str, params: list | None = None) -> dict:
        """Ejecuta una consulta SQL de LECTURA (SELECT/SHOW/WITH) contra la BD."""
        from .mcp_router import execute_sql as _exec_sql
        return _exec_sql(query, params)

    # ------------------------------------------------------------------
    # Escritura de datos (delega a execute_dml del mcp_router)
    # ------------------------------------------------------------------

    def execute_dml(self, query: str, params: list | None = None) -> dict:
        """Ejecuta una operacion de ESCRITURA (INSERT/UPDATE/DELETE) contra la BD."""
        from .mcp_router import execute_dml as _exec_dml
        return _exec_dml(query, params)

    # ------------------------------------------------------------------
    # Ayudas especificas del dominio hotelero
    # ------------------------------------------------------------------

    def get_or_create_user_profile(self, sender_id, contact_info=None):
        """Busca cliente por WhatsApp. Si no existe, lo crea."""
        sender_id = str(sender_id or "").strip()
        existing = self.execute_sql(
            "SELECT id, name, doc_identidad, id_tipo_documento "
            "FROM clients WHERE whatsapp_number = $1 LIMIT 1",
            [sender_id],
        )
        if existing.get("ok") and existing["rows"]:
            row = existing["rows"][0]
            return {
                "id":            row.get("id"),
                "name":          row.get("name"),
                "doc_identidad": row.get("doc_identidad"),
                "tipo_documento": row.get("id_tipo_documento"),
                "is_new":        False,
            }
        name = (contact_info or {}).get("name", "Invitado")
        created = self.execute_dml(
            "INSERT INTO clients (whatsapp_number, name) VALUES ($1, $2)",
            [sender_id, name],
        )
        if created.get("success"):
            return {
                "id":     created.get("last_insert_id"),
                "name":   name,
                "is_new": True,
            }
        return {"id": None, "name": name, "is_new": True, "error": created.get("error")}

    def query_availability(self, fecha=None, tipo_habitacion=None, huespedes=1):
        """Consulta habitaciones disponibles filtrando por estado, tipo y capacidad."""
        try:
            est = self.execute_sql(
                "SELECT id FROM estado_habitacion WHERE codigo = 'DISPONIBLE' LIMIT 1"
            )
            if not est.get("ok") or not est["rows"]:
                return {"ok": False, "error": "No se encontro el estado DISPONIBLE."}
            id_estado_disp = est["rows"][0]["id"]

            sql = (
                "SELECT r.id, r.room_number, th.nombre AS tipo_hab, "
                "       th.capacidad, eh.nombre AS estado_hab "
                "FROM rooms r "
                "JOIN tipo_habitacion th ON r.id_tipo_hab = th.id "
                "JOIN estado_habitacion eh ON r.id_estado_hab = eh.id "
                "WHERE r.id_estado_hab = $1 AND th.capacidad >= $2"
            )
            params = [id_estado_disp, int(huespedes)]
            if tipo_habitacion:
                sql += " AND th.codigo = $3"
                params.append(tipo_habitacion.upper())
            sql += " ORDER BY r.room_number"
            return self.execute_sql(sql, params)
        except Exception as exc:
            logger.warning("[McpDatabase] query_availability error: %s", exc)
            return {"ok": False, "error": str(exc)}

    def get_active_reservation(self, client_wa):
        """Devuelve la reserva activa (PENDIENTE o CONFIRMADA) del huesped."""
        try:
            return self.execute_sql(
                "SELECT res.id, res.check_in_date, res.check_out_date, "
                "       res.total_amount, er.codigo AS estado, "
                "       r.room_number, th.nombre AS tipo_habitacion, "
                "       cl.name, cl.doc_identidad "
                "FROM reservations res "
                "JOIN clients cl ON res.client_id = cl.id "
                "JOIN rooms r ON res.room_id = r.id "
                "JOIN tipo_habitacion th ON r.id_tipo_hab = th.id "
                "JOIN estado_reserva er ON res.id_estado = er.id "
                "WHERE cl.whatsapp_number = $1 "
                "  AND er.codigo IN ('PENDIENTE', 'CONFIRMADA') "
                "ORDER BY res.created_at DESC LIMIT 1",
                [str(client_wa)],
            )
        except Exception as exc:
            logger.warning("[McpDatabase] get_active_reservation error: %s", exc)
            return {"ok": False, "error": str(exc)}

    # ── Helper para leer catalogo tipos de documento (sin cache en disco) ──

    def list_tipos_documento(self):
        """Lista los tipos de documento desde la tabla tipo_documento."""
        result = self.execute_sql("SELECT id, codigo, nombre FROM tipo_documento ORDER BY id")
        if result.get("ok") and result["rows"]:
            return result["rows"]
        return []

    def list_tipos_habitacion(self):
        """Lista los tipos de habitacion desde la tabla tipo_habitacion."""
        result = self.execute_sql(
            "SELECT id, codigo, nombre, capacidad FROM tipo_habitacion ORDER BY id"
        )
        if result.get("ok") and result["rows"]:
            return result["rows"]
        return []

    def list_estados_reserva(self):
        """Lista los estados de reserva desde la tabla estado_reserva."""
        result = self.execute_sql("SELECT id, codigo, nombre FROM estado_reserva ORDER BY id")
        if result.get("ok") and result["rows"]:
            return result["rows"]
        return []
