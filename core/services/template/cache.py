import gzip
import pickle  # nosec B403
from hashlib import sha256
from typing import Any, Optional

from core.base_service import BaseService
from core.dependence.redisdb import RedisDB

__all__ = ["TemplatePreviewCache", "HtmlToFileIdCache"]


class TemplatePreviewCache(BaseService.Component):
    """暂存渲染模板的数据用于预览"""

    def __init__(self, redis: RedisDB):
        self.client = redis.client
        self.qname = "bot:template:preview"

    async def get_data(self, key: str) -> Any:
        data = await self.client.get(self.cache_key(key))
        if data:
            # skipcq: BAN-B301
            return pickle.loads(gzip.decompress(data))  # nosec B301

    async def set_data(self, key: str, data: Any, ttl: int = 8 * 60 * 60):
        ck = self.cache_key(key)
        await self.client.set(ck, gzip.compress(pickle.dumps(data)))
        if ttl != -1:
            await self.client.expire(ck, ttl)

    def cache_key(self, key: str) -> str:
        return f"{self.qname}:{key}"


class HtmlToFileIdCache(BaseService.Component):
    """html to file_id 的缓存"""

    def __init__(self, redis: RedisDB):
        self.client = redis.client
        self.qname = "bot:template:html-to-file-id"

    async def get_data(self, html: str, file_type: str) -> Optional[str]:
        data = await self.client.get(self.cache_key(html, file_type))
        if data:
            return data.decode()

    async def set_data(self, html: str, file_type: str, file_id: str, ttl: int = 24 * 60 * 60):
        ck = self.cache_key(html, file_type)
        await self.client.set(ck, file_id)
        if ttl != -1:
            await self.client.expire(ck, ttl)

    async def delete_data(self, html: str, file_type: str) -> bool:
        return await self.client.delete(self.cache_key(html, file_type))

    def cache_key(self, html: str, file_type: str) -> str:
        key = sha256(html.encode()).hexdigest()
        return f"{self.qname}:{file_type}:{key}"
