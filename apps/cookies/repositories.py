from typing import cast, List

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.base import RegionEnum
from utils.error import NotFoundError, RegionNotFoundError
from utils.mysql import MySQL
from .models import HyperionCookie, HoyolabCookie, Cookies


class CookiesRepository:
    def __init__(self, mysql: MySQL):
        self.mysql = mysql

    async def add_cookies(self, user_id: int, cookies: dict, region: RegionEnum):
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            if region == RegionEnum.HYPERION:
                db_data = HyperionCookie(user_id=user_id, cookie=cookies)
            elif region == RegionEnum.HOYOLAB:
                db_data = HoyolabCookie(user_id=user_id, cookie=cookies)
            else:
                raise RegionNotFoundError(region.name)
            await session.add(db_data)
            await session.commit()

    async def update_cookies(self, user_id: int, cookies: dict, region: RegionEnum):
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            if region == RegionEnum.HYPERION:
                statement = select(HyperionCookie).where(HyperionCookie.user_id == user_id)
                results = await session.exec(statement)
                db_cookies = results.one()
                if db_cookies is None:
                    raise CookiesNotFoundError(user_id)
                db_cookies.cookie = cookies
                await session.add(db_cookies)
                await session.commit()
                await session.refresh(db_cookies)
            elif region == RegionEnum.HOYOLAB:
                statement = select(HyperionCookie).where(HyperionCookie.user_id == user_id)
                results = await session.add(statement)
                db_cookies = results.one()
                if db_cookies is None:
                    raise CookiesNotFoundError(user_id)
                db_cookies.cookie = cookies
                await session.add(db_cookies)
                await session.commit()
                await session.refresh(db_cookies)
            else:
                raise RegionNotFoundError(region.name)

    async def update_cookies_ex(self, cookies: Cookies, region: RegionEnum):
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            if region == RegionEnum.HYPERION:
                session.add(cookies)
                await session.commit()
                await session.refresh(cookies)
            elif region == RegionEnum.HOYOLAB:
                await session.add(cookies)
                await session.commit()
                await session.refresh(cookies)
            else:
                raise RegionNotFoundError(region.name)

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


class CookiesNotFoundError(NotFoundError):
    entity_name: str = "CookiesRepository"
    entity_value_name: str = "user_id"
