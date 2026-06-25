"""Payments integration: MercadoPago + local payment system."""
import logging
import httpx
from lib.config import settings

logger = logging.getLogger(__name__)


class PaymentsClient:
    def __init__(self):
        self.headers = {"Authorization": f"Bearer {settings.mp_access_token}"} if settings.mp_access_token else {}

    def _call_system(self, method: str, path: str, **kwargs) -> dict:
        url = f"{settings.system_payment_url}{path}"
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = getattr(client, method)(url, **kwargs)
            if resp.status_code >= 400:
                logger.error("payment-system %s %s -> %s", method, path, resp.status_code)
                raise RuntimeError(f"payment-system error {resp.status_code}: {resp.text}")
            return resp.json()
        except Exception as exc:
            logger.error("Payments call failed: %s", exc)
            raise

    def generate_payment_link(self, amount: float, reference: str, user_id: str, description: str = "Reserva Hotel") -> dict:
        """Generate a MercadoPago payment preference link."""
        return self._call_system("post", "/generate-link", json={
            "amount": amount,
            "reference": reference,
            "user_id": user_id,
            "description": description,
        })

    def verify_payment(self, payment_id: str) -> dict:
        """Verify a payment status with MercadoPago."""
        return self._call_system("get", f"/verify/{payment_id}")

    def record_transaction(self, data: dict) -> dict:
        """Record a new payment transaction."""
        return self._call_system("post", "/transactions", json=data)


payments_client = PaymentsClient()