"""
Utilidad: lee el schema SQL de la DB del hotel y expone la estructura
en formato JSON para que los agentes de IA puedan consultarla sin
necesidad de hardcodear tablas, columnas o tipos en el prompt.
"""

import json
import os
import re

# Ruta al schema SQL (dentro del contenedor core)
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), '../../../db/db_hotel/init/00_schema.sql')
# Compatibilidad con PYTHONPATH=/core usada en el Dockerfile
SCHEMA_PATH_ALT = '/core/services/db/db_hotel/init/00_schema.sql'


def _find_schema() -> str | None:
    """Busca el archivo 00_schema.sql en las rutas conocidas."""
    for p in [SCHEMA_PATH, SCHEMA_PATH_ALT]:
        if os.path.isfile(p):
            return p
    return None


def _parse_schema(sql_content: str) -> dict:
    """
    Extrae nombres de tablas, columnas, tipos, constraints y comentarios
    del SQL sin ejecutarlo.
    """
    tables: dict = {}

    # Extraer bloques CREATE TABLE
    create_blocks = re.findall(
        r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)\s*\((.*?)\);',
        sql_content,
        re.DOTALL | re.IGNORECASE,
    )

    for table_name, body in create_blocks:
        table = {"columns": [], "constraints": [], "comment": ""}

        # Columnas
        for col_match in re.finditer(
            r'(\w+)\s+([\w\(\)]+(?:\s+[\w\(\)]+)*)'
            r'(?:\s+DEFAULT\s+[^,]+)?'
            r'(?:\s+NOT\s+NULL)?'
            r'(?:\s+REFERENCES\s+\w+\([\w]+\)[^,]*)?'
            r',?\s*(?:--.*)?(?:\n|$)',
            body,
            re.IGNORECASE,
        ):
            col_name = col_match.group(1).strip()
            col_type = col_match.group(2).strip()

            # Obtener el comentario de la línea siguiente si existe
            rest_start = col_match.end()
            tail = body[rest_start: rest_start + 120]
            comment_m = re.search(r'--\s*(.+)', tail)
            comment = comment_m.group(1).strip() if comment_m else ""

            if col_name.upper() not in {
                'PRIMARY', 'FOREIGN', 'CONSTRAINT', 'UNIQUE',
                'CHECK', 'INDEX', 'CREATE',
            }:
                table["columns"].append({
                    "name": col_name,
                    "type": col_type,
                    "comment": comment,
                })

        # Constraints de tabla
        for cons in re.finditer(
            r'CONSTRAINT\s+(\w+)\s+(.*?)(?:ON\s+DELETE\s+\w+)?(?:,?\s*)(?:\n|$)',
            body,
            re.IGNORECASE,
        ):
            table["constraints"].append({
                "name": cons.group(1).strip(),
                "definition": cons.group(2).strip(),
            })

        tables[table_name] = table

    return tables


# ── API pública ──────────────────────────────────────────────────────────────

def get_schema() -> dict:
    """
    Devuelve el esquema completo de la DB del hotel como diccionario.

    Returns:
        dict con tablas como claves, cada una con 'columns', 'constraints'
        y 'comment'.
        Si no puede leer el archivo, devuelve dict vacío.
    """
    path = _find_schema()
    if not path:
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            content = f.read()
        return _parse_schema(content)
    except Exception:
        return {}


def get_schema_summary() -> str:
    """
    Devuelve un resumen legible del esquema para incluirlo en prompts.
    """
    schema = get_schema()
    if not schema:
        return "ERROR: No se pudo leer el esquema de la base de datos."

    lines = ["ESQUEMA DE LA BASE DE DATOS DEL HOTEL:\n"]
    for table_name, info in schema.items():
        lines.append(f"Tabla: {table_name}")
        for col in info.get("columns", []):
            cmt = f"  -- {col['comment']}" if col.get("comment") else ""
            lines.append(f"  {col['name']}: {col['type']}{cmt}")
        if info.get("constraints"):
            for c in info["constraints"]:
                lines.append(f"  [FK/Constraint] {c['name']}: {c['definition']}")
        lines.append("")

    return "\n".join(lines)


# Cargar esquema una sola vez al importar el módulo
SCHEMA = get_schema()
SCHEMA_SUMMARY = get_schema_summary()
