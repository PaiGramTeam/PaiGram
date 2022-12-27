import json
from typing import Dict, Any, Optional

from enkanetwork import Cache
from redis import asyncio as aioredis

__all__ = ("RedisCache",)


class RedisCache(Cache):
    def __init__(self, redis: aioredis.Redis, key: Optional[str] = None, ttl: int = 60 * 3) -> None:
        self.redis = redis
        self.ttl = ttl
        self.key = key
        super().__init__(1024, 60 * 3)

    def get_qname(self, key):
        if self.key:
            return f"{self.key}:{key}"
        else:
            return f"enka_network:{key}"

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
        await self.redis.set(qname, data, ex=self.ttl)
