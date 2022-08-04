from .models import User
from .repositories import UserRepository


class UserService:

    def __init__(self, user_repository: UserRepository) -> None:
        self._repository: UserRepository = user_repository

    async def get_user_by_id(self, user_id: int) -> User:
        """从数据库获取用户信息
        :param user_id:用户ID
        :return: User
        """
        user = await self._repository.get_by_user_id(user_id)
        return user
