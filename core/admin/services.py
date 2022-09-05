from typing import List

from pymysql import IntegrityError
from telegram import Bot

from core.admin.cache import BotAdminCache, GroupAdminCache
from core.admin.repositories import BotAdminRepository
from core.config import config
from utils.log import logger


class BotAdminService:
    def __init__(self, repository: BotAdminRepository, cache: BotAdminCache):
        self._repository = repository
        self._cache = cache

    async def get_admin_list(self) -> List[int]:
        admin_list = await self._cache.get_list()
        if len(admin_list) == 0:
            admin_list = await self._repository.get_all_user_id()
            for config_admin in config.admins:
                admin_list.append(config_admin["user_id"])
            await self._cache.set_list(admin_list)
        return admin_list

    async def add_admin(self, user_id: int) -> bool:
        try:
            await self._repository.add_by_user_id(user_id)
        except IntegrityError as error:
            logger.warning(f"{user_id} 已经存在数据库 \n", error)
        admin_list = await self._repository.get_all_user_id()
        for config_admin in config.admins:
            admin_list.append(config_admin["user_id"])
        await self._cache.set_list(admin_list)
        return True

    async def delete_admin(self, user_id: int) -> bool:
        try:
            await self._repository.delete_by_user_id(user_id)
        except ValueError:
            return False
        admin_list = await self._repository.get_all_user_id()
        for config_admin in config.admins:
            admin_list.append(config_admin["user_id"])
        await self._cache.set_list(admin_list)
        return True


class GroupAdminService:
    def __init__(self, cache: GroupAdminCache):
        self._cache = cache

    async def get_admins(self, bot: Bot, chat_id: int, extra_user: List[int]) -> List[int]:
        admin_id_list = await self._cache.get_chat_admin(chat_id)
        if len(admin_id_list) == 0:
            admin_list = await bot.get_chat_administrators(chat_id)
            admin_id_list = [admin.user.id for admin in admin_list]
            await self._cache.set_chat_admin(chat_id, admin_id_list)
        admin_id_list += extra_user
        return admin_id_list
