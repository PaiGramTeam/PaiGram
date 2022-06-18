from typing import List

from pymysql import IntegrityError

from config import config
from logger import Log
from service.cache import RedisCache
from service.repository import AsyncRepository


class AdminService:
    def __init__(self, repository: AsyncRepository, cache: RedisCache):
        self.repository = repository
        self.cache = cache
        self.qname = "bot:admin"

    async def get_admin_list(self) -> List[int]:
        admin_list = await self.cache.get_int_list(self.qname)
        if len(admin_list) == 0:
            admin_list = await self.repository.get_admin()
            for config_admin in config.ADMINISTRATORS:
                admin_list.append(config_admin["user_id"])
            await self.cache.set_int_list(self.qname, admin_list, -1)
        return admin_list

    async def add_admin(self, user_id: int) -> bool:
        try:
            await self.repository.add_admin(user_id)
        except IntegrityError as error:
            Log.warning(f"{user_id} 已经存在数据库 \n", error)
        admin_list = await self.repository.get_admin()
        for config_admin in config.ADMINISTRATORS:
            admin_list.append(config_admin["user_id"])
        await self.cache.set_int_list(self.qname, admin_list, -1)
        return True

    async def delete_admin(self, user_id: int) -> bool:
        try:
            await self.repository.delete_admin(user_id)
        except ValueError:
            return False
        admin_list = await self.repository.get_admin()
        for config_admin in config.ADMINISTRATORS:
            admin_list.append(config_admin["user_id"])
        await self.cache.set_int_list(self.qname, admin_list, -1)
        return True
