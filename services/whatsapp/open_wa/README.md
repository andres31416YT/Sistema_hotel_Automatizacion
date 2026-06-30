# WhatsApp / OpenWA Service

Este servicio ejecuta OpenWA (https://github.com/rmyndharis/OpenWA) como gateway de WhatsApp.

## Despliegue

Se usa la imagen oficial de GitHub Container Registry (no requiere build local):

```yaml
image: ghcr.io/rmyndharis/openwa:latest
```

Puerto interno: **2785** (mapeado a **8001** en docker-compose).

## Configuración

Variables principales:
- `OPENWA_API_KEY`: API key para autenticación interna (misma que debe setear el core).
- `OPENWA_SESSION_ID`: Nombre de la sesión de WhatsApp (por defecto `hotel`).

El volumen `whatsapp_data` persiste la sesión de WhatsApp Web (QR, tokens) entre reinicios.

## Uso

1. Levantar el servicio: `docker compose up -d whatsapp`
2. Acceder al dashboard: `http://localhost:8001`
3. Escanear el QR con WhatsApp para autenticar la sesión
4. El core automáticamente configura el webhook hacia `http://core:8080/webhooks/openwa`

## Nota

No hay código fuente custom en este directorio; todo corre dentro del contenedor oficial de OpenWA.
