"""WhatsApp client for sending messages via the Business API."""
import logging
import httpx
from lib.config import settings

logger = logging.getLogger(__name__)


class WhatsAppClient:
    def __init__(self):
        self.api_url = f"https://graph.facebook.com/v18.0"
        self.token = settings.whatsapp_token  # optional, loaded from .env if present
        self.phone_id = settings.whatsapp_phone_number_id  # optional

    def _headers(self) -> dict:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def send_text(self, to: str, message: str) -> dict:
        """Send a text message to a WhatsApp number."""
        if not self.token or not self.phone_id:
            logger.warning("WhatsApp credentials not configured")
            return {"status": "skipped", "reason": "no_credentials"}

        url = f"{self.api_url}/{self.phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": message},
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=payload, headers=self._headers())
            if resp.status_code >= 400:
                logger.error("WhatsApp send failed: %s", resp.text)
                return {"status": "error", "code": resp.status_code}
            return {"status": "sent", "response": resp.json()}
        except Exception as exc:
            logger.error("WhatsApp send exception: %s", exc)
            return {"status": "error", "exception": str(exc)}

    def send_template(self, to: str, template_name: str, language: str = "es", components: list | None = None) -> dict:
        """Send a template message."""
        if not self.token or not self.phone_id:
            return {"status": "skipped", "reason": "no_credentials"}
        url = f"{self.api_url}/{self.phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components or [],
            },
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=payload, headers=self._headers())
            return {"status": "sent" if resp.status_code < 400 else "error", "response": resp.json()}
        except Exception as exc:
            logger.error("WhatsApp template exception: %s", exc)
            return {"status": "error", "exception": str(exc)}


whatsapp_client = WhatsAppClient()