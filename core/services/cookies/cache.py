from typing import List, Union

from core.base_service import BaseService
from core.basemodel import RegionEnum
from core.dependence.redisdb import RedisDB
from core.services.cookies.error import CookiesCachePoolExhausted
from utils.error import RegionNotFoundError

__all__ = ("PublicCookiesCache",)


class PublicCookiesCache(BaseService.Component):
    """使用优先级(score)进行排序，对使用次数最少的Cookies进行审核"""

    def __init__(self, redis: RedisDB):
        self.client = redis.client
        self.score_qname = "cookie:public"
        self.user_times_qname = "cookie:public:times"
        self.end = 20
        self.user_times_ttl = 60 * 60 * 24

    def get_public_cookies_queue_name(self, region: RegionEnum):
        if region == RegionEnum.HYPERION:
            return f"{self.score_qname}:yuanshen"
        if region == RegionEnum.HOYOLAB:
            return f"{self.score_qname}:genshin"
        raise RegionNotFoundError(region.name)

    async def putback_public_cookies(self, uid: int, region: RegionEnum):
        """重新添加单个到缓存列表
        :param uid:
        :param region:
        :return:
        """
        qname = self.get_public_cookies_queue_name(region)
        score_maps = {f"{uid}": 0}
        result = await self.client.zrem(qname, f"{uid}")
        if result == 1:
            await self.client.zadd(qname, score_maps)
        return result

    async def add_public_cookies(self, uid: Union[List[int], int], region: RegionEnum):
        """单个或批量添加到缓存列表
        :param uid:
        :param region:
        :return: 成功返回列表大小
        """
        qname = self.get_public_cookies_queue_name(region)
        if isinstance(uid, int):
            score_maps = {f"{uid}": 0}
        elif isinstance(uid, list):
            score_maps = {f"{i}": 0 for i in uid}
        else:
            raise TypeError("uid variable type error")
        async with self.client.pipeline(transaction=True) as pipe:
            # nx:只添加新元素。不要更新已经存在的元素
            await pipe.zadd(qname, score_maps, nx=True)
            await pipe.zcard(qname)
            add, count = await pipe.execute()
            return int(add), count

    async def get_public_cookies(self, region: RegionEnum):
        """从缓存列表获取
        :param region:
        :return:
        """
        qname = self.get_public_cookies_queue_name(region)
        scores = await self.client.zrange(qname, 0, self.end, withscores=True, score_cast_func=int)
        if len(scores) <= 0:
            raise CookiesCachePoolExhausted
        key = scores[0][0]
        score = scores[0][1]
        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.zincrby(qname, 1, key)
            await pipe.execute()
        return int(key), score + 1

    async def delete_public_cookies(self, uid: int, region: RegionEnum):
        qname = self.get_public_cookies_queue_name(region)
        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.zrem(qname, uid)
            return await pipe.execute()

    async def get_public_cookies_count(self, limit: bool = True):
        async with self.client.pipeline(transaction=True) as pipe:
            if limit:
                await pipe.zcount(0, self.end)
            else:
                await pipe.zcard(self.score_qname)
            return await pipe.execute()

    async def incr_by_user_times(self, user_id: Union[List[int], int], amount: int = 1):
        qname = f"{self.user_times_qname}:{user_id}"
        times = await self.client.incrby(qname, amount)
        if times <= 1:
            await self.client.expire(qname, self.user_times_ttl)
        return times
