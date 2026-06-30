#!/bin/sh
set -e

NGROK_API_URL="${NGROK_API_URL:-http://ngrok-whatsapp:4040}"
OPENWA_ENV_FILE="/project/services/whatsapp/open_wa/.env"
WEBHOOK_PATH="/webhooks/openwa"

echo "[NGROK-WEBHOOK] Waiting for ngrok API..."
for i in $(seq 1 60); do
  if curl -sf "${NGROK_API_URL}/api/tunnels" > /dev/null 2>&1; then
    echo "[NGROK-WEBHOOK] ngrok API is ready."
    break
  fi
  sleep 1
done

PUBLIC_URL=$(curl -sf "${NGROK_API_URL}/api/tunnels" | grep -o '"public_url":"[^"]*' | head -1 | cut -d'"' -f4)

if [ -z "$PUBLIC_URL" ]; then
  echo "[NGROK-WEBHOOK] ERROR: Could not detect ngrok public URL."
  exit 1
fi

echo "[NGROK-WEBHOOK] Detected public URL: ${PUBLIC_URL}"

FULL_WEBHOOK_URL="${PUBLIC_URL}${WEBHOOK_PATH}"
echo "[NGROK-WEBHOOK] Full webhook URL: ${FULL_WEBHOOK_URL}"

if [ -f "$OPENWA_ENV_FILE" ]; then
  if grep -q '^OPENWA_WEBHOOK_URL=' "$OPENWA_ENV_FILE"; then
    grep -v '^OPENWA_WEBHOOK_URL=' "$OPENWA_ENV_FILE" > "${OPENWA_ENV_FILE}.tmp"
    echo "OPENWA_WEBHOOK_URL=${FULL_WEBHOOK_URL}" >> "${OPENWA_ENV_FILE}.tmp"
    mv "${OPENWA_ENV_FILE}.tmp" "$OPENWA_ENV_FILE"
  else
    echo "OPENWA_WEBHOOK_URL=${FULL_WEBHOOK_URL}" > "$OPENWA_ENV_FILE"
  fi
  echo "[NGROK-WEBHOOK] Updated OpenWA .env with webhook URL."
else
  echo "[NGROK-WEBHOOK] WARNING: OpenWA .env not found at $OPENWA_ENV_FILE"
fi
