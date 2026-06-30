#!/bin/sh
set -e

NGROK_API_URL="${NGROK_API_URL:-http://ngrok-core:4040}"
OPENWA_ENV_FILE="/project/services/whatsapp/open_wa/.env"
WEBHOOK_PATH="/webhooks/openwa"

echo "[NGROK-CORE-WEBHOOK] Waiting for ngrok API..."
for i in $(seq 1 60); do
  if curl -sf "${NGROK_API_URL}/api/tunnels" > /dev/null 2>&1; then
    echo "[NGROK-CORE-WEBHOOK] ngrok API is ready."
    break
  fi
  sleep 1
done

PUBLIC_URL=$(curl -sf "${NGROK_API_URL}/api/tunnels" | grep -o '"public_url":"[^"]*' | head -1 | cut -d'"' -f4)

if [ -z "$PUBLIC_URL" ]; then
  echo "[NGROK-CORE-WEBHOOK] ERROR: Could not detect ngrok public URL."
  exit 1
fi

echo "[NGROK-CORE-WEBHOOK] Detected public URL: ${PUBLIC_URL}"

FULL_WEBHOOK_URL="${PUBLIC_URL}${WEBHOOK_PATH}"
echo "[NGROK-CORE-WEBHOOK] Full webhook URL: ${FULL_WEBHOOK_URL}"

if [ -f "$OPENWA_ENV_FILE" ]; then
  TMP_FILE=$(mktemp)
  if grep -q '^OPENWA_WEBHOOK_URL=' "$OPENWA_ENV_FILE"; then
    grep -v '^OPENWA_WEBHOOK_URL=' "$OPENWA_ENV_FILE" > "$TMP_FILE"
    echo "OPENWA_WEBHOOK_URL=${FULL_WEBHOOK_URL}" >> "$TMP_FILE"
  else
    echo "OPENWA_WEBHOOK_URL=${FULL_WEBHOOK_URL}" > "$TMP_FILE"
  fi
  cat "$TMP_FILE" > "$OPENWA_ENV_FILE"
  rm -f "$TMP_FILE"
  echo "[NGROK-CORE-WEBHOOK] Updated OpenWA .env with webhook URL."
else
  echo "[NGROK-CORE-WEBHOOK] WARNING: OpenWA .env not found at $OPENWA_ENV_FILE"
fi
