from typing import Optional, List

from sqlmodel import select

from core.base_service import BaseService
from core.dependence.database import Database
from core.services.users.models import UserDataBase as User
from core.sqlmodel.session import AsyncSession

__all__ = ("UserRepository",)


class UserRepository(BaseService.Component):
    def __init__(self, database: Database):
        self.engine = database.engine

    async def get_by_user_id(self, user_id: int) -> Optional[User]:
        async with AsyncSession(self.engine) as session:
            statement = select(User).where(User.user_id == user_id)
            results = await session.exec(statement)
            return results.first()

    async def add(self, user: User):
        async with AsyncSession(self.engine) as session:
            session.add(user)
            await session.commit()

    async def update(self, user: User) -> User:
        async with AsyncSession(self.engine) as session:
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def remove(self, user: User):
        async with AsyncSession(self.engine) as session:
            await session.delete(user)
            await session.commit()

    async def get_all(self) -> List[User]:
        async with AsyncSession(self.engine) as session:
            statement = select(User)
            results = await session.exec(statement)
            return results.all()
