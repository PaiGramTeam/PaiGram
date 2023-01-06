from typing import List

from core.service import Component

from core.dependence.redisdb import RedisDB

__all__ = ["GameCache"]


class GameCache(Component):
    def __init__(self, redis: RedisDB, qname: str, ttl: int = 3600):
        self.client = redis.client
        self.qname = qname
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
