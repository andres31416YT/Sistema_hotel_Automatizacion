"""Date and time utilities for agent prompts."""
from datetime import datetime
from zoneinfo import ZoneInfo


def get_current_datetime_block() -> str:
    """Return a formatted block with current date/time for injection into LLM prompts."""
    tz = ZoneInfo("America/Lima")
    now = datetime.now(tz)
    date_str = now.strftime("%d/%m/%Y")
    time_str = now.strftime("%H:%M")
    day_of_week = now.strftime("%A")
    day_map = {
        "Monday": "Lunes",
        "Tuesday": "Martes",
        "Wednesday": "Miércoles",
        "Thursday": "Jueves",
        "Friday": "Viernes",
        "Saturday": "Sábado",
        "Sunday": "Domingo",
    }
    day_es = day_map.get(day_of_week, day_of_week)
    return (
        f"FECHA Y HORA ACTUAL (zona horaria Perú, UTC-5):\n"
        f"  Ahora es: {time_str}\n"
        f"  Hoy es:   {day_es}, {date_str}\n"
        f"Usa esta información para calcular fechas, vencimientos, días de la semana y horarios."
    )