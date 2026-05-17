"""
Servicio de autenticacion y configuracion de administradores del Hotel.

Estrategia:
- ADMIN_PHONES: lista de numeros de WhatsApp autorizados como administradores.
  Se parsea cada vez desde la variable de entorno ADMIN_PHONES (coma-separada).
  Los admins tienen inmunidad ante bloqueos y restricciones de contenido.
- Escalable: agregar/quitar numeros solo cambiando ADMIN_PHONES en el .env del core.
- Para persistencia futura (multi-tenant, DB) reemplazar _parse_admin_phones()
  sin tocar is_admin() ni el resto de archivos.
"""

import os
import logging

logger = logging.getLogger(__name__)


def _parse_admin_phones() -> list[str]:
    """Parsea ADMIN_PHONES desde el .env del core a lista de strings."""
    raw = os.getenv("ADMIN_PHONES", "")
    return [p.strip() for p in raw.split(",") if p.strip()]


def is_admin(phone: str) -> bool:
    """
    Verifica si un numero de WhatsApp corresponde a un administrador.

    Args:
        phone: Numero de WhatsApp (se compara como string exacto).

    Returns:
        True si el numero esta en ADMIN_PHONES del .env del core.
    """
    if not phone or not isinstance(phone, str):
        return False

    admin_phones = _parse_admin_phones()
    result = phone.strip() in admin_phones

    if result:
        logger.info(f"[AUTH] Acceso ADMIN confirmado — {phone}")

    return result


def get_admin_phones() -> list[str]:
    """Devuelve la lista actual de numeros de administrador."""
    return _parse_admin_phones()
