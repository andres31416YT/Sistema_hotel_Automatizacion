"""
MCP Server McpRouter
Enruta mensajes entre agentes y orquesta el flujo.
Expone las herramientas MCP disponibles para que el LLM las use en el
momento de armar consultas, sin necesidad de tener la estructura
de la DB hardcodeada en el prompt.
"""

from .mcp_datetime  import McpDateTime  # noqa: E402
from .mcp_database  import McpDatabase  # noqa: E402


# Catálogo de herramientas MCP disponibles
# Cada entrada describe el nombre, qué hace y cuándo usarla.
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
        "name":        "validate_column",
        "servicio":    "mcp_database",
        "description": (
            "Verifica que una columna exista en una tabla del esquema. "
            "Util despues de leer el esquema para confirmar nombres."
        ),
        "args": {"table": "nombre de la tabla", "column": "nombre de la columna"},
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
