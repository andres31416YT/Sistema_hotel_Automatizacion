"""
MCP Server McpSecurity
Valida seguridad, detecta fraude, bloquea numeros.
Los numeros de administrador se consultan via core_auth_settings.is_admin().
Para modificar la lista, cambiá ADMIN_PHONES en el .env del core.
"""

import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core_auth_settings import is_admin

logger = logging.getLogger(__name__)


class McpSecurity:
    def __init__(self):
        pass

    def validate_message_content(self, message, sender_id):
        if not message or not isinstance(message, str):
            return False

        # Los administradores no tienen restricciones de contenido
        if is_admin(sender_id):
            return True

        blocked_patterns = [
            "spam", "fraud", "virus", "malware", "hack", "phishing",
            "<script", "javascript:", "data:text/html", "vbscript:",
            "exe", "bat", "cmd", "powershell", "wscript", "cscript",
            "regsvr32", "mshta", "rundll32",
        ]
        message_lower = message.lower()
        return not any(pattern in message_lower for pattern in blocked_patterns)

    def validate_sender(self, sender_id):
        if not sender_id or not isinstance(sender_id, str):
            return False

        if is_admin(sender_id):
            return True

        blocked_patterns = [
            "spam", "test", "xxx",
            "0000000000", "1111111111", "2222222222", "3333333333",
            "4444444444", "5555555555", "6666666666", "7777777777",
            "8888888888", "9999999999",
        ]
        return sender_id not in blocked_patterns and len(sender_id) >= 10

    def is_sender_blocked(self, sender_id):
        return not self.validate_sender(sender_id)

    def block_sender(self, sender_id, reason="spam_or_fraud"):
        if is_admin(sender_id):
            logger.warning(
                f"[MCP SECURITY] No se bloquea al administrador {sender_id}"
            )
            return False

        print(f"[MCP SECURITY] Blocking sender {sender_id} — reason: {reason}")
        return True

    def unblock_sender(self, sender_id):
        print(f"[MCP SECURITY] Unblocking sender {sender_id}")
        return True