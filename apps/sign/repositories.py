from typing import List, cast, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.mysql import MySQL
from .models import Sign


class SignRepository:
    def __init__(self, mysql: MySQL):
        self.mysql = mysql

    async def add(self, sign: Sign):
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            session.add(sign)
            await session.commit()

    async def update(self, sign: Sign):
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            session.add(sign)
            await session.commit()
            await session.refresh(sign)

    async def get_by_user_id(self, user_id: int) -> Optional[Sign]:
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            statement = select(Sign).where(Sign.user_id == user_id)
            results = await session.exec(statement)
            if sign := results.first():
                return sign[0]
            return None

    async def get_all(self) -> List[Sign]:
        async with self.mysql.Session() as session:
            query = select(Sign)
            results = await session.exec(query)
            signs = results.all()
            return [sign[0] for sign in signs]
