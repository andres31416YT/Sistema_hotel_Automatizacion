#!/usr/bin/env bash
set -euo pipefail

mkdir -p /core/data

# Wait for Ollama and pull model if not present (using Python since curl not available in slim image)
wait_for_model() {
  local model="${OLLAMA_MODEL:-qwen2.5:7b}"
  local max_attempts=30
  local attempt=0
  
  while [ $attempt -lt $max_attempts ]; do
    if python3 -c "import urllib.request,json; r=urllib.request.urlopen('http://ai:11434/api/tags'); print('found' if any(m.get('name')=='$model' for m in json.loads(r.read()).get('models',[])) else '')" 2>/dev/null | grep -q found; then
      echo "[INIT] Model $model already available"
      return 0
    fi
    
    echo "[INIT] Waiting for model $model... ($((attempt+1))/$max_attempts)"
    attempt=$((attempt+1))
    sleep 2
  done
  
  echo "[INIT] Model $model not found - will download in background"
}

# Try to ensure model exists in background (non-blocking)
wait_for_model &

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
