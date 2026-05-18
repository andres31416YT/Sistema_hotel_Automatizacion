"""
MCP Server McpDateTime — herramientas de fecha y hora en tiempo real.
Todos los valores se calculan en el momento de la llamada, nunca se cachean.
"""

from datetime import (
    datetime,
    timezone,
    timedelta,
)
import logging

logger = logging.getLogger(__name__)

# Zona horaria de Peru (UTC-5)
PERU_TZ = timezone(timedelta(hours=-5))


def _now() -> datetime:
    """Devuelve la fecha/hora actual en zona horaria de Peru."""
    return datetime.now(PERU_TZ)


# ── Herramientas MCP ─────────────────────────────────────────────────────────

def get_current_datetime(format: str = "iso") -> dict:
    """
    Devuelve la fecha y hora actual en Peru.

    Args:
        format: 'iso' | 'pretty' | 'date' | 'time' | 'datetime'
            - iso        → "2026-05-18T15:30:00-05:00"
            - pretty     → "lunes, 18 de mayo de 2026, 15:30"
            - date       → "2026-05-18"
            - time       → "15:30:00"
            - datetime   → "2026-05-18 15:30:00"

    Returns:
        dict con la clave 'result'.
    """
    now = _now()

    formatters = {
        "iso":       lambda: now.isoformat(),
        "pretty":    lambda: now.strftime("%A, %-d de %B de %Y, %H:%M"),
        "date":      lambda: now.strftime("%Y-%m-%d"),
        "time":      lambda: now.strftime("%H:%M:%S"),
        "datetime":  lambda: now.strftime("%Y-%m-%d %H:%M:%S"),
    }

    fmt = format.lower()
    if fmt not in formatters:
        return {"result": f"Formato desconocido: {format!r}. Usa: iso, pretty, date, time, datetime."}

    value = formatters[fmt]()
    return {"result": value}


def get_current_date() -> dict:
    """Devuelve la fecha actual en Peru en formato YYYY-MM-DD."""
    return {"result": _now().strftime("%Y-%m-%d")}


def get_current_time() -> dict:
    """Devuelve la hora actual en Peru en formato HH:MM:SS."""
    return {"result": _now().strftime("%H:%M:%S")}


def get_day_of_week() -> dict:
    """Devuelve el dia de la semana actual en espanol."""
    days = {
        "Monday":    "lunes",
        "Tuesday":   "martes",
        "Wednesday": "miercoles",
        "Thursday":  "jueves",
        "Friday":    "viernes",
        "Saturday":  "sabado",
        "Sunday":    "domingo",
    }
    return {"result": days.get(_now().strftime("%A"), _now().strftime("%A"))}


def is_today_holiday(country: str = "PE") -> dict:
    """
    Verifica si hoy es feriado en el pais indicado.

    Args:
        country: Codigo ISO del pais (PE, AR, MX, CL, CO, etc.)

    Returns:
        dict con 'result' indicando si es feriado o no.
    """
    # Feriados fijos de Peru 2026 (ejemplo; ampliar segun necesidad)
    FERIADOS_PE_2026 = {
        "2026-01-01",  # Ano Nuevo
        "2026-04-02",  # Jueves Santo
        "2026-04-03",  # Viernes Santo
        "2026-05-01",  # Dia del Trabajo
        "2026-06-29",  # San Pedro y San Pablo
        "2026-07-28",  # Fiestas Patrias
        "2026-07-29",  # Fiestas Patrias
        "2026-08-30",  # Santa Rosa de Lima
        "2026-10-08",  # Combate de Angamos
        "2026-11-01",  # Todos los Santos
        "2026-12-25",  # Navidad
    }

    today_str = _now().strftime("%Y-%m-%d")
    is_holiday = today_str in FERIADOS_PE_2026
    return {
        "result": (
            f"Si, hoy {today_str} es feriado en Peru."
            if is_holiday
            else f"No, hoy {today_str} no es feriado en Peru."
        )
    }


# ── Registro de herramientas ─────────────────────────────────────────────────

TOOLS = [
    {
        "name":        "get_current_datetime",
        "description": (
            "Devuelve la fecha y hora actual en Peru en el formato solicitado. "
            "USAR CADA VEZ que el usuario pregunte por la fecha, hora o dia de hoy."
        ),
        "parameters": {
            "type":       "object",
            "properties": {
                "format": {
                    "type":        "string",
                    "description": "Formato de salida: iso, pretty, date, time, datetime",
                    "enum":        ["iso", "pretty", "date", "time", "datetime"],
                    "default":     "pretty",
                }
            },
            "required": [],
        },
    },
    {
        "name":        "get_current_date",
        "description": "Devuelve la fecha actual en Peru (YYYY-MM-DD).",
        "parameters":  {"type": "object", "properties": {}},
    },
    {
        "name":        "get_current_time",
        "description": "Devuelve la hora actual en Peru (HH:MM:SS, zona UTC-5).",
        "parameters":  {"type": "object", "properties": {}},
    },
    {
        "name":        "get_day_of_week",
        "description": "Devuelve el dia de la semana actual en espanol.",
        "parameters":  {"type": "object", "properties": {}},
    },
    {
        "name":        "is_today_holiday",
        "description": (
            "Verifica si hoy es feriado en el pais indicado (por defecto Peru). "
            "Usar cuando el huesped pregunte si hoy es feriado o si hay horarios especiales."
        ),
        "parameters": {
            "type":       "object",
            "properties": {
                "country": {
                    "type":        "string",
                    "description": "Codigo ISO del pais (PE, AR, MX, CL, CO, etc.)",
                    "default":     "PE",
                }
            },
            "required": [],
        },
    },
]

TOOL_MAP = {
    "get_current_datetime": get_current_datetime,
    "get_current_date":     get_current_date,
    "get_current_time":     get_current_time,
    "get_day_of_week":      get_day_of_week,
    "is_today_holiday":     is_today_holiday,
}


class McpDateTime:
    """MC Skeleton de fecha/hora — expone herramientas al LLM."""

    def __init__(self):
        pass

    def get_current_datetime(self, format: str = "iso") -> dict:
        return get_current_datetime(format=format)

    def get_current_date(self) -> dict:
        return get_current_date()

    def get_current_time(self) -> dict:
        return get_current_time()

    def get_day_of_week(self) -> dict:
        return get_day_of_week()

    def is_today_holiday(self, country: str = "PE") -> dict:
        return is_today_holiday(country=country)
