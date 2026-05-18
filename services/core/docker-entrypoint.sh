#!/usr/bin/env bash
# docker-entrypoint.sh — Exporta fecha/hora actual en variables de entorno antes de iniciar uvicorn
# Evalua now.py una sola vez al arrancar para evitar multiplexar procesos.

set -euo pipefail

# Obtener fecha/hora desde now.py y exportarlas como variables de entorno
eval "$(python3 - <<'PY'
import sys
sys.path.insert(0, '/core')
from now import NOW_ISO, NOW_DATE, NOW_TIME, NOW_DATE_PRETTY, NOW_DATETIME_PRETTY
print(f'export NOW_ISO="{NOW_ISO}"')
print(f'export NOW_DATE="{NOW_DATE}"')
print(f'export NOW_TIME="{NOW_TIME}"')
print(f'export NOW_DATE_PRETTY="{NOW_DATE_PRETTY}"')
print(f'export NOW_DATETIME_PRETTY="{NOW_DATETIME_PRETTY}"')
PY
)"

export NOW_ISO NOW_DATE NOW_TIME NOW_DATE_PRETTY NOW_DATETIME_PRETTY

echo "[entrypoint] NOW_ISO=$NOW_ISO  NOW_DATE=$NOW_DATE  NOW_TIME=$NOW_TIME  NOW_DATE_PRETTY=$NOW_DATE_PRETTY  NOW_DATETIME_PRETTY=$NOW_DATETIME_PRETTY"

exec "$@"
