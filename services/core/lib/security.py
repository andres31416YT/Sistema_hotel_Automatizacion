"""Security and authentication utilities."""
import logging
import re
from lib.config import settings

logger = logging.getLogger(__name__)


_SANITIZE_BLOCKS = [
    r"<environment_details>[\s\S]*?</environment_details>",
    r"<environment_details>[\s\S]*",
    r"<system>[\s\S]*?</system>",
    r"<internal>[\s\S]*?</internal>",
    r"<meta>[\s\S]*?</meta>",
    r"<\[.*?\]>[\s\S]*?<\/\[.*?\]>",
    r"Current time:.*",
    r"Working directory:.*",
    r"Workspace root folder:.*",
    r"Active file:.*",
    r"Visible files:.*",
    r"<environment_details>",
    r"</environment_details>",
    r"<thinking>[\s\S]*?</thinking>",
    r"<reasoning>[\s\S]*?</reasoning>",
    r"<scratchpad>[\s\S]*?</scratchpad>",
    r"\[Internal thinking.*?\n",
    r"\[System note.*?\n",
    r"<[^>]+>",
    r"FECHA Y HORA ACTUAL.*?\n.*?\n.*?\n.*?\n",
    r"zona horaria Perú.*?\n",
    r"UTC-5.*?\n",
    r"Ten en cuenta que la fecha actual.*?\n",
    r"la hora es \d{1,2}:\d{2}.*?\n",
    r"27 de junio.*?\n",
]


def sanitize_llm_response(text: str) -> str:
    original = text
    cleaned = text
    for pattern in _SANITIZE_BLOCKS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    result = cleaned.strip()
    if result != original:
        logger.warning("[SANITIZE] Response was sanitized (original=%d chars, final=%d chars)", len(original), len(result))
        logger.warning("[SANITIZE] Removed content preview: %s", original[:400].replace('\n', ' '))
    return result


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
    """Sanitize a name from WhatsApp profile or DB.
    Keeps the original text but removes only truly broken characters.
    """
    if not name or not isinstance(name, str):
        return ""
    cleaned = name.strip()
    if not cleaned:
        return ""
    if len(cleaned) < 2:
        return ""
    cleaned = re.sub(r'[^\w\s\-\.]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if len(cleaned) < 2:
        return ""
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