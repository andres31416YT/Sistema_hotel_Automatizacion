#!/bin/sh
set -e

SESSION_NAME="${OPENWA_SESSION_ID:-bot-apr}"
EXPECTED_KEY="${OPENWA_API_KEY:-dev-admin-key}"
NGROK_API_URL="${NGROK_API_URL:-http://ngrok-core:4040}"
OPENWA_ENV_FILE="/project/services/whatsapp/open_wa/.env"
WEBHOOK_PATH="/webhooks/openwa"

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

echo "[BOOTSTRAP] Detecting ngrok public URL..."
for i in $(seq 1 60); do
  if curl -sf "${NGROK_API_URL}/api/tunnels" > /dev/null 2>&1; then
    echo "[BOOTSTRAP] ngrok API is ready."
    break
  fi
  sleep 1
done

PUBLIC_URL=$(curl -sf "${NGROK_API_URL}/api/tunnels" | grep -o '"public_url":"[^"]*' | head -1 | cut -d'"' -f4)

if [ -z "$PUBLIC_URL" ]; then
  echo "[BOOTSTRAP] ERROR: Could not detect ngrok public URL."
  exit 1
fi

echo "[BOOTSTRAP] Detected public URL: ${PUBLIC_URL}"

FULL_WEBHOOK_URL="${PUBLIC_URL}${WEBHOOK_PATH}"
echo "[BOOTSTRAP] Full webhook URL: ${FULL_WEBHOOK_URL}"

if [ -f "$OPENWA_ENV_FILE" ]; then
  if grep -q '^OPENWA_WEBHOOK_URL=' "$OPENWA_ENV_FILE"; then
    grep -v '^OPENWA_WEBHOOK_URL=' "$OPENWA_ENV_FILE" > "${OPENWA_ENV_FILE}.tmp"
    echo "OPENWA_WEBHOOK_URL=${FULL_WEBHOOK_URL}" >> "${OPENWA_ENV_FILE}.tmp"
    mv "${OPENWA_ENV_FILE}.tmp" "$OPENWA_ENV_FILE"
  else
    echo "OPENWA_WEBHOOK_URL=${FULL_WEBHOOK_URL}" > "$OPENWA_ENV_FILE"
  fi
  echo "[BOOTSTRAP] OpenWA .env updated with webhook URL."
else
  echo "[BOOTSTRAP] WARNING: OpenWA .env not found at $OPENWA_ENV_FILE"
fi

echo "[BOOTSTRAP] Cleaning old webhooks for session ${SESSION_ID}..."
OLD_WEBHOOKS=$(curl -s http://whatsapp:2785/api/sessions/${SESSION_ID}/webhooks -H "X-API-Key: ${API_KEY}")
WH_COUNT=$(echo "$OLD_WEBHOOKS" | grep -o '"id":"[^"]*' | wc -l)
echo "[BOOTSTRAP] Found ${WH_COUNT} existing webhook(s)."

if [ "$WH_COUNT" -gt 0 ]; then
  echo "$OLD_WEBHOOKS" | grep -o '"id":"[^"]*' | cut -d'"' -f4 | while read -r WH_ID; do
    echo "[BOOTSTRAP] Deleting old webhook: ${WH_ID}"
    curl -s -X DELETE "http://whatsapp:2785/api/sessions/${SESSION_ID}/webhooks/${WH_ID}" -H "X-API-Key: ${API_KEY}" > /dev/null
  done
fi

echo "[BOOTSTRAP] Registering webhook: ${FULL_WEBHOOK_URL}"
WEBHOOK_RESPONSE=$(curl -s -X POST "http://whatsapp:2785/api/sessions/${SESSION_ID}/webhooks" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"url\": \"${FULL_WEBHOOK_URL}\", \"events\": [\"message.received\"]}")
echo "[BOOTSTRAP] Webhook registration response: $WEBHOOK_RESPONSE"

echo "[BOOTSTRAP] Syncing API key and session UUID to core .env..."
CORE_ENV="/project/services/core/.env"
if [ -f "$CORE_ENV" ]; then
  grep -v '^OPENWA_API_KEY=' "$CORE_ENV" > "${CORE_ENV}.tmp" || true
  grep -v '^OPENWA_SESSION_UUID=' "${CORE_ENV}.tmp" > "${CORE_ENV}.tmp2" || true
  echo "OPENWA_API_KEY=${API_KEY}" >> "${CORE_ENV}.tmp2"
  if [ -n "$SESSION_ID" ]; then
    echo "OPENWA_SESSION_UUID=${SESSION_ID}" >> "${CORE_ENV}.tmp2"
  fi
  mv "${CORE_ENV}.tmp2" "$CORE_ENV"
  rm -f "${CORE_ENV}.tmp"
  echo "[BOOTSTRAP] Core .env updated with API key and session UUID."
else
  echo "[BOOTSTRAP] WARNING: Core .env not found at $CORE_ENV"
fi
