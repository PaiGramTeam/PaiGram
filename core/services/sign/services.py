from core.base_service import BaseService
from core.services.sign.models import Sign
from core.services.sign.repositories import SignRepository

__all__ = ["SignServices"]


class SignServices(BaseService):
    def __init__(self, sign_repository: SignRepository) -> None:
        self._repository: SignRepository = sign_repository

    async def get_all(self):
        return await self._repository.get_all()

    async def add(self, sign: Sign):
        return await self._repository.add(sign)

    async def remove(self, sign: Sign):
        return await self._repository.remove(sign)

    async def update(self, sign: Sign):
        return await self._repository.update(sign)

    async def get_by_user_id(self, user_id: int):
        return await self._repository.get_by_user_id(user_id)

    async def get_by_chat_id(self, chat_id: int):
        return await self._repository.get_by_chat_id(chat_id)
