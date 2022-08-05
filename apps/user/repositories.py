from typing import cast

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from utils.error import NotFoundError
from utils.mysql import MySQL
from .models import User


class UserRepository:
    def __init__(self, mysql: MySQL):
        self.mysql = mysql

    async def get_by_user_id(self, user_id: int) -> User:
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            statement = select(User).where(User.user_id == user_id)
            results = await session.exec(statement)
            user = results.first()
            return user


class UserNotFoundError(NotFoundError):
    entity_name: str = "User"
    entity_value_name: str = "user_id"
