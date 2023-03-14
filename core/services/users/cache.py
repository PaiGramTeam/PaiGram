from typing import List

from core.base_service import BaseService
from core.dependence.redisdb import RedisDB

__all__ = ("UserAdminCache",)


class UserAdminCache(BaseService.Component):
    def __init__(self, redis: RedisDB):
        self.client = redis.client
        self.qname = "users:admin"

    async def ismember(self, user_id: int) -> bool:
        return await self.client.sismember(self.qname, user_id)

    async def get_all(self) -> List[int]:
        return [int(str_data) for str_data in await self.client.smembers(self.qname)]

    async def set(self, user_id: int) -> bool:
        return await self.client.sadd(self.qname, user_id)

    async def remove(self, user_id: int) -> bool:
        return await self.client.srem(self.qname, user_id)
