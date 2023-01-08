from typing import cast

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.base_service import BaseService
from core.dependence.mysql import MySQL
from core.services.user.error import UserNotFoundError
from core.services.user.models import User

__all__ = ["UserRepository"]


class UserRepository(BaseService.Component):
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

    async def del_user_by_id(self, user_id):
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            statement = select(User).where(User.user_id == user_id)
            results = await session.execute(statement)
            user = results.unique().scalar_one()
            if user:
                await session.delete(user)
                await session.commit()
            else:
                raise UserNotFoundError(user_id)
