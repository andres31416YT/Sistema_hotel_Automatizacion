"""Guard agent node: security validation."""
import logging
from langchain_core.messages import HumanMessage
from lib.security import is_admin, validate_sender, validate_message_content

logger = logging.getLogger(__name__)


async def guard_node(state: dict) -> dict:
    phone = state.get("phone", "")
    message = state.get("message", "")

    sender_valid = validate_sender(phone)
    content_valid = validate_message_content(message, phone)

    if not sender_valid:
        logger.warning("Blocked invalid sender: %s", phone)
        return {
            "security_valid": False,
            "blocked_reason": "invalid_sender",
        }

    if not content_valid:
        logger.warning("Blocked unsafe content from %s", phone)
        return {
            "security_valid": False,
            "blocked_reason": "unsafe_content",
        }

    logger.info("Security check passed for %s (admin=%s)", phone, is_admin(phone))
    return {
        "security_valid": True,
        "blocked_reason": None,
    }