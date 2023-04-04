from typing import List

from core.base_service import BaseService
from core.dependence.redisdb import RedisDB

__all__ = ["GameCache", "GameCacheForStrategy"]


class GameCache:
    qname: str

    def __init__(self, redis: RedisDB, ttl: int = 3600):
        self.client = redis.client
        self.ttl = ttl

    async def get_url_list(self, character_name: str):
        qname = f"{self.qname}:{character_name}"
        return [str(str_data, encoding="utf-8") for str_data in await self.client.lrange(qname, 0, -1)][::-1]

    async def set_url_list(self, character_name: str, str_list: List[str]):
        qname = f"{self.qname}:{character_name}"
        await self.client.ltrim(qname, 1, 0)
        await self.client.lpush(qname, *str_list)
        await self.client.expire(qname, self.ttl)
        return await self.client.llen(qname)


class GameCacheForStrategy(BaseService.Component, GameCache):
    qname = "game:strategy"
