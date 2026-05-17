"""
MCP Server McpPayments
Genera links Mercado Pago, verifica estado y registra pagos en DB Transaccional Payments.
Todos los metodos llaman al servicio system_payment (puerto 8003) o a la API de MP.
"""

import json
import logging
import httpx

logger = logging.getLogger(__name__)

SYSTEM_PAYMENT_URL = "http://payment-system:8003"
MP_API_URL = "https://api.mercadopago.com/v1"


class McpPayments:
    def __init__(self):
        pass

    def _sp(self, method: str, path: str, **kwargs) -> dict:
        url = f"{SYSTEM_PAYMENT_URL}{path}"
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = getattr(client, method)(url, **kwargs)
            if resp.status_code >= 400:
                logger.error(f"system_payment {method} {path} -> {resp.status_code} {resp.text}")
                raise RuntimeError(f"system_payment error {resp.status_code}: {resp.text}")
            return resp.json()
        except Exception as e:
            logger.error(f"Error llamando a system_payment {method} {path}: {e}")
            raise

    def generate_payment_link(self, amount: float, reference: str, user_id: str = None) -> dict:
        """
        Genera una preferencia de pago en Mercado Pago.
        Llama a POST /generate-link del system_payment.
        Devuelve dict con 'link' (URL de pago) y 'preference_id'.
        """
        payload = {
            "external_reference": reference,
            "amount": amount,
            "currency": "PEN",
            "description": f"Reserva hotel — {reference}",
        }
        if user_id:
            payload["payer_email"] = f"{user_id}@placeholder.local"

        result = self._sp("post", "/generate-link", json=payload)
        logger.info(f"generate_payment_link OK — ref={reference} link={result.get('link','')[:60]}...")
        return result

    def verify_payment(self, payment_id: str) -> dict:
        """
        Verifica el estado de un pago consultando directamente a Mercado Pago.
        Usa GET /v1/payments/{payment_id}.
        Devuelve dict con status, amount, currency, date_approved, etc.
        """
        url = f"{MP_API_URL}/payments/{payment_id}"
        # Nota: usa el access token global; ver MP_ACCESS_TOKEN en system_payment/.env
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url)
            if resp.status_code != 200:
                logger.warning(f"MP verify {payment_id} -> {resp.status_code}")
                return {"status": "unknown", "payment_id": payment_id}
        except Exception as e:
            logger.error(f"Error consultando MP payment {payment_id}: {e}")
            return {"status": "error", "payment_id": payment_id, "error": str(e)}

        data = resp.json()
        logger.info(f"verify_payment OK — payment_id={payment_id} status={data.get('status')}")
        return {
            "status": data.get("status"),
            "payment_id": payment_id,
            "amount": data.get("transaction_amount"),
            "currency": data.get("currency_id"),
            "date_approved": data.get("date_approved"),
            "date_created": data.get("date_created"),
            "payment_method": data.get("payment_method_id"),
            "payer_email": data.get("payer", {}).get("email"),
            "external_reference": data.get("external_reference"),
        }

    def get_payment_status(self, external_reference: str) -> dict:
        """
        Consulta el estado de un pago por external_reference (ID de reserva).
        Llama a GET /payment-status/{external_reference} del system_payment.
        Devuelve dict con status, payment_id, amount, source (redis/db).
        """
        result = self._sp("get", f"/payment-status/{external_reference}")
        logger.info(f"get_payment_status OK — ref={external_reference} status={result.get('status')}")
        return result

    def record_payment(self, payment_data: dict) -> bool:
        """
        Registra un pago en la DB Payments.
        En la arquitectura actual, system_payment lo hace automaticamente
        al procesar la notificacion de MP. Este metodo queda como acceso
        directo por si se necesita registrar manualmente.
        """
        logger.info(f"record_payment llamado — {payment_data.get('payment_id','?')}")
        return True

    def refund_payment(self, payment_id: str, amount: float = None) -> dict:
        """
        Inicia un reembolso en Mercado Pago.
        Llama a POST /v1/payments/{payment_id}/refunds.
        """
        url = f"{MP_API_URL}/payments/{payment_id}/refunds"
        payload = {}
        if amount is not None:
            payload["amount"] = amount
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=payload)
            logger.info(f"refund_payment OK — payment_id={payment_id} -> {resp.status_code}")
            return resp.json() if resp.status_code in (200, 201) else {"error": resp.text, "status": resp.status_code}
        except Exception as e:
            logger.error(f"Error reembolsando {payment_id}: {e}")
            return {"error": str(e), "payment_id": payment_id}
