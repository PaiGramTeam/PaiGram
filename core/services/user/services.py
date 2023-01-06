from core.service import Service
from core.services.user.models import User
from core.services.user.repositories import UserRepository

__all__ = ["UserService"]


class UserService(Service):
    def __init__(self, user_repository: UserRepository) -> None:
        self._repository: UserRepository = user_repository

    async def get_user_by_id(self, user_id: int) -> User:
        """从数据库获取用户信息
        :param user_id:用户ID
        :return: User
        """
        return await self._repository.get_by_user_id(user_id)

    async def del_user_by_id(self, user_id: int) -> User:
        return await self._repository.del_user_by_id(user_id)

    async def update_user(self, user: User) -> User:
        return await self._repository.update_user(user)

    async def add_user(self, user: User) -> User:
        return await self._repository.add_user(user)
