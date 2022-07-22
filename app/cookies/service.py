from app.cookies.repositories import CookiesRepository
from model.base import ServiceEnum


class CookiesService:
    def __init__(self, user_repository: CookiesRepository) -> None:
        self._repository: CookiesRepository = user_repository

    async def update_cookie(self, user_id: int, cookies: str, default_service: ServiceEnum):
        await self._repository.update_cookie(user_id, cookies, default_service)

    async def set_cookie(self, user_id: int, cookies: str, default_service: ServiceEnum):
        await self._repository.set_cookie(user_id, cookies, default_service)

    async def read_cookies(self, user_id: int, default_service: ServiceEnum):
        return await self._repository.read_cookies(user_id, default_service)
