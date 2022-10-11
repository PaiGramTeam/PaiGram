from typing import Any
import pickle
import gzip

from core.base.redisdb import RedisDB


class TemplatePreviewCache:
    '''暂存渲染模板的数据用于预览'''

    def __init__(self, redis: RedisDB):
        self.client = redis.client
        self.qname = "bot:template:preview"

    async def get_data(self, id: str) -> Any:
        data = await self.client.get(self.get_key(id))
        if data:
            return pickle.loads(gzip.decompress(data))

    async def set_data(self, id: str, data: Any, ttl: int = 8 * 60 * 60):
        key = self.get_key(id)
        await self.client.set(key, gzip.compress(pickle.dumps(data)))
        if ttl != -1:
            await self.client.expire(key, ttl)
    
    def get_key(self, id: str) -> str:
        return f"{self.qname}:{id}"
