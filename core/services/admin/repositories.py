from typing import List, cast

from core.service import Component
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.dependence.mysql import MySQL
from core.services.admin.models import Admin

__all__ = ["BotAdminRepository"]


class BotAdminRepository(Component):
    def __init__(self, mysql: MySQL):
        self.mysql = mysql

    async def delete_by_user_id(self, user_id: int):
        async with self.mysql.Session() as session:
            session = cast(AsyncSession, session)
            statement = select(Admin).where(Admin.user_id == user_id)
            results = await session.exec(statement)
            admin = results.one()
            await session.delete(admin)

    async def add_by_user_id(self, user_id: int):
        async with self.mysql.Session() as session:
            admin = Admin(user_id=user_id)
            session.add(admin)
            await session.commit()

    async def get_all_user_id(self) -> List[int]:
        async with self.mysql.Session() as session:
            query = select(Admin)
            results = await session.exec(query)
            admins = results.all()
            return [admin[0].user_id for admin in admins]
