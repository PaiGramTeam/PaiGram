from typing import Optional, List

from sqlmodel import select

from core.base_service import BaseService
from core.basemodel import RegionEnum
from core.dependence.database import Database
from core.services.cookies.models import CookiesDataBase as Cookies
from core.sqlmodel.session import AsyncSession

__all__ = ("CookiesRepository",)


class CookiesRepository(BaseService.Component):
    def __init__(self, database: Database):
        self.engine = database.engine

    async def get(
        self,
        user_id: int,
        account_id: Optional[int] = None,
        region: Optional[RegionEnum] = None,
    ) -> Optional[Cookies]:
        async with AsyncSession(self.engine) as session:
            statement = select(Cookies).where(Cookies.user_id == user_id)
            if account_id is not None:
                statement = statement.where(Cookies.account_id == account_id)
            if region is not None:
                statement = statement.where(Cookies.region == region)
            results = await session.exec(statement)
            return results.first()

    async def add(self, cookies: Cookies) -> None:
        async with AsyncSession(self.engine) as session:
            session.add(cookies)
            await session.commit()

    async def update(self, cookies: Cookies) -> Cookies:
        async with AsyncSession(self.engine) as session:
            session.add(cookies)
            await session.commit()
            await session.refresh(cookies)
            return cookies

    async def delete(self, cookies: Cookies) -> None:
        async with AsyncSession(self.engine) as session:
            await session.delete(cookies)
            await session.commit()

    async def get_all_by_region(self, region: RegionEnum) -> List[Cookies]:
        async with AsyncSession(self.engine) as session:
            statement = select(Cookies).where(Cookies.region == region)
            results = await session.exec(statement)
            cookies = results.all()
            return cookies
