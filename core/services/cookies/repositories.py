from typing import Optional, List

from sqlmodel import select

from core.dependence.mysql import MySQL
from utils.models.base import RegionEnum
from core.services.cookies.models import CookiesDataBase as Cookies
from core.sqlmodel.session import AsyncSession
from core.base_service import BaseService

__all__ = ("CookiesRepository",)


class CookiesRepository(BaseService.Component):
    def __init__(self, mysql: MySQL):
        self.engine = mysql.engine

    async def get_by_user_id(self, user_id: int, region: Optional[RegionEnum]) -> Optional[Cookies]:
        async with AsyncSession(self.engine) as session:
            if region:
                statement = select(Cookies).where(Cookies.user_id == user_id).where(Cookies.region == region)
            else:
                statement = select(Cookies).where(Cookies.user_id == user_id)
            results = await session.exec(statement)
            return results.first()

    async def add(self, cookies: Cookies):
        async with AsyncSession(self.engine) as session:
            session.add(cookies)
            await session.commit()

    async def update(self, cookies: Cookies) -> Cookies:
        async with AsyncSession(self.engine) as session:
            session.add(cookies)
            await session.commit()
            await session.refresh(cookies)
            return cookies

    async def remove(self, cookies: Cookies):
        async with AsyncSession(self.engine) as session:
            await session.delete(cookies)
            await session.commit()

    async def get_all_by_region(self, region: RegionEnum) -> List[Cookies]:
        async with AsyncSession(self.engine) as session:
            statement = select(Cookies).where(Cookies.region == region)
            results = await session.exec(statement)
            cookies = results.all()
            return cookies
