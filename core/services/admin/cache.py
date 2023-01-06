from typing import List

from core.service import Component

from core.dependence.redisdb import RedisDB

__all__ = ["BotAdminCache", "GroupAdminCache"]


class BotAdminCache(Component):
    def __init__(self, redis: RedisDB):
        self.client = redis.client
        self.qname = "bot:admin"

    async def get_list(self):
        return [int(str_data) for str_data in await self.client.lrange(self.qname, 0, -1)]

    async def set_list(self, str_list: List[int], ttl: int = -1):
        await self.client.ltrim(self.qname, 1, 0)
        await self.client.lpush(self.qname, *str_list)
        if ttl != -1:
            await self.client.expire(self.qname, ttl)
        count = await self.client.llen(self.qname)
        return count


class GroupAdminCache(Component):
    def __init__(self, redis: RedisDB):
        self.client = redis.client
        self.qname = "group:admin_list"

    async def get_chat_admin(self, chat_id: int):
        qname = f"{self.qname}:{chat_id}"
        return [int(str_id) for str_id in await self.client.lrange(qname, 0, -1)]

    async def set_chat_admin(self, chat_id: int, admin_list: List[int]):
        qname = f"{self.qname}:{chat_id}"
        await self.client.ltrim(qname, 1, 0)
        await self.client.lpush(qname, *admin_list)
        await self.client.expire(qname, 60)
        count = await self.client.llen(qname)
        return count
