from typing import Optional

from core.dependence.redisdb import RedisDB

__all__ = [
    "GCSimCache",
]


class GCSimCache:
    qname: str = "gcsim:"

    def __init__(self, redis: RedisDB, ttl: int = 24 * 60 * 60):
        self.client = redis.client
        self.ttl = ttl

    def get_key(self, player_id: str, script_hash: int) -> str:
        return f"{self.qname}:{player_id}:{script_hash}"

    async def set_cache(self, player_id: str, script_hash: int, file_id: str) -> None:
        key = self.get_key(player_id, script_hash)
        await self.client.set(key, file_id, ex=self.ttl)

    async def get_cache(self, player_id: str, script_hash: int) -> Optional[str]:
        key = self.get_key(player_id, script_hash)
        data = await self.client.get(key)
        if data:
            return data.decode()
