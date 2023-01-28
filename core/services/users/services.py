from typing import List, Optional

from core.base_service import BaseService
from core.services.users.cache import UserAdminCache
from core.services.users.models import PermissionsEnum, UserDataBase as User
from core.services.users.repositories import UserRepository

__all__ = ("UserService", "UserAdminService")


class UserService(BaseService):
    def __init__(self, user_repository: UserRepository) -> None:
        self._repository: UserRepository = user_repository

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """从数据库获取用户信息
        :param user_id:用户ID
        :return: User
        """
        return await self._repository.get_by_user_id(user_id)

    async def remove(self, user: User):
        return await self._repository.remove(user)

    async def update_user(self, user: User):
        return await self._repository.add(user)


class UserAdminService(BaseService):
    def __init__(self, user_repository: UserRepository, cache: UserAdminCache):
        self.user_repository = user_repository
        self._cache = cache

    async def initialize(self):
        pass  # todo : 从config添加管理员

    async def get_admin_list(self) -> List[int]:
        return await self._cache.get_all()

    async def add_admin(self, user_id: int) -> bool:
        user = await self.user_repository.get_by_user_id(user_id)
        if user:
            if user.permissions != PermissionsEnum.ADMIN:
                user.permissions = PermissionsEnum.ADMIN
                await self.user_repository.update(user)
        else:
            user = User(user_id=user_id, permissions=PermissionsEnum.ADMIN)
            await self.user_repository.add(user)
        return await self._cache.set(user.user_id)

    async def delete_admin(self, user_id: int) -> bool:
        user = await self.user_repository.get_by_user_id(user_id)
        if user:
            user.permissions = PermissionsEnum.PUBLIC
            await self.user_repository.update(user)
            return await self._cache.remove(user.user_id)
        return False
