from typing import List, cast

from core.service import Component
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlmodel.ext.asyncio.session import AsyncSession

from core.dependence.mysql import MySQL
from core.services.cookies.error import CookiesNotFoundError
from core.services.cookies.models import Cookies, HoyolabCookie, HyperionCookie
from utils.error import RegionNotFoundError
from utils.models.base import RegionEnum

__all__ = ["CookiesRepository"]


class CookiesRepository(Component):
    def __init__(self, mysql: MySQL):
        self.mysql = mysql

    async def add_cookies(self, user_id: int, cookies: dict, region: RegionEnum):
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            if region == RegionEnum.HYPERION:
                db_data = HyperionCookie(user_id=user_id, cookies=cookies)
            elif region == RegionEnum.HOYOLAB:
                db_data = HoyolabCookie(user_id=user_id, cookies=cookies)
            else:
                raise RegionNotFoundError(region.name)
            session.add(db_data)
            await session.commit()

    async def update_cookies(self, user_id: int, cookies: dict, region: RegionEnum):
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            if region == RegionEnum.HYPERION:
                statement = select(HyperionCookie).where(HyperionCookie.user_id == user_id)
            elif region == RegionEnum.HOYOLAB:
                statement = select(HoyolabCookie).where(HoyolabCookie.user_id == user_id)
            else:
                raise RegionNotFoundError(region.name)
            results = await session.exec(statement)
            db_cookies = results.first()
            if db_cookies is None:
                raise CookiesNotFoundError(user_id)
            db_cookies = db_cookies[0]
            db_cookies.cookies = cookies
            session.add(db_cookies)
            await session.commit()
            await session.refresh(db_cookies)

    async def update_cookies_ex(self, cookies: Cookies, region: RegionEnum):
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            if region not in [RegionEnum.HYPERION, RegionEnum.HOYOLAB]:
                raise RegionNotFoundError(region.name)
            session.add(cookies)
            await session.commit()
            await session.refresh(cookies)

    async def get_cookies(self, user_id, region: RegionEnum) -> Cookies:
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            if region == RegionEnum.HYPERION:
                statement = select(HyperionCookie).where(HyperionCookie.user_id == user_id)
                results = await session.exec(statement)
                db_cookies = results.first()
                if db_cookies is None:
                    raise CookiesNotFoundError(user_id)
                return db_cookies[0]
            elif region == RegionEnum.HOYOLAB:
                statement = select(HoyolabCookie).where(HoyolabCookie.user_id == user_id)
                results = await session.exec(statement)
                db_cookies = results.first()
                if db_cookies is None:
                    raise CookiesNotFoundError(user_id)
                return db_cookies[0]
            else:
                raise RegionNotFoundError(region.name)

    async def get_all_cookies(self, region: RegionEnum) -> List[Cookies]:
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            if region == RegionEnum.HYPERION:
                statement = select(HyperionCookie)
                results = await session.exec(statement)
                db_cookies = results.all()
                return [cookies[0] for cookies in db_cookies]
            elif region == RegionEnum.HOYOLAB:
                statement = select(HoyolabCookie)
                results = await session.exec(statement)
                db_cookies = results.all()
                return [cookies[0] for cookies in db_cookies]
            else:
                raise RegionNotFoundError(region.name)

    async def del_cookies(self, user_id, region: RegionEnum):
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            if region == RegionEnum.HYPERION:
                statement = select(HyperionCookie).where(HyperionCookie.user_id == user_id)
            elif region == RegionEnum.HOYOLAB:
                statement = select(HoyolabCookie).where(HoyolabCookie.user_id == user_id)
            else:
                raise RegionNotFoundError(region.name)
            results = await session.execute(statement)
            try:
                db_cookies = results.unique().scalar_one()
            except NoResultFound as exc:
                raise CookiesNotFoundError(user_id) from exc
            await session.delete(db_cookies)
            await session.commit()
