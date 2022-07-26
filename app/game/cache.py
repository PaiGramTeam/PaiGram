from typing import List

from utils.redisdb import RedisDB


class GameStrategyCache:
    def __init__(self, redis: RedisDB, ttl: int = 3600):
        self.client = redis.client
        self.qname = "game:strategy"
        self.ttl = ttl

    async def get_url_list(self, character_name: str):
        qname = f"{self.qname}:{character_name}"
        return [str(str_data, encoding="utf-8") for str_data in await self.client.lrange(qname, 0, -1)]

    async def set_url_list(self, character_name: str, str_list: List[str]):
        qname = f"{self.qname}:{character_name}"
        await self.client.ltrim(qname, 1, 0)
        await self.client.lpush(qname, *str_list)
        await self.client.expire(qname, self.ttl)
        count = await self.client.llen(qname)
        return count
