from typing import List, Optional

from sqlmodel import select

from core.base_service import BaseService
from core.dependence.database import Database
from core.services.sign.models import Sign
from core.sqlmodel.session import AsyncSession

__all__ = ("SignRepository",)


class SignRepository(BaseService.Component):
    def __init__(self, database: Database):
        self.engine = database.engine

    async def add(self, sign: Sign):
        async with AsyncSession(self.engine) as session:
            session.add(sign)
            await session.commit()

    async def remove(self, sign: Sign):
        async with AsyncSession(self.engine) as session:
            await session.delete(sign)
            await session.commit()

    async def update(self, sign: Sign) -> Sign:
        async with AsyncSession(self.engine) as session:
            session.add(sign)
            await session.commit()
            await session.refresh(sign)
            return sign

    async def get_by_user_id(self, user_id: int) -> Optional[Sign]:
        async with AsyncSession(self.engine) as session:
            statement = select(Sign).where(Sign.user_id == user_id)
            results = await session.exec(statement)
            return results.first()

    async def get_by_chat_id(self, chat_id: int) -> Optional[List[Sign]]:
        async with AsyncSession(self.engine) as session:
            statement = select(Sign).where(Sign.chat_id == chat_id)
            results = await session.exec(statement)
            return results.all()

    async def get_all(self) -> List[Sign]:
        async with AsyncSession(self.engine) as session:
            query = select(Sign)
            results = await session.exec(query)
            return results.all()
