"""
Constantes de fecha/hora en tiempo real para todos los agentes y MCP servers.
Se calculan en cada importacion, por lo que siempre reflejan el momento en que
se proceso el request, no el momento de inicio del contenedor.

Uso en agentes:
    from now import NOW_ISO, NOW_DATE, NOW_TIME, NOW_PRETTY

Uso desde otros procesos (variables de entorno exportadas por docker-entrypoint.sh):
    os.getenv("NOW_ISO"), os.getenv("NOW_DATE"), etc.
"""

from datetime import datetime

NOW_ISO   = datetime.now().isoformat()                      # ej: "2026-05-18T13:08:21.123456"
NOW_DATE  = datetime.now().strftime("%Y-%m-%d")              # ej: "2026-05-18"
NOW_TIME  = datetime.now().strftime("%H:%M:%S")              # ej: "13:08:21"
NOW_DATE_PRETTY = datetime.now().strftime("%d de %B de %Y")  # ej: "18 de mayo de 2026"
NOW_DATETIME_PRETTY = datetime.now().strftime("%-d de %B de %Y, %H:%M")  # ej: "18 de mayo de 2026, 13:08"
