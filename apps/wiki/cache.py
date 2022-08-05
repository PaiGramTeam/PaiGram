import ujson

from utils.redisdb import RedisDB


class WikiCache:
    def __init__(self, redis: RedisDB):
        self.client = redis.client
        self.qname = "wiki"

    async def refresh_info_cache(self, key_name: str, info):
        qname = f"{self.qname}:{key_name}"
        await self.client.set(qname, ujson.dumps(info))

    async def del_one(self, key_name: str):
        qname = f"{self.qname}:{key_name}"
        await self.client.delete(qname)

    async def get_one(self, key_name: str) -> str:
        qname = f"{self.qname}:{key_name}"
        return await self.client.get(qname)
