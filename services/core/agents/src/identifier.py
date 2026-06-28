"""Identifier agent node: identify the sender and build context."""
import logging
from lib.db import get_hotel_connection
from lib.security import sanitize_name

logger = logging.getLogger(__name__)


async def identifier_node(state: dict) -> dict:
    phone = state.get("phone", "")
    name = state.get("name", "")

    sender_info: dict = {"phone": phone, "name": name or "Usuario"}
    is_new = False

    try:
        conn = await get_hotel_connection()
        try:
            row = await conn.fetchrow(
                "SELECT id, name, doc_identidad, created_at FROM clients WHERE whatsapp_number = $1 LIMIT 1",
                phone,
            )
            if row:
                sender_info.update({
                    "client_id": row["id"],
                    "name": sanitize_name(row["name"] or name),
                    "doc_identidad": row["doc_identidad"],
                    "is_existing_client": True,
                    "created_at": str(row["created_at"]),
                })
            else:
                sender_info.update({
                    "client_id": None,
                    "is_existing_client": False,
                    "is_new_user": True,
                })
                is_new = True
                try:
                    new_row = await conn.fetchrow(
                        "INSERT INTO clients (whatsapp_number, name) VALUES ($1, $2) RETURNING id, name, created_at",
                        phone,
                        sanitize_name(name or "Usuario"),
                    )
                    if new_row:
                        sender_info["client_id"] = new_row["id"]
                        sender_info["name"] = sanitize_name(new_row["name"])
                        sender_info["created_at"] = str(new_row["created_at"])
                        sender_info["is_existing_client"] = False
                        sender_info["is_new_user"] = True
                        logger.info("Created new client %s (id=%s)", phone, new_row["id"])
                except Exception as exc:
                    logger.warning("Failed to create new client %s: %s", phone, exc)
        finally:
            await conn.close()
    except Exception as exc:
        logger.warning("Identifier DB query failed: %s", exc)

    if is_new and not name:
        sender_info["name"] = sender_info.get("name") or "Usuario"

    logger.info("Identified sender %s: %s (new=%s)", phone, sender_info.get("name"), is_new)
    return {"sender_info": sender_info}