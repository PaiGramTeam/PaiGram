from model.base import ServiceEnum
from service.repository import AsyncRepository


class UserInfoFormDB:

    def __init__(self, repository: AsyncRepository):
        self.repository = repository

    async def get_user_info(self, user_id: int):
        user_info = await self.repository.read_user_info(user_id)
        mihoyo_cookie = await self.repository.read_mihoyo_cookie(user_id)
        user_info.mihoyo_cookie = mihoyo_cookie
        hoyoverse_cookie = await self.repository.read_hoyoverse_cookie(user_id)
        user_info.hoyoverse_cookie = hoyoverse_cookie
        return user_info

    async def set_cookie(self, user_id: int, cookie: str, service: ServiceEnum):
        await self.repository.set_cookie(user_id, cookie, service)

    async def set_user_info(self, user_id: int, mihoyo_game_uid: int, hoyoverse_game_uid: int, service: int):
        await self.repository.set_user_info(user_id, mihoyo_game_uid, hoyoverse_game_uid, service)
