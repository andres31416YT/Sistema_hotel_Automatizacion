"""
Herramientas de fecha y hora en tiempo real (Peru, UTC-5).
Todos los valores se calculan en el momento de la llamada, nunca se cachean.
"""

from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

PERU_TZ = timezone(timedelta(hours=-5))


def _now() -> datetime:
    """Devuelve la fecha/hora actual en zona horaria de Peru."""
    return datetime.now(PERU_TZ)


def get_current_datetime(format: str = "iso") -> dict:
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

    return {"result": formatters[fmt]()}


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


# ── Clase wrapper compatible con McpDateTime ───────────────────────────────────

class HerramientasFecha:
    """Wrapper de herramientas de fecha/hora para usar como MCP toolset."""

    def get_current_datetime(self, format: str = "iso") -> dict:
        return get_current_datetime(format=format)

    def get_current_date(self) -> dict:
        return get_current_date()

    def get_current_time(self) -> dict:
        return get_current_time()

    def get_day_of_week(self) -> dict:
        return get_day_of_week()
