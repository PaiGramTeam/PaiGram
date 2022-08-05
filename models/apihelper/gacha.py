import httpx

from .base import BaseResponseData


class GachaInfo:
    GACHA_LIST_URL = "https://webstatic.mihoyo.com/hk4e/gacha_info/cn_gf01/gacha/list.json"
    GACHA_INFO_URL = "https://webstatic.mihoyo.com/hk4e/gacha_info/cn_gf01/%s/zh-cn.json"

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                 "Chrome/90.0.4430.72 Safari/537.36"

    def __init__(self):
        self.headers = {
            'User-Agent': self.USER_AGENT,
        }
        self.client = httpx.AsyncClient(headers=self.headers)

    async def get_gacha_list_info(self) -> BaseResponseData:
        req = await self.client.get(self.GACHA_LIST_URL)
        if req.is_error:
            return BaseResponseData(error_message="请求错误")
        return BaseResponseData(req.json())

    async def get_gacha_info(self, gacha_id: str) -> dict:
        req = await self.client.get(self.GACHA_INFO_URL % gacha_id)
        if req.is_error:
            return {}
        return req.json()
