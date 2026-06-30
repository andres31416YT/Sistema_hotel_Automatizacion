"""Redis client wrapper for queues and chat history."""
import json
import logging
import asyncio
from typing import Any
import redis.asyncio as aioredis
from lib.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self):
        self._client: aioredis.Redis | None = None

    async def connect(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                decode_responses=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def push_whatsapp(self, raw_message: str) -> None:
        r = await self.connect()
        await r.lpush("whatsapp_in", raw_message)

    async def pop_whatsapp(self, timeout: int = 5) -> str | None:
        r = await self.connect()
        result = await r.brpop("whatsapp_in", timeout=timeout)
        if result:
            return result[1]
        return None

    async def get_history(self, phone: str, max_messages: int = 20) -> list[dict]:
        r = await self.connect()
        key = f"chat_history:{phone}"
        try:
            raw = await asyncio.wait_for(r.lrange(key, -max_messages, -1), timeout=3.0)
            return [json.loads(m) for m in reversed(raw) if m]
        except asyncio.TimeoutError:
            logger.warning("Timeout getting history for %s", phone)
            return []
        except Exception as exc:
            logger.warning("History error for %s: %s", phone, exc)
            return []

    async def save_inbound(self, phone: str, message: str) -> None:
        r = await self.connect()
        key = f"chat_history:{phone}"
        turn = json.dumps({"role": "user", "content": message}, ensure_ascii=False)
        await r.rpush(key, turn)
        await r.expire(key, settings.redis_ttl_chat)

    async def save_turn(self, phone: str, user_msg: str, assistant_msg: str) -> None:
        r = await self.connect()
        key = f"chat_history:{phone}"
        turn = json.dumps({"role": "user", "content": user_msg}, ensure_ascii=False)
        await r.rpush(key, turn)
        turn = json.dumps({"role": "assistant", "content": assistant_msg}, ensure_ascii=False)
        await r.rpush(key, turn)
        await r.expire(key, settings.redis_ttl_chat)


redis_client = RedisClient()