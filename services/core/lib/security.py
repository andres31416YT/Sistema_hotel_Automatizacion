"""Security and authentication utilities."""
import logging
import re
from lib.config import settings

logger = logging.getLogger(__name__)


def is_admin(phone: str) -> bool:
    """Check if a WhatsApp phone number belongs to an administrator."""
    if not phone or not isinstance(phone, str):
        return False
    cleaned = phone.strip()
    admin_list = settings.admin_phones_list
    result = cleaned in admin_list
    logger.info("[ADMIN_CHECK] phone=%s admin_list=%s is_admin=%s", cleaned, admin_list, result)
    return result


def sanitize_name(name: str) -> str:
    """Sanitize a name from WhatsApp profile to avoid corrupted/truncated names."""
    if not name or not isinstance(name, str):
        return "Usuario"
    cleaned = name.strip()
    if not cleaned:
        return "Usuario"
    if len(cleaned) < 2:
        return "Usuario"
    suspicious = ["non", "null", "undefined", "none", "test", "spam"]
    if cleaned.lower() in suspicious:
        return "Usuario"
    cleaned = re.sub(r'[^\w\s\-\.]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if len(cleaned) < 2:
        return "Usuario"
    return cleaned


def validate_sender(sender_id: str) -> bool:
    """Validate that the sender is not a known spam/fraud number."""
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


def validate_message_content(message: str, sender_id: str) -> bool:
    """Validate message content for security threats. Admins bypass this."""
    if not message or not isinstance(message, str):
        return False
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