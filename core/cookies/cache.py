from typing import List, Union

from core.base.redisdb import RedisDB
from modules.base import RegionEnum
from utils.error import RegionNotFoundError
from .error import CookiesCachePoolExhausted


class PublicCookiesCache:
    """使用优先级(score)进行排序，对使用次数最少的Cookies进行审核"""

    def __init__(self, redis: RedisDB):
        self.client = redis.client
        self.score_qname = "cookie:public"
        self.end = 20

    def get_queue_name(self, region: RegionEnum):
        if region == RegionEnum.HYPERION:
            return self.score_qname + ":yuanshen"
        elif region == RegionEnum.HOYOLAB:
            return self.score_qname + ":genshin"
        else:
            raise RegionNotFoundError(region.name)

    async def putback(self, uid: int, region: RegionEnum):
        """重新添加单个到缓存列表
        :param uid:
        :param region:
        :return:
        """
        qname = self.get_queue_name(region)
        score_maps = {f"{uid}": 0}
        result = await self.client.zrem(qname, f"{uid}")
        if result == 1:
            await self.client.zadd(qname, score_maps)
        return result

    async def add(self, uid: Union[List[int], int], region: RegionEnum):
        """单个或批量添加到缓存列表
        :param uid:
        :param region:
        :return: 成功返回列表大小
        """
        qname = self.get_queue_name(region)
        if isinstance(uid, int):
            score_maps = {f"{uid}": 0}
        elif isinstance(uid, list):
            score_maps = {}
            for i in uid:
                score_maps[f"{i}"] = 0
        else:
            raise TypeError(f"uid variable type error")
        async with self.client.pipeline(transaction=True) as pipe:
            # nx:只添加新元素。不要更新已经存在的元素
            await pipe.zadd(qname, score_maps, nx=True)
            await pipe.zcard(qname)
            add, count = await pipe.execute()
            return int(add), count

    async def get(self, region: RegionEnum):
        """从缓存列表获取
        :param region:
        :return:
        """
        qname = self.get_queue_name(region)
        scores = await self.client.zrevrange(qname, 0, self.end, withscores=True, score_cast_func=int)
        if len(scores) > 0:
            def take_score(elem):
                return elem[1]
            scores.sort(key=take_score)
            key = scores[0][0]
            score = scores[0][1]
        else:
            raise CookiesCachePoolExhausted
        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.zincrby(qname, 1, key)
            await pipe.execute()
        return int(key), score + 1

    async def delete(self, uid: int, region: RegionEnum):
        qname = self.get_queue_name(region)
        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.zrem(qname, uid)
            return await pipe.execute()

    async def count(self, limit: bool = True):
        async with self.client.pipeline(transaction=True) as pipe:
            if limit:
                await pipe.zcount(0, self.end)
            else:
                await pipe.zcard(self.score_qname)
            return await pipe.execute()
