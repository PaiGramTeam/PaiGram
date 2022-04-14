from model.genshinhelper import GachaInfo
from service.repository import AsyncRepository
from service.cache import RedisCache


class GachaService:
    def __init__(self, repository: AsyncRepository, cache: RedisCache):
        self.repository = repository
        self.cache = cache
        self.gacha = GachaInfo()

    async def gacha_info(self, gacha_name: str = "角色活动"):
        gacha_list_info = await self.gacha.get_gacha_list_info()
        gacha_id = ""
        for gacha in gacha_list_info.data["list"]:
            if gacha["gacha_name"] == gacha_name:
                gacha_id = gacha["gacha_id"]
        if gacha_id == "":
            return {}
        gacha_info = await self.gacha.get_gacha_info(gacha_id)
        gacha_info["gacha_id"] = gacha_id
        return gacha_info