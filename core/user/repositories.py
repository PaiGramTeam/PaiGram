from typing import cast

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.base.mysql import MySQL
from .error import UserNotFoundError
from .models import User


class UserRepository:
    def __init__(self, mysql: MySQL):
        self.mysql = mysql

    async def get_by_user_id(self, user_id: int) -> User:
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            statement = select(User).where(User.user_id == user_id)
            results = await session.exec(statement)
            if user := results.first():
                return user[0]
            else:
                raise UserNotFoundError(user_id)

    async def update_user(self, user: User):
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            session.add(user)
            await session.commit()
            await session.refresh(user)

    async def add_user(self, user: User):
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            session.add(user)
            await session.commit()
