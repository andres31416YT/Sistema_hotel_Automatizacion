# WhatsApp / OpenWA Service

Este servicio ejecuta OpenWA (https://github.com/rmyndharis/OpenWA) como gateway de WhatsApp.

## Despliegue

Se usa la imagen oficial de GitHub Container Registry (no requiere build local):

```yaml
image: ghcr.io/rmyndharis/openwa:latest
```

Puerto interno: **2785** (mapeado a **8001** en docker-compose).

## Configuración

Variables principales en `.env`:
- `OPENWA_API_KEY`: API key para autenticación (persistida en volumen `whatsapp_data`)
- `OPENWA_SESSION_ID`: Nombre de la sesión (por defecto `bot-apr`)
- `OPENWA_WEBHOOK_URL`: URL del webhook (configurada automáticamente por `openwa-bootstrap`)
- `OPENWA_WEBHOOK_SECRET`: Secreto para validación HMAC de webhooks

El volumen `whatsapp_data` persiste:
- Sesión de WhatsApp Web (QR, tokens)
- API key generada automáticamente
- Base de datos de sesión (`openwa.sqlite`)

## Uso

1. Levantar todos los servicios: `docker compose up --build -d`
2. El servicio `openwa-bootstrap` se ejecuta automáticamente y:
   - Lee/genera la API key persistida
   - Crea la sesión `bot-apr`
   - Obtiene URL pública de ngrok
   - Configura el webhook en OpenWA
   - Sincroniza credenciales a `services/core/.env`
3. Acceder al dashboard: `http://localhost:8001`
4. Escanear el QR con WhatsApp para autenticar la sesión
5. Verificar estado: `docker compose logs openwa-bootstrap`

## Webhooks

Los eventos `message.received` se envían a:
- `http://core:8080/webhooks/openwa` (interno, vía ngrok-core)

El webhook incluye firma HMAC en header `X-Hub-Signature-256`.

## Servicios Relacionados

- `openwa-bootstrap`: Inicializa credenciales y webhook (ejecución única)
- `ngrok-whatsapp`: Tunnel público para pruebas externas
- `ngrok-core`: Tunnel para webhook de mensajes