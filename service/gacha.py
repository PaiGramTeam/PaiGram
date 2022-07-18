from model.apihelper.gacha import GachaInfo
from service.cache import RedisCache
from service.repository import AsyncRepository


class GachaService:
    def __init__(self, repository: AsyncRepository, cache: RedisCache):
        self.repository = repository
        self.cache = cache
        self.gacha = GachaInfo()

    async def gacha_info(self, gacha_name: str = "角色活动", default: bool = False):
        gacha_list_info = await self.gacha.get_gacha_list_info()
        gacha_id = ""
        for gacha in gacha_list_info.data["list"]:
            if gacha["gacha_name"] == gacha_name:
                gacha_id = gacha["gacha_id"]
        if gacha_id == "":
            if default and len(gacha_list_info.data["list"]) > 0:
                gacha_id = gacha_list_info.data["list"][0]["gacha_id"]
            else:
                return {}
        gacha_info = await self.gacha.get_gacha_info(gacha_id)
        gacha_info["gacha_id"] = gacha_id
        return gacha_info
