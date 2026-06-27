#!/usr/bin/env bash
set -euo pipefail

mkdir -p /core/data

eval "$(python3 - <<'PY'
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, '/core')
tz = ZoneInfo('America/Lima')
now = datetime.now(tz)
print(f'export NOW_ISO="{now.isoformat()}"')
print(f'export NOW_DATE="{now.strftime("%Y-%m-%d")}"')
print(f'export NOW_TIME="{now.strftime("%H:%M:%S")}"')
print(f'export NOW_DATE_PRETTY="{now.strftime("%d/%m/%Y")}"')
print(f'export NOW_DATETIME_PRETTY="{now.strftime("%d/%m/%Y %H:%M")}"')
PY
)"

export NOW_ISO NOW_DATE NOW_TIME NOW_DATE_PRETTY NOW_DATETIME_PRETTY

exec "$@"
