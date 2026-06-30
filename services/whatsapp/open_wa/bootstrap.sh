#!/bin/sh
set -e

SESSION_NAME="${OPENWA_SESSION_ID:-bot-apr}"
EXPECTED_KEY="${OPENWA_API_KEY:-dev-admin-key}"

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
  PERSISTED_KEY=$(tr -d '\n' < "$API_KEY_FILE")
  echo "[BOOTSTRAP] Persisted API key in volume: ${PERSISTED_KEY:0:12}..."
  if [ "$PERSISTED_KEY" != "$EXPECTED_KEY" ]; then
    echo "[BOOTSTRAP] WARNING: Persisted key ($PERSISTED_KEY) differs from expected ($EXPECTED_KEY)."
    echo "[BOOTSTRAP] Using persisted key for this run."
  fi
  API_KEY="$PERSISTED_KEY"
else
  echo "[BOOTSTRAP] No persisted key found. First-run mode, expecting ALLOW_DEV_API_KEY to seed dev-admin-key."
  API_KEY="$EXPECTED_KEY"
fi

echo "[BOOTSTRAP] Using API key: ${API_KEY:0:12}..."

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
  START_RESPONSE=$(curl -s -X POST "http://whatsapp:2785/api/sessions/${SESSION_ID}/start" \
    -H "X-API-Key: ${API_KEY}")
  echo "[BOOTSTRAP] Start response: $START_RESPONSE"
  echo "[BOOTSTRAP] Done. Scan QR from dashboard (http://localhost:8001) if not already authenticated."
else
  echo "[BOOTSTRAP] Failed to find or create session."
  exit 1
fi

if [ -n "$OPENWA_WEBHOOK_URL" ]; then
  echo "[BOOTSTRAP] Registering webhook: ${OPENWA_WEBHOOK_URL}"
  WEBHOOK_RESPONSE=$(curl -s -X POST "http://whatsapp:2785/api/sessions/${SESSION_ID}/webhooks" \
    -H 'Content-Type: application/json' \
    -H "X-API-Key: ${API_KEY}" \
    -d "{\"url\": \"${OPENWA_WEBHOOK_URL}\", \"events\": [\"message.received\"]}")
  echo "[BOOTSTRAP] Webhook registration response: $WEBHOOK_RESPONSE"
else
  echo "[BOOTSTRAP] No OPENWA_WEBHOOK_URL defined, skipping webhook registration."
fi

echo "[BOOTSTRAP] Syncing API key and session UUID to core .env..."
CORE_ENV="/project/services/core/.env"
if [ -f "$CORE_ENV" ]; then
  if grep -q '^OPENWA_API_KEY=' "$CORE_ENV"; then
    grep -v '^OPENWA_API_KEY=' "$CORE_ENV" > "${CORE_ENV}.tmp"
    echo "OPENWA_API_KEY=${API_KEY}" >> "${CORE_ENV}.tmp"
    cat "${CORE_ENV}.tmp" > "$CORE_ENV"
    rm -f "${CORE_ENV}.tmp"
  else
    echo "OPENWA_API_KEY=${API_KEY}" >> "$CORE_ENV"
  fi

  if [ -n "$SESSION_ID" ]; then
    if grep -q '^OPENWA_SESSION_UUID=' "$CORE_ENV"; then
      grep -v '^OPENWA_SESSION_UUID=' "$CORE_ENV" > "${CORE_ENV}.tmp"
      echo "OPENWA_SESSION_UUID=${SESSION_ID}" >> "${CORE_ENV}.tmp"
      cat "${CORE_ENV}.tmp" > "$CORE_ENV"
      rm -f "${CORE_ENV}.tmp"
    else
      echo "OPENWA_SESSION_UUID=${SESSION_ID}" >> "$CORE_ENV"
    fi
  fi

  echo "[BOOTSTRAP] Core .env updated with API key and session UUID."
else
  echo "[BOOTSTRAP] WARNING: Core .env not found at $CORE_ENV"
fi
