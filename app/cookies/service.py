from app.cookies.repositories import CookiesRepository
from model.base import ServiceEnum


class CookiesService:
    def __init__(self, cookies_repository: CookiesRepository) -> None:
        self._repository: CookiesRepository = cookies_repository

    async def update_cookies(self, user_id: int, cookies: str, region: RegionEnum):
        await self._repository.update_cookies(user_id, cookies, region)

    async def add_cookies(self, user_id: int, cookies: str, region: RegionEnum):
        await self._repository.add_cookies(user_id, cookies, region)

    async def get_cookies(self, user_id: int, region: RegionEnum):
        return await self._repository.get_cookies(user_id, region)

    async def read_cookies(self, user_id: int, default_service: ServiceEnum):
        return await self._repository.read_cookies(user_id, default_service)
