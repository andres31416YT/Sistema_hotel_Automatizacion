#!/bin/sh
set -e

SESSION_NAME="${OPENWA_SESSION_ID:-bot-apr}"

echo "[BOOTSTRAP] Waiting for OpenWA to be ready..."
for i in $(seq 1 30); do
  if curl -sf http://whatsapp:2785/ > /dev/null 2>&1; then
    echo "[BOOTSTRAP] OpenWA is ready."
    break
  fi
  sleep 1
done

API_KEY_FILE="/app/data/.api-key"
if [ -f "$API_KEY_FILE" ]; then
  API_KEY=$(tr -d '\n' < "$API_KEY_FILE")
  echo "[BOOTSTRAP] Loaded API key from volume: ${API_KEY:0:12}..."
else
  echo "[BOOTSTRAP] ERROR: API key file not found at $API_KEY_FILE"
  exit 1
fi

if [ -z "$API_KEY" ]; then
  echo "[BOOTSTRAP] ERROR: API key is empty."
  exit 1
fi

echo "[BOOTSTRAP] Ensuring OpenWA session: ${SESSION_NAME}"

CREATE_RESPONSE=$(curl -s -X POST http://whatsapp:2785/api/sessions \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"name\": \"${SESSION_NAME}\"}") || true

SESSION_ID=$(echo "$CREATE_RESPONSE" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)

if [ -z "$SESSION_ID" ]; then
  echo "[BOOTSTRAP] Session may already exist, listing sessions to find it..."
  SESSIONS_RESPONSE=$(curl -s http://whatsapp:2785/api/sessions -H "X-API-Key: ${API_KEY}")
  SESSION_ID=$(echo "$SESSIONS_RESPONSE" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)
fi

if [ -n "$SESSION_ID" ]; then
  echo "[BOOTSTRAP] Starting session: ${SESSION_ID}"
  curl -s -X POST "http://whatsapp:2785/api/sessions/${SESSION_ID}/start" \
    -H "X-API-Key: ${API_KEY}"
  echo "[BOOTSTRAP] Done. Scan QR from dashboard (http://localhost:8001) if not already authenticated."
else
  echo "[BOOTSTRAP] Failed to find or create session."
  exit 1
fi
