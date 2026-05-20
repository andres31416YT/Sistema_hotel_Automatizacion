"""
MCP Server McpDatabase — acceso cognitivo a la base de datos Hotel.
No expone SQL directo al LLM. En su lugar provee herramientas que el LLM
puede llamar para consultar la informacion de forma segura.
"""

import re
import json
import os
import logging
from pathlib import Path
logger = logging.getLogger(__name__)

# Rutas al schema SQL
# Resueltas desde la raíz del paquete /core/ (parent[2] desde mcp_servers/mcp_database.py)
_PKG_ROOT  = Path(__file__).resolve().parents[2]      # /core
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


def _parse_schema_summary(sql_text: str) -> str:
    """Extrae un resumen legible de tablas y columnas del SQL."""
    lines = ["ESTRUCTURA DE LA BASE DE DATOS DEL HOTEL:\n"]
    tables = re.split(r'--\s*=+\s*\n', sql_text)

    current_table = None
    for block in tables:
        block = block.strip()
        if not block:
            continue

        # Detectar nombre de tabla en CREATE TABLE
        m = re.search(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)', block, re.IGNORECASE)
        if m:
            current_table = m.group(1)

        if current_table:
            lines.append(f"  Tabla: {current_table}")
            # Columnas
            for col_m in re.finditer(
                    r'(\w+)\s+([\w\(\)]+(?:\s+[\w\(\)]+)*)'
                    r'(?:\s+DEFAULT\s+[^,]+)?'
                    r'(?:,?\s*--\s*(.+))?',
                    block, re.IGNORECASE):
                col_name = col_m.group(1).strip()
                col_type = col_m.group(2).strip()
                col_comment = col_m.group(3).strip() if col_m.group(3) else ""

                skip = {'PRIMARY', 'FOREIGN', 'CONSTRAINT', 'UNIQUE',
                         'CHECK', 'INDEX', 'CREATE', 'TABLE', 'IF', 'NOT',
                         'EXISTS', 'SMALLSERIAL', 'SERIAL', 'DROP', 'TRIGGER',
                         'OR', 'REPLACE', 'FUNCTION', 'RETURNS', 'BEGIN',
                         'LANGUAGE', 'plpgsql'}
                if col_name.upper() in skip:
                    continue
                if re.match(r'^[A-Z_]+$', col_name):
                    continue
                cmt = f"  -- {col_comment}" if col_comment else ""
                lines.append(f"    {col_name}: {col_type}{cmt}")

            # Constraints FK
            for cons_m in re.finditer(
                    r'FOREIGN\s+KEY\s*\(([\w,]+)\)\s*REFERENCES\s+(\w+)',
                    block, re.IGNORECASE):
                cols = cons_m.group(1)
                ref_table = cons_m.group(2)
                lines.append(f"    [FK] ({cols}) -> {ref_table}")

            current_table = None

    return "\n".join(lines)


# ── Esquema cargado al importar ─────────────────────────────────────────────

_schema_raw   = _load_schema_text()
_schema_cache: dict | None = None


def get_db_schema() -> dict:
    """
    Devuelve el esquema completo de la base de datos como diccionario.
    Cada entrada tiene 'columns' y 'constraints'.

    NO ejecuta SQL — solo lee el archivo 00_schema.sql que es la fuente de
    verdad del esquema.
    """
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache

    _schema_cache = _parse_schema_text(_schema_raw)
    return _schema_cache


def _parse_schema_text(sql_text: str) -> dict:
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
            if cname.upper() in {
                'PRIMARY','FOREIGN','CONSTRAINT','UNIQUE','CHECK',
                'INDEX','CREATE','TABLE','IF','NOT','EXISTS',
                'SMALLSERIAL','SMALLINT','SERIAL','DROP','TRIGGER',
                'OR','REPLACE','FUNCTION','RETURNS','BEGIN','LANGUAGE',
                'plpgsql','DO','NOTHING','ON','CONFLICT','SELECT',
            }:
                continue
            if _re.match(r'^[A-Z_]+$', cname):
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


# ── API síncrona para uso desde agentes / prompts ────────────────────────────

def get_schema_short() -> str:
    """Resumen compacto del esquema — apto para insertar en prompts."""
    sql = _schema_raw or _load_schema_text()
    return _parse_schema_summary(sql)


# ── Clase MCP ─────────────────────────────────────────────────────────────────

class McpDatabase:
    """
    Servidor MCP de base de datos cognitiva.
    Expone el esquema como herramienta para que el LLM lo use sin
    hardcodear tablas ni columnas en el prompt.
    """

    def __init__(self):
        self._schema = get_db_schema()

    # ------------------------------------------------------------------
    # Herramientas MCP
    # ------------------------------------------------------------------

    def get_db_schema(self) -> dict:
        """
        Devuelve la estructura completa de la base de datos del hotel.
        Lee el archivo 00_schema.sql — la fuente de verdad.
        """
        return self._schema

    def get_schema_summary(self, fmt: str = "text") -> dict:
        """
        Devuelve un resumen legible del esquema.

        Args:
            fmt: 'text' (prompt-friendly) | 'json' (estructurado)
        """
        raw = _load_schema_text()
        if fmt == "json":
            return {"result": json.dumps(self._schema, indent=2, ensure_ascii=False)}
        return {"result": _parse_schema_summary(raw)}

    def validate_column(self, table: str, column: str) -> dict:
        """
        Verifica si una columna existe en una tabla del esquema.
        Usala antes de armar una consulta para confirmar nombres correctos.
        """
        t = (table or "").strip().lower()
        c = (column or "").strip().lower()
        tbl = self._schema.get(t)
        if not tbl:
            return {"result": f"La tabla '{table}' no existe en el esquema."}
        cols = {col["name"] for col in tbl["columns"]}
        return {"result": "OK" if c in cols else f"La columna '{column}' no existe en '{table}'. Columnas: {sorted(cols)}"}
