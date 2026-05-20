"""
MCP Server McpDatabase — acceso cognitivo a la base de datos Hotel.
Expone el esquema y herramientas de lectura/escritura para que el LLM
las use sin hardcodear nombres de tablas ni columnas en el prompt.
"""

import re
import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Rutas al schema SQL (resueltas desde la raíz del paquete /core/)
_PKG_ROOT   = Path(__file__).resolve().parents[2]      # /core
_SCHEMA_DIR  = _PKG_ROOT / 'db_hotel' / 'init'
_SCHEMA_FILE = _SCHEMA_DIR / '00_schema.sql'


def _load_schema_text() -> str:
    """Lee el archivo 00_schema.sql completo."""
    try:
        with open(_SCHEMA_FILE, encoding='utf-8') as f:
            return f.read()
    except Exception as exc:
        logger.warning("[McpDatabase] No se pudo leer 00_schema.sql: %s", exc)
        return ""


# ── Parseo de esquema ────────────────────────────────────────────────────────

_SKIP = {
    'PRIMARY', 'FOREIGN', 'CONSTRAINT', 'UNIQUE', 'CHECK', 'INDEX',
    'CREATE', 'TABLE', 'IF', 'NOT', 'EXISTS', 'SMALLSERIAL', 'SERIAL',
    'DROP', 'TRIGGER', 'OR', 'REPLACE', 'FUNCTION', 'RETURNS', 'BEGIN',
    'LANGUAGE', 'plpgsql', 'DO', 'NOTHING', 'ON', 'CONFLICT', 'SELECT',
    'SMALLINT', 'INTEGER', 'BIGINT', 'VARCHAR', 'TEXT', 'DATE', 'TIMESTAMP',
    'TIMESTAMPTZ', 'BOOLEAN', 'DECIMAL', 'NUMERIC', 'FLOAT', 'DOUBLE',
}


def _is_reserved_word(word: str) -> bool:
    return bool(re.match(r'^[A-Z_][A-Z0-9_]*$', word))


def _parse_schema_summary(sql_text: str) -> str:
    """Extrae un resumen legible de tablas y columnas del SQL."""
    lines = ["ESTRUCTURA DE LA BASE DE DATOS DEL HOTEL:\n"]
    tables = re.split(r'--\s*=+\s*\n', sql_text)

    current_table = None
    for block in tables:
        block = block.strip()
        if not block:
            continue

        m = re.search(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)', block, re.IGNORECASE)
        if m:
            current_table = m.group(1)

        if current_table:
            lines.append(f"  Tabla: {current_table}")
            for col_m in re.finditer(
                    r'(\w+)\s+([\w\(\)]+(?:\s+[\w\(\)]+)*)'
                    r'(?:\s+DEFAULT\s+[^,]+)?'
                    r'(?:,?\s*--\s*(.+))?',
                    block, re.IGNORECASE):
                col_name = col_m.group(1).strip()
                col_type = col_m.group(2).strip()
                col_comment = col_m.group(3).strip() if col_m.group(3) else ""

                if col_name.upper() in _SKIP or _is_reserved_word(col_name):
                    continue
                cmt = f"  -- {col_comment}" if col_comment else ""
                lines.append(f"    {col_name}: {col_type}{cmt}")

            for cons_m in re.finditer(
                    r'FOREIGN\s+KEY\s*\(([\w,]+)\)\s*REFERENCES\s+(\w+)',
                    block, re.IGNORECASE):
                cols = cons_m.group(1)
                ref_table = cons_m.group(2)
                lines.append(f"    [FK] ({cols}) -> {ref_table}")

            current_table = None

    return "\n".join(lines)


def _parse_schema_text(sql_text: str) -> dict:
    """Devuelve el esquema estructurado como diccionario."""
    import re as _re
    tables: dict = {}

    create_blocks = _re.findall(
        r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)\s*\((.*?)\);',
        sql_text, _re.DOTALL | _re.IGNORECASE,
    )
    for table_name, body in create_blocks:
        cols = []
        for cm in _re.finditer(
                r'(\w+)\s+([\w\(\)]+(?:\s+[\w\(\)]+)*)'
                r'(?:\s+DEFAULT\s+[^,]+)?'
                r'(?:,?\s*--\s*(.+))?',
                body, _re.IGNORECASE):
            cname = cm.group(1).strip()
            ctype = cm.group(2).strip()
            ccmt  = cm.group(3).strip() if cm.group(3) else ""
            if cname.upper() in _SKIP or _is_reserved_word(cname):
                continue
            cols.append({"name": cname, "type": ctype, "comment": ccmt})

        cons = []
        for fm in _re.finditer(
                r'(?:CONSTRAINT\s+(\w+)\s+)?'
                r'FOREIGN\s+KEY\s*\(([\w,]+)\)\s*REFERENCES\s+(\w+)',
                body, _re.IGNORECASE):
            cons.append({
                "name":        fm.group(1) or "",
                "foreign_key": fm.group(2),
                "references":  fm.group(3),
            })

        tables[table_name] = {"columns": cols, "constraints": cons}

    return tables


# ── Esquema cargado al importar ─────────────────────────────────────────────

_schema_raw   = _load_schema_text()
_schema_cache: dict | None = None


def get_db_schema() -> dict:
    """
    Devuelve el esquema completo de la base de datos como diccionario,
    parseado desde 00_schema.sql.
    """
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache

    _schema_cache = _parse_schema_text(_schema_raw)
    return _schema_cache


def get_schema_short() -> str:
    """Resumen compacto del esquema — apto para insertar en prompts."""
    sql = _schema_raw or _load_schema_text()
    return _parse_schema_summary(sql)


# ── Clase MCP ─────────────────────────────────────────────────────────────────

class McpDatabase:
    """
    Servidor MCP de base de datos cognitiva.
    Expone el esquema y herramientas de lectura/escritura para el LLM.
    """

    def __init__(self):
        self._schema = get_db_schema()

    # ------------------------------------------------------------------
    # Consulta de esquema
    # ------------------------------------------------------------------

    def get_db_schema(self) -> dict:
        """Devuelve la estructura completa de la base de datos del hotel."""
        return self._schema

    def get_schema_summary(self, fmt: str = "text") -> dict:
        """Devuelve un resumen legible del esquema (texto o JSON)."""
        raw = _load_schema_text()
        if fmt == "json":
            return {"result": json.dumps(self._schema, indent=2, ensure_ascii=False)}
        return {"result": _parse_schema_summary(raw)}

    def describe_table(self, table: str) -> dict:
        """
        Devuelve la estructura detallada de una tabla específica:
        columnas, tipos, comentarios y claves foráneas.
        Args:
            table: Nombre de la tabla (ej: 'clients', 'reservations').
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
        """Verifica si una columna existe en una tabla del esquema."""
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
        """
        Ejecuta una consulta SQL de LECTURA (SELECT/SHOW/WITH).
        Lee la DB en vivo — no usa el schema cache.
        Para confirmar nombres de columnas usa get_db_schema o describe_table antes.
        """
        from .mcp_router import execute_sql as _exec_sql  # import diferido evita circular
        return _exec_sql(query, params)

    # ------------------------------------------------------------------
    # Escritura de datos (delega a execute_dml del mcp_router)
    # ------------------------------------------------------------------

    def execute_dml(self, query: str, params: list | None = None) -> dict:
        """
        Ejecuta una operación de ESCRITURA (INSERT/UPDATE/DELETE).
        BLOQUEA DDL (DROP/ALTER/CREATE/TRUNCATE).
        Para confirmar columnas y valores usa get_db_schema o describe_table antes.
        """
        from .mcp_router import execute_dml as _exec_dml  # import diferido evita circular
        return _exec_dml(query, params)

    # ------------------------------------------------------------------
    # Ayudas específicas del dominio hotelero
    # ------------------------------------------------------------------

    def get_or_create_user_profile(self, sender_id: str, contact_info: dict | None = None) -> dict:
        """
        Busca un cliente por número de WhatsApp. Si no existe, lo crea.
        Args:
            sender_id:     Número de WhatsApp (ej: '51977972106').
            contact_info:  Dict opcional con 'name' del contacto.
        Returns:
            Dict con 'id', 'name', 'doc_identidad', 'tipo_documento', 'is_new'.
        """
        sender_id = str(sender_id or "").strip()

        # 1) Buscar cliente existente
        existing = self.execute_sql(
            "SELECT id, name, doc_identidad, id_tipo_documento "
            "FROM clients WHERE whatsapp_number = $1 LIMIT 1",
            [sender_id],
        )
        if existing.get("ok") and existing["rows"]:
            row = existing["rows"][0]
            return {
                "id":             row.get("id"),
                "name":           row.get("name"),
                "doc_identidad":  row.get("doc_identidad"),
                "tipo_documento": row.get("id_tipo_documento"),
                "is_new":         False,
            }

        # 2) Crear cliente nuevo
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

    def query_availability(self, fecha: str | None, tipo_habitacion: str | None, huespedes: int = 1) -> dict:
        """
        Consulta habitaciones disponibles.
        Busca el id en estado_habitacion por código 'DISPONIBLE' usando execute_sql.
        Args:
            fecha:           Fecha de check-in en formato 'YYYY-MM-DD' o None.
            tipo_habitacion: Código o nombre del tipo de habitación (ej: 'DOBLE') o None.
            huespedes:       Número de huéspedes.
        Returns:
            Lista de habitaciones disponibles o dict con 'ok' y 'error'.
        """
        try:
            # Obtener id del estado 'DISPONIBLE'
            est = self.execute_sql(
                "SELECT id, nombre FROM estado_habitacion WHERE codigo = 'DISPONIBLE' LIMIT 1"
            )
            if not est.get("ok") or not est["rows"]:
                return {"ok": False, "error": "No se encontró el estado DISPONIBLE en estado_habitacion."}
            id_estado_disp = est["rows"][0]["id"]

            sql = (
                "SELECT r.id, r.room_number, th.nombre AS tipo_hab, eh.nombre AS estado_hab "
                "FROM rooms r "
                "JOIN tipo_habitacion th ON r.id_tipo_hab = th.id "
                "JOIN estado_habitacion eh ON r.id_estado_hab = eh.id "
                "WHERE r.id_estado_hab = $1 AND th.capacidad >= $2"
            )
            params = [id_estado_disp, int(huespedes)]

            if tipo_habitacion:
                sql += " AND th.codigo = $3"
                params.append(tipo_habitacion.upper())

            sql += " ORDER BY r.room_number LIMIT 20"
            return self.execute_sql(sql, params)

        except Exception as exc:
            logger.warning("[McpDatabase] query_availability error: %s", exc)
            return {"ok": False, "error": str(exc)}

    def get_active_reservation(self, client_wa: str) -> dict:
        """
        Devuelve la reserva activa (PENDIENTE o CONFIRMADA) del huésped.
        Args:
            client_wa: Número de WhatsApp del cliente.
        Returns:
            Dict con 'ok', 'rows' y 'columns', o 'ok' False con 'error'.
        """
        try:
            return self.execute_sql(
                "SELECT res.id, res.check_in_date, res.check_out_date, "
                "       res.total_amount, er.codigo AS estado, "
                "       r.room_number, th.nombre AS tipo_habitacion, "
                "       cl.name, cl.doc_identidad "
                "FROM reservations res "
                "JOIN clients cl       ON res.client_id       = cl.id "
                "JOIN rooms r          ON res.room_id          = r.id "
                "JOIN tipo_habitacion th ON r.id_tipo_hab     = th.id "
                "JOIN estado_reserva er ON res.id_estado       = er.id "
                "WHERE cl.whatsapp_number = $1 "
                "  AND er.codigo IN ('PENDIENTE', 'CONFIRMADA') "
                "ORDER BY res.created_at DESC LIMIT 1",
                [str(client_wa)],
            )
        except Exception as exc:
            logger.warning("[McpDatabase] get_active_reservation error: %s", exc)
            return {"ok": False, "error": str(exc)}
