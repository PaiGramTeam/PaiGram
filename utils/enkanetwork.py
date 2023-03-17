import json
from typing import Dict, Any, Optional, TYPE_CHECKING

from enkanetwork import Cache

if TYPE_CHECKING:
    from redis import asyncio as aioredis

__all__ = ("RedisCache",)


class RedisCache(Cache):
    def __init__(self, redis: "aioredis.Redis", key: Optional[str] = None, ex: int = 60 * 3) -> None:
        self.redis = redis
        self.ex = ex
        self.key = key

    def get_qname(self, key):
        return f"{self.key}:{key}" if self.key else f"enka_network:{key}"

    async def get(self, key) -> Optional[Dict[str, Any]]:
        qname = self.get_qname(key)
        data = await self.redis.get(qname)
        if data:
            json_data = str(data, encoding="utf-8")
            return json.loads(json_data)
        return None

    async def set(self, key, value) -> None:
        qname = self.get_qname(key)
        data = json.dumps(value)
        await self.redis.set(qname, data, ex=self.ex)

    async def exists(self, key) -> int:
        qname = self.get_qname(key)
        return await self.redis.exists(qname)

    async def ttl(self, key) -> int:
        qname = self.get_qname(key)
        return await self.redis.ttl(qname)
