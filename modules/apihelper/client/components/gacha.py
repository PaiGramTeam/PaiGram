import time
from typing import List

from ..base.hyperionrequest import HyperionRequest
from ...models.genshin.gacha import GachaInfo

__all__ = ("Gacha",)


class Gacha:
    GACHA_LIST_URL = "https://webstatic.mihoyo.com/hk4e/gacha_info/cn_gf01/gacha/list.json"
    GACHA_INFO_URL = "https://webstatic.mihoyo.com/hk4e/gacha_info/cn_gf01/%s/zh-cn.json"

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.72 Safari/537.36"
    )

    def __init__(self):
        self.headers = {
            "User-Agent": self.USER_AGENT,
        }
        self.client = HyperionRequest(headers=self.headers)
        self.cache = {}
        self.cache_ttl = 600

    async def get_gacha_list_info(self) -> List[GachaInfo]:
        if self.cache.get("time", 0) + self.cache_ttl < time.time():
            self.cache.clear()
        cache = self.cache.get("gacha_list_info")
        if cache is not None:
            return cache
        req = await self.client.get(self.GACHA_LIST_URL)
        data = [GachaInfo(**i) for i in req["list"]]
        self.cache["gacha_list_info"] = data
        self.cache["time"] = time.time()
        return data

    async def get_gacha_info(self, gacha_id: str) -> dict:
        cache = self.cache.get(gacha_id)
        if cache is not None:
            return cache
        req = await self.client.get(self.GACHA_INFO_URL % gacha_id)
        self.cache[gacha_id] = req
        return req

    async def close(self):
        await self.client.shutdown()
