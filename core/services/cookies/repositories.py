from typing import Optional, List
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession


from utils.models.base import RegionEnum
from .models import CookiesDataBase as Cookies

__all__ = ("CookiesRepository",)

from ...dependence.mysql import MySQL


class CookiesRepository:
    def __init__(self, mysql: MySQL):
        self.engine = mysql.engine

    async def get_by_user_id(self, user_id: int, region: Optional[RegionEnum]) -> Optional[Cookies]:
        async with AsyncSession(self.engine) as session:
            if region:
                statement = select(Cookies).where(Cookies.user_id == user_id and Cookies.region == region)
            else:
                statement = select(Cookies).where(Cookies.user_id == user_id)
            results = await session.exec(statement)
            return results.first()

    async def add(self, cookies: Cookies):
        async with AsyncSession(self.engine) as session:
            session.add(cookies)
            await session.commit()

    async def remove(self, cookies: Cookies):
        async with AsyncSession(self.engine) as session:
            await session.delete(cookies)
            await session.commit()

    async def get_all_by_user_id(self, user_id: int) -> List[Cookies]:
        async with AsyncSession(self.engine) as session:
            statement = select(Cookies).where(Cookies.user_id == user_id)
            results = await session.exec(statement)
            players = results.all()
            return players
